"""Real AnimateDiff node: pinned downloads -> image -> video -> verified MP4."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extensions/Video"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/video-smoke")
    parser.add_argument("--output", type=Path, default=ROOT / "output/video-smoke")
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--frames", type=int, default=4)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--workflow", action="store_true", help="Run the example through the SSUI sandbox loader")
    parser.add_argument("--prompt", default="A small sailboat on a calm blue lake, mountains in the background, daylight, detailed landscape painting")
    args = parser.parse_args()
    if args.size < 64 or args.size % 64 or args.frames < 2 or args.steps < 2:
        parser.error("size must be a positive multiple of 64; frames and steps must be at least 2")

    from huggingface_hub import hf_hub_download
    import yaml
    manifest = yaml.safe_load((ROOT / "tests/model_manifest.yaml").read_text(encoding="utf-8"))["diffsynth"]
    paths = []
    for key in ("sd1", "animatediff"):
        entry = manifest[key]
        print(f"Model: {entry['repo']} @ {entry['revision']}", flush=True)
        paths.append(hf_hub_download(entry["repo"], entry["file"], revision=entry["revision"],
                                    local_dir=args.model_dir / key, local_files_only=args.local_files_only))
        if entry.get("sha256"):
            digest = hashlib.sha256()
            with open(paths[-1], "rb") as source:
                for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Checksum mismatch: {paths[-1]}")
            print(f"SHA-256 verified: {entry['file']}", flush=True)
    if args.download_only:
        return

    import torch
    import numpy as np
    import imageio.v2 as imageio
    from PIL import Image
    from backend.util.devices import TorchDevice
    from ssui.config import SSUIConfig
    from ssui.base import Prompt
    from ssui_video.AnimateDiff import AnimateDiffModel, AnimateDiffTextToVideo
    TorchDevice.config.device = args.device
    device = TorchDevice.choose_torch_device()
    print(f"Loading real models on {device}", flush=True)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    started = time.monotonic()
    parameters = {"width": args.size, "height": args.size, "num_frames": args.frames,
                  "num_inference_steps": args.steps, "seed": args.seed, "cfg_scale": 7.5,
                  "denoising_strength": 0.9}
    negative = Prompt("blurry, low quality, text, watermark")
    if args.workflow:
        from ss_executor.loader import SSLoader
        os.environ["SSUI_ANIMATEDIFF_CHECKPOINT"] = paths[0]
        os.environ["SSUI_ANIMATEDIFF_MOTION"] = paths[1]
        loader = SSLoader()
        loader.load(str(ROOT / "examples/advance/workflow-video-mac.py"))
        loader.Execute()
        loader.GetConfig("txt2vid_animatediff")
        loader.config.set_prepared(False)
        for key, value in parameters.items():
            loader.config("Generate Video")[key] = value
        fn = next(fn for fn, _, _ in loader.callables if fn.__name__ == "txt2vid_animatediff")
        frames = fn(Prompt(args.prompt), negative)._frames
        loaded = started  # Loading happens inside the workflow; included in generation time.
        dtype = TorchDevice.choose_torch_dtype(device)
    else:
        model = AnimateDiffModel(checkpoint_path=paths[0], motion_path=paths[1])
        loaded = time.monotonic()
        names = set(model.model_manager.model_name)
        required = {"sd_unet", "sd_text_encoder", "sd_vae_encoder", "sd_vae_decoder", "sd_motion_modules"}
        if not required <= names:
            raise RuntimeError(f"Missing real model components: {required - names}")
        config = SSUIConfig()("video_smoke")
        for key, value in parameters.items():
            config[key] = value
        frames = AnimateDiffTextToVideo(config, model, Prompt(args.prompt), negative)
        dtype = model.model_manager.torch_dtype
    generated = time.monotonic()
    if len(frames) != args.frames:
        raise RuntimeError(f"Expected {args.frames} frames, got {len(frames)}")
    arrays = [np.asarray(frame.convert("RGB")) for frame in frames]
    if any(a.shape != (args.size, args.size, 3) or a.std() < 1 for a in arrays):
        raise RuntimeError("Invalid dimensions or blank output frame")
    args.output.mkdir(parents=True, exist_ok=True)
    video_path = args.output / "animatediff.mp4"
    imageio.mimwrite(video_path, arrays, fps=4, codec="libx264")
    decoded = imageio.mimread(video_path)
    if len(decoded) != args.frames or decoded[0].shape != arrays[0].shape:
        raise RuntimeError("Encoded video failed frame count/dimension validation")
    preview = Image.new("RGB", (args.size * min(args.frames, 4), args.size))
    preview_indices = np.linspace(0, len(frames) - 1, min(args.frames, 4), dtype=int).tolist()
    for i, frame_index in enumerate(preview_indices):
        preview.paste(frames[frame_index], (i * args.size, 0))
    preview.save(args.output / "preview.png")
    report = {"device": str(device), "torch": torch.__version__, "dtype": str(dtype),
              "seed": args.seed, "prompt": args.prompt, "frames": len(frames), "size": args.size,
              "steps": args.steps, "models": manifest, "workflow": args.workflow, "load_seconds": None if args.workflow else loaded - started,
              "generation_seconds": generated - loaded, "video": str(video_path),
              "frame_std": [float(a.std()) for a in arrays],
              "mean_frame_difference": float(np.abs(arrays[-1].astype(float) - arrays[0]).mean())}
    if device.type == "cuda":
        report.update(hip=torch.version.hip, gpu=torch.cuda.get_device_name(device),
                      peak_vram_bytes=torch.cuda.max_memory_allocated(device))
    import psutil
    report["peak_rss_bytes"] = getattr(psutil.Process().memory_info(), "peak_wset", None)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
