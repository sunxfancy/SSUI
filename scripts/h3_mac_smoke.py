"""Fixed-revision H3 T2VA smoke test through the SSUI node's MPS runner."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO = "MiniMaxAI/MiniMax-H3"
REVISION = "42ed227ee7df40d41602854ae760620d6eb651fe"
ROOT = Path(__file__).resolve().parents[1]


def _run_guarded(command):
    """Monitor loading as well as inference, independently of GPU progress."""
    import psutil
    initial_swap = psutil.swap_memory().used
    print(f"H3 memory baseline: available={psutil.virtual_memory().available / 1024**3:.2f} GiB, "
          f"swap={initial_swap / 1024**3:.2f} GiB", flush=True)
    with subprocess.Popen(command) as process:
        try:
            while True:
                try:
                    code = process.wait(timeout=1)
                    if code:
                        raise subprocess.CalledProcessError(code, command)
                    return
                except subprocess.TimeoutExpired:
                    available = psutil.virtual_memory().available / 1024**3
                    growth = (psutil.swap_memory().used - initial_swap) / 1024**3
                    if available < 1.5 or growth > 2:
                        raise RuntimeError(f"H3 stopped: available={available:.2f} GiB (minimum 1.5), "
                                           f"swap growth={growth:.2f} GiB (maximum 2)") from None
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/h3-mac")
    parser.add_argument("--output", type=Path, default=ROOT / "output/h3-mps/h3.mp4")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=124)
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--prompt", default="A small orange cat walking slowly on grass, natural outdoor ambience.")
    args = parser.parse_args()
    if args.size < 64 or args.size % 32 or not 124 <= args.frames <= 345 or (args.frames - 5) % 17 or args.steps < 2:
        parser.error("size >=64 divisible by32; frames 124..345 and 17n+5; steps >=2")
    if args.download_only:
        from huggingface_hub import snapshot_download
        snapshot_download(REPO, revision=REVISION, local_dir=args.model_dir,
                          allow_patterns=["modular_model_index.json", "transformer/*.json", "transformer/*.safetensors",
                                          "text_encoder/*.json", "text_encoder/*.safetensors", "vae/*.json", "vae/*.safetensors",
                                          "audio_vae/*.json", "audio_vae/*.safetensors", "tokenizer/*", "processor/*",
                                          "scheduler/*", "audio_scheduler/*"], max_workers=2)
        return
    _run_guarded([sys.executable, "-u", str(ROOT / "extensions/Video/ssui_video/h3_runner.py"),
                    "--model-id", str(args.model_dir), "--device", "mps", "--quantization", "none",
                    "--task", "t2va", "--prompt", args.prompt, "--height", str(args.size), "--width", str(args.size),
                    "--num-frames", str(args.frames), "--num-inference-steps", str(args.steps),
                    "--output", str(args.output)])
    import av
    with av.open(str(args.output)) as container:
        frames = list(container.decode(video=0))
        assert len(frames) == args.frames
        assert all(frame.width == args.size and frame.height == args.size for frame in frames)
    with av.open(str(args.output)) as container:
        assert len(container.streams.audio) == 1
        assert sum(frame.samples for frame in container.decode(audio=0)) > 0
    report_path = Path(str(args.output) + ".json")
    report = json.loads(report_path.read_text())
    report.update(repo=REPO, revision=REVISION, video_audio_roundtrip=True)
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
