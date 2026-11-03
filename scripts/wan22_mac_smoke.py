"""Wan 2.2 TI2V-5B: MPS-only short T2V with mmap-backed host weights."""
import os
# Unsupported accelerator operators must fail instead of silently running on CPU.
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import wan_mac_smoke as common

ROOT = common.ROOT
REPO = "Wan-AI/Wan2.2-TI2V-5B"
REVISION = "921dbaf3f1674a56f47e83fb80a34bac8a8f203e"


def denoise(args):
    import torch
    from diffsynth.models.utils import init_weights_on_device, load_state_dict_from_safetensors
    from diffsynth.models.wan_video_dit import WanModel
    from diffsynth.pipelines.wan_video_new import WanVideoPipeline, model_fn_wan_video
    from diffsynth.schedulers.flow_match import FlowMatchScheduler
    weights = {}
    for path in sorted(args.model_dir.glob("diffusion_pytorch_model-*.safetensors")):
        weights.update(load_state_dict_from_safetensors(str(path)))
    weights, config = WanModel.state_dict_converter().from_civitai(weights)
    if config.get("dim") != 3072 or config.get("in_dim") != 48:
        raise RuntimeError("Expected official Wan 2.2 TI2V-5B weights")
    with init_weights_on_device():
        model = WanModel(**config)
    model.load_state_dict(weights, assign=True)
    del weights
    model.eval().requires_grad_(False)
    pipe = WanVideoPipeline(device="mps", torch_dtype=torch.bfloat16)
    pipe.dit = model
    pipe.enable_vram_management(vram_limit=0, vram_buffer=0)
    pipe.load_models_to_device(["dit"])
    prompts = torch.load(args.output / "prompts.pt", weights_only=True, map_location="mps")
    latent = torch.randn((1, 48, (args.frames-1)//4+1, args.size//16, args.size//16),
                         generator=torch.Generator().manual_seed(args.seed)).to("mps", dtype=torch.bfloat16)
    scheduler = FlowMatchScheduler(shift=5, sigma_min=0, extra_one_step=True)
    scheduler.set_timesteps(args.steps)
    with torch.inference_mode():
        for i, timestep in enumerate(scheduler.timesteps):
            t = timestep.unsqueeze(0).to("mps", dtype=torch.bfloat16)
            positive = model_fn_wan_video(model, latents=latent, timestep=t, context=prompts["positive"])
            negative = model_fn_wan_video(model, latents=latent, timestep=t, context=prompts["negative"])
            latent = scheduler.step(negative + 5 * (positive-negative), timestep, latent)
            common.finite(latent, "Wan 2.2 denoise")
            torch.mps.synchronize()
            torch.mps.empty_cache()
            print(f"MPS denoise {i+1}/{args.steps}", flush=True)
    torch.save(latent.cpu(), args.output / "latents.pt")


def decode(args):
    import torch
    import imageio.v2 as imageio
    from diffsynth.models.utils import init_weights_on_device
    from diffsynth.models.wan_video_vae import WanVideoVAE38
    weights = torch.load(args.model_dir / "Wan2.2_VAE.pth", mmap=True, weights_only=True, map_location="cpu")
    weights = WanVideoVAE38.state_dict_converter().from_civitai(weights)
    with init_weights_on_device():
        vae = WanVideoVAE38()
    vae.load_state_dict(weights, assign=True)
    del weights
    vae.eval().requires_grad_(False).to("mps", dtype=torch.float32)
    latent = torch.load(args.output / "latents.pt", weights_only=True, map_location="cpu").float()
    with torch.inference_mode():
        video = vae.decode(latent, device="mps", tiled=False)[0]
        common.finite(video, "Wan 2.2 decode")
        frames = ((video.permute(1,2,3,0).float()+1)*127.5).clamp(0,255).byte().cpu().numpy()
    assert frames.shape == (args.frames, args.size, args.size, 3), frames.shape
    imageio.mimwrite(args.output / "wan22.mp4", frames, fps=8, codec="libx264")
    assert len(imageio.mimread(args.output / "wan22.mp4")) == args.frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/wan22-mac")
    parser.add_argument("--text-model-dir", type=Path, default=ROOT / "models/wan-mac")
    parser.add_argument("--output", type=Path, default=ROOT / "output/wan22-mps")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=5)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prompt", default="A small orange cat walking slowly on grass, daylight, fixed camera.")
    parser.add_argument("--negative", default="blurry, distorted, text, watermark")
    parser.add_argument("--stage", choices=("text", "denoise", "decode"))
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    if args.size < 64 or args.size % 32 or args.frames < 5 or args.frames % 4 != 1 or args.steps < 2:
        parser.error("size >=64 and divisible by32; frames >=5 and 4n+1; steps >=2")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.stage:
        import torch
        import resource
        if not torch.backends.mps.is_available():
            raise RuntimeError("Wan 2.2 requires MPS; CPU fallback disabled")
        args.device = "mps"
        torch.set_num_threads(4)
        started = time.monotonic()
        if args.stage == "text":
            args.model_dir = args.text_model_dir
            common.text_stage(args)
        else:
            {"denoise": denoise, "decode": decode}[args.stage](args)
        (args.output / f"{args.stage}_metrics.json").write_text(json.dumps({"device":"mps", "seconds":time.monotonic()-started, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
        return
    from huggingface_hub import snapshot_download
    snapshot_download(REPO, revision=REVISION, local_dir=args.model_dir,
                      allow_patterns=["diffusion_pytorch_model-*.safetensors", "Wan2.2_VAE.pth", "config.json"],
                      local_files_only=args.local_files_only, max_workers=2)
    snapshot_download(common.REPO, revision=common.REVISION, local_dir=args.text_model_dir,
                      allow_patterns=["models_t5_umt5-xxl-enc-bf16.pth", "google/umt5-xxl/*"],
                      local_files_only=args.local_files_only, max_workers=2)
    if args.download_only:
        return
    for stage in ("text", "denoise", "decode"):
        subprocess.run([sys.executable, "-u", __file__, *sys.argv[1:], "--stage", stage], check=True)
    report = {"device": "mps", "repo": REPO, "revision": REVISION,
              "text_repo": common.REPO, "text_revision": common.REVISION,
              "size": args.size, "frames": args.frames, "steps": args.steps,
              "stages": {stage: json.loads((args.output / f"{stage}_metrics.json").read_text())
                         for stage in ("text", "denoise", "decode")}}
    (args.output / "report.json").write_text(json.dumps(report, indent=2))
    print(args.output / "wan22.mp4")


if __name__ == "__main__":
    main()
