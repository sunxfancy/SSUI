"""Wan 1.3B short video: isolated text, denoise and decode processes for 16GB Macs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'extensions/Video')]
REPO = 'Wan-AI/Wan2.1-T2V-1.3B'
REVISION = '37ec512624d61f7aa208f7ea8140a131f93afc9a'
WEIGHTS = {
    'models_t5_umt5-xxl-enc-bf16.pth': '7cace0da2b446bbbbc57d031ab6cf163a3d59b366da94e5afe36745b746fd81d',
    'diffusion_pytorch_model.safetensors': '96b6b242ca1c2f24e9d02cd6596066fab6d310e2d7538f33ae267cb18d957e8f',
    'Wan2.1_VAE.pth': '38071ab59bd94681c686fa51d75a1968f64e470262043be31f7a094e442fd981',
}


def finite(tensor, label):
    import torch
    # Torch 2.4 MPS reductions cannot handle axis 4 of a video tensor.
    if not torch.isfinite(tensor.reshape(-1)).all().item():
        raise RuntimeError(f'Non-finite values in {label}')


def text_stage(args):
    import torch
    from diffsynth.models.utils import init_weights_on_device
    from diffsynth.models.wan_video_text_encoder import WanTextEncoder
    from diffsynth.prompters.wan_prompter import WanPrompter
    # File-backed CPU tensors can be reclaimed by macOS; never allocate a second
    # full UMT5 copy. Only one transformer block is transferred to MPS at a time.
    weights = torch.load(args.model_dir / 'models_t5_umt5-xxl-enc-bf16.pth',
                         map_location='cpu', weights_only=True, mmap=True)
    with init_weights_on_device():
        model = WanTextEncoder()
    model.load_state_dict(weights, assign=True)
    del weights
    model.eval().requires_grad_(False)
    prompter = WanPrompter(str(args.model_dir / 'google/umt5-xxl'))
    ids, mask = prompter.tokenizer([args.prompt, args.negative], return_mask=True, add_special_tokens=True)
    with torch.inference_mode():
        x = model.token_embedding(ids).to(args.device, dtype=torch.bfloat16)
        model.token_embedding.to('meta')
        mask = mask.to(args.device)
        for index, block in enumerate(model.blocks):
            block.to(args.device, dtype=torch.bfloat16)
            x = block(x, mask, pos_bias=None)
            finite(x, f'UMT5 block {index}')
            block.to('meta')
            if args.device == 'mps':
                torch.mps.synchronize()
                torch.mps.empty_cache()
            print(f'UMT5 block {index + 1}/{len(model.blocks)}', flush=True)
        model.norm.to(args.device, dtype=torch.bfloat16)
        x = model.norm(x)
        x = x.masked_fill(~mask.bool().unsqueeze(-1), 0)
        finite(x, 'prompt embeddings')
        torch.save({'positive': x[:1].cpu(), 'negative': x[1:].cpu()}, args.output / 'prompts.pt')


def denoise_stage(args):
    import torch
    from diffsynth.models.utils import init_weights_on_device, load_state_dict_from_safetensors
    from diffsynth.models.wan_video_dit import WanModel
    from diffsynth.pipelines.wan_video import model_fn_wan_video
    from diffsynth.schedulers.flow_match import FlowMatchScheduler
    # Convert individual mmap-backed tensors before allocating GPU weights.
    weights = load_state_dict_from_safetensors(str(args.model_dir / 'diffusion_pytorch_model.safetensors'), torch_dtype=torch.bfloat16)
    weights, config = WanModel.state_dict_converter().from_civitai(weights)
    if config.get('dim') != 1536 or config.get('num_layers') != 30:
        raise RuntimeError('Expected official Wan 2.1 T2V 1.3B checkpoint')
    with init_weights_on_device():
        model = WanModel(**config)
    model.load_state_dict(weights, assign=True)
    del weights
    model.eval().requires_grad_(False).to(args.device)
    prompts = torch.load(args.output / 'prompts.pt', weights_only=True, map_location=args.device)
    scheduler = FlowMatchScheduler(shift=5, sigma_min=0, extra_one_step=True)
    scheduler.set_timesteps(args.steps, denoising_strength=1, shift=5)
    latent = torch.randn((1, 16, (args.frames - 1) // 4 + 1, args.size // 8, args.size // 8),
                         generator=torch.Generator('cpu').manual_seed(args.seed)).to(args.device, dtype=torch.bfloat16)
    with torch.inference_mode():
        for index, timestep in enumerate(scheduler.timesteps):
            started = time.monotonic()
            t = timestep.unsqueeze(0).to(args.device, dtype=torch.bfloat16)
            positive = model_fn_wan_video(model, x=latent, timestep=t, context=prompts['positive'])
            negative = model_fn_wan_video(model, x=latent, timestep=t, context=prompts['negative'])
            noise = negative + args.cfg * (positive - negative)
            latent = scheduler.step(noise, timestep, latent)
            finite(latent, f'denoising step {index}')
            print(f'Denoise {index + 1}/{args.steps}: {time.monotonic() - started:.1f}s', flush=True)
    torch.save(latent.cpu(), args.output / 'latents.pt')


def decode_stage(args):
    import torch
    import numpy as np
    import imageio.v2 as imageio
    from PIL import Image
    from diffsynth.models.utils import init_weights_on_device
    from diffsynth.models.wan_video_vae import WanVideoVAE
    weights = torch.load(args.model_dir / 'Wan2.1_VAE.pth', map_location='cpu', weights_only=True, mmap=True)
    weights = WanVideoVAE.state_dict_converter().from_civitai(weights)
    with init_weights_on_device():
        model = WanVideoVAE()
    model.load_state_dict(weights, assign=True)
    del weights
    # VAE is small enough for FP32 and benefits from full decode precision.
    model.eval().requires_grad_(False).to(args.device, dtype=torch.float32)
    latent = torch.load(args.output / 'latents.pt', weights_only=True, map_location='cpu').float()
    with torch.inference_mode():
        video = model.decode(latent, device=args.device, tiled=False)[0]
        finite(video, 'VAE output')
        arrays = ((video.float().permute(1, 2, 3, 0) + 1) * 127.5).clamp(0, 255).byte().cpu().numpy()
    if arrays.shape != (args.frames, args.size, args.size, 3) or any(frame.std() < 1 for frame in arrays):
        raise RuntimeError(f'Invalid or blank video: {arrays.shape}')
    imageio.mimwrite(args.output / 'wan.mp4', arrays, fps=args.fps, codec='libx264')
    decoded = imageio.mimread(args.output / 'wan.mp4')
    if len(decoded) != args.frames or decoded[0].shape != arrays[0].shape:
        raise RuntimeError('MP4 round-trip validation failed')
    preview = Image.new('RGB', (args.size * 4, args.size))
    for column, index in enumerate(np.linspace(0, args.frames - 1, 4, dtype=int)):
        preview.paste(Image.fromarray(arrays[index]), (column * args.size, 0))
    preview.save(args.output / 'preview.png')
    (args.output / 'video_metrics.json').write_text(json.dumps({
        'frame_std': [float(a.std()) for a in arrays],
        'mean_frame_difference': float(np.abs(arrays[-1].astype(float) - arrays[0]).mean()),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=ROOT / 'models/wan-mac')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/wan-mac')
    parser.add_argument('--size', type=int, default=256)
    parser.add_argument('--frames', type=int, default=9)
    parser.add_argument('--steps', type=int, default=30)
    parser.add_argument('--fps', type=int, default=8)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cfg', type=float, default=5)
    parser.add_argument('--device', choices=['mps', 'cpu'], default='mps')
    parser.add_argument('--prompt', default='A small orange cat walking slowly across a green lawn, daylight, fixed camera, realistic video.')
    parser.add_argument('--negative', default='blurry, distorted, static, text, watermark, low quality')
    parser.add_argument('--local-files-only', action='store_true')
    parser.add_argument('--download-only', action='store_true')
    parser.add_argument('--stage', choices=['text', 'denoise', 'decode'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.size < 64 or args.size % 16 or args.frames < 5 or args.frames % 4 != 1 or args.steps < 2 or args.fps < 1:
        parser.error('size >=64 and divisible by16; frames >=5 and 4n+1; steps >=2; fps >=1')
    args.model_dir = args.model_dir.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.stage:
        import resource
        import torch
        torch.set_num_threads(4)
        started = time.monotonic()
        {'text': text_stage, 'denoise': denoise_stage, 'decode': decode_stage}[args.stage](args)
        metrics = {'torch': torch.__version__, 'device': args.device,
                   'dtype': 'float32' if args.stage == 'decode' else 'bfloat16',
                   'seconds': time.monotonic() - started, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)}
        (args.output / f'{args.stage}_metrics.json').write_text(json.dumps(metrics, indent=2))
        print(f'{args.stage} complete: {metrics}', flush=True)
        return
    from huggingface_hub import snapshot_download
    snapshot_download(REPO, revision=REVISION, local_dir=args.model_dir,
                      allow_patterns=list(WEIGHTS) + ['google/umt5-xxl/*'],
                      local_files_only=args.local_files_only, max_workers=2)
    for filename, expected in WEIGHTS.items():
        digest = hashlib.sha256()
        with (args.model_dir / filename).open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f'Checksum mismatch: {filename}')
        print(f'SHA256 verified: {filename}', flush=True)
    if args.download_only:
        return
    import psutil
    memory = {'physical_bytes': psutil.virtual_memory().total,
              'min_system_available_bytes': psutil.virtual_memory().available,
              'initial_system_swap_bytes': psutil.swap_memory().used,
              'max_system_swap_bytes': psutil.swap_memory().used}
    for stage in ('text', 'denoise', 'decode'):
        print(f'Starting isolated {stage} stage', flush=True)
        command = [sys.executable, '-u', str(Path(__file__).resolve()), *sys.argv[1:], '--stage', stage]
        process = subprocess.Popen(command)
        try:
            while process.poll() is None:
                memory['min_system_available_bytes'] = min(memory['min_system_available_bytes'], psutil.virtual_memory().available)
                memory['max_system_swap_bytes'] = max(memory['max_system_swap_bytes'], psutil.swap_memory().used)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
    report = {'memory': memory, 'repo': REPO, 'revision': REVISION, 'sha256': WEIGHTS,
              'parameters': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              'stages': {stage: json.loads((args.output / f'{stage}_metrics.json').read_text()) for stage in ('text', 'denoise', 'decode')},
              'video': str(args.output / 'wan.mp4'),
              'metrics': json.loads((args.output / 'video_metrics.json').read_text())}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
