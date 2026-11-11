"""Real CogVideoX/Hunyuan short videos using the isolated MPS runtime."""
import os
# Unsupported accelerator operators must fail instead of silently running on CPU.
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"

import argparse
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("cogvideo", "hunyuan"), default="cogvideo")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=9)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--prompt", default="A small orange cat walking slowly on green grass, daylight.")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    args.model_dir = args.model_dir or Path("models") / (args.model + "-mac")
    args.output = args.output or Path("output") / (args.model + "-mps")
    if args.size < 64 or args.size % 16 or args.frames < 5 or args.frames % 4 != 1 or args.steps < 2:
        parser.error("size >=64 divisible by16; frames >=5 and 4n+1; steps >=2")
    if args.model == "cogvideo" and (args.frames < 9 or args.frames % 8 != 1):
        parser.error("CogVideo short clips require 8n+1 frames (at least 9)")
    repo, revision = ({
        "cogvideo": ("THUDM/CogVideoX-5b", "8fc5b281006c82b82d34fd2543d2f0ebb4e7e321"),
        "hunyuan": ("hunyuanvideo-community/HunyuanVideo", "e8c2aaa66fe3742a32c11a6766aecbf07c56e773"),
    })[args.model]
    if args.download_only:
        from huggingface_hub import snapshot_download
        snapshot_download(repo, revision=revision, local_dir=args.model_dir,
                          allow_patterns=["model_index.json", "scheduler/*", "tokenizer/*", "tokenizer_2/*",
                                          "text_encoder/*.json", "text_encoder/*.safetensors",
                                          "text_encoder_2/*.json", "text_encoder_2/*.safetensors",
                                          "transformer/*.json", "transformer/*.safetensors", "vae/*.json", "vae/*.safetensors"],
                          max_workers=2)
        return
    import torch
    from diffusers import CogVideoXPipeline, HunyuanVideoPipeline
    import av
    if not torch.backends.mps.is_available():
        raise RuntimeError("Video generation requires MPS; CPU fallback disabled")
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    started = time.monotonic()
    pipeline_class = CogVideoXPipeline if args.model == "cogvideo" else HunyuanVideoPipeline
    pipe = pipeline_class.from_pretrained(str(args.model_dir), dtype=torch.bfloat16,
                                            local_files_only=True, low_cpu_mem_usage=True)
    pipe.enable_sequential_cpu_offload(device="mps")
    pipe.vae.enable_tiling()
    pipe.vae.enable_slicing()
    observed = {"text": 0, "denoise": 0, "decode": 0}
    def text_hook(module, inputs, output):
        assert output[0].device.type == "mps"
        observed["text"] += 1
    pipe.text_encoder.register_forward_hook(text_hook)
    def decode_hook(module, inputs, output):
        sample = output[0] if isinstance(output, tuple) else output
        assert sample.device.type == "mps"
        assert torch.isfinite(sample.flatten()).all().item()
        observed["decode"] += 1
    pipe.vae.decoder.register_forward_hook(decode_hook)
    def step(pipe, index, timestep, kwargs):
        assert kwargs["latents"].device.type == "mps"
        assert torch.isfinite(kwargs["latents"].flatten()).all().item()
        observed["denoise"] += 1
        return kwargs
    with torch.inference_mode():
        frames = pipe(prompt=args.prompt, height=args.size, width=args.size, num_frames=args.frames,
                      num_inference_steps=args.steps, generator=torch.Generator().manual_seed(42),
                      callback_on_step_end=step).frames[0]
    assert len(frames) == args.frames and observed["text"] > 0 and observed["decode"] > 0, (len(frames), observed)
    output = args.output / (args.model + ".mp4")
    with av.open(str(output), "w") as container:
        stream = container.add_stream("libx264", rate=8)
        stream.width = stream.height = args.size
        stream.pix_fmt = "yuv420p"
        for image in frames:
            for packet in stream.encode(av.VideoFrame.from_image(image)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    with av.open(str(output)) as container:
        assert sum(1 for _ in container.decode(video=0)) == args.frames
    report = {"device": "mps", "torch": torch.__version__, "seconds": time.monotonic()-started,
              "observed": observed, "size": args.size, "frames": args.frames, "steps": args.steps,
              "repo": repo, "revision": revision}
    (args.output / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
