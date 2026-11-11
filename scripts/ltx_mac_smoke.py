"""Fixed-revision LTX-2.5 distilled short video on MPS with disk offload."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = "Lightricks/LTX-2.5"
REVISION = "49b093a39c19169a8a81721dcc541e07e945232f"
FILES = {
    "transformer": "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors",
    "text-encoder": "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
    "video-vae": "vae/ltx-2.5-video-vae-bf16.safetensors",
    "audio-vae": "vae/ltx-2.5-audio-vae-bf16.safetensors",
    "spatial-upsampler": "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/ltx-2.5")
    parser.add_argument("--output", type=Path, default=ROOT / "output/ltx-mps/ltx.mp4")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=9)
    parser.add_argument("--prompt", default="A small orange cat walking slowly on green grass in daylight.")
    args = parser.parse_args()
    if args.size < 128 or args.size % 64 or args.frames < 9 or (args.frames - 1) % 8:
        parser.error("size >=128 divisible by64; frames >=9 and 8n+1")
    if args.download_only:
        from huggingface_hub import snapshot_download
        snapshot_download(REPO, revision=REVISION, local_dir=args.model_dir,
                          allow_patterns=list(FILES.values()), max_workers=2)
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-u", str(ROOT / "extensions/Video/ssui_video/ltx_runner.py"),
               "--execution-report", str(args.output) + ".execution.json",
               "--module", "distilled", "--offload", "disk", "--prompt", args.prompt,
               "--height", str(args.size), "--width", str(args.size), "--num-frames", str(args.frames),
               "--seed", "42", "--output-path", str(args.output)]
    for name, filename in FILES.items():
        command.extend([f"--{name}-path", str(args.model_dir / filename)])
    started = time.monotonic()
    import psutil
    initial_swap = psutil.swap_memory().used
    print(f"LTX memory baseline: available={psutil.virtual_memory().available / 1024**3:.2f} GiB, swap={initial_swap / 1024**3:.2f} GiB", flush=True)
    with subprocess.Popen(command) as process:
        try:
            while True:
                try:
                    code = process.wait(timeout=1)
                    if code:
                        raise subprocess.CalledProcessError(code, command)
                    break
                except subprocess.TimeoutExpired:
                    available = psutil.virtual_memory().available / 1024**3
                    swap_growth = (psutil.swap_memory().used - initial_swap) / 1024**3
                    if available < 1.5 or swap_growth > 2:
                        raise RuntimeError(f"LTX stopped: available={available:.2f} GiB (minimum 1.5), "
                                           f"swap growth={swap_growth:.2f} GiB (maximum 2)") from None
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    import av
    with av.open(str(args.output)) as container:
        frames = list(container.decode(video=0))
        assert len(frames) == args.frames
        assert all(frame.width == args.size and frame.height == args.size for frame in frames)
    report = {"repo": REPO, "revision": REVISION, "seconds": time.monotonic() - started,
              "frames": args.frames, "size": args.size, "offload": "disk"}
    report.update(json.loads(Path(str(args.output) + ".execution.json").read_text()))
    Path(str(args.output) + ".json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
