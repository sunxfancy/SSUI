"""Run a small, real Qwen-Image generation through the SSUI pixel pipeline."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import psutil
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "extensions" / "Video"), str(ROOT / "extensions" / "Image")]

from ssui.base import Prompt  # noqa: E402
from ssui.config import SSUIConfig  # noqa: E402
from ssui_image.PixelArt import FinalizePixelArt  # noqa: E402
from ssui_video.QwenImage import QwenImageGenerate, QwenImageModel  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "qwen-pixel-smoke.png")
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--vram-limit", type=float)
    parser.add_argument(
        "--prompt",
        default=(
            "pixel art game illustration, one full-body blue-haired adventurer "
            "standing beside one large glowing cyan crystal, centered composition, "
            "dark cave, strong readable silhouette, crisp hard-edged shapes, "
            "limited color palette, no text"
        ),
    )
    args = parser.parse_args()

    os.environ.setdefault("SSUI_QWEN_IMAGE_MODEL_ROOT", str(ROOT / "models"))
    os.environ.setdefault("SSUI_QWEN_IMAGE_DOWNLOAD_SOURCE", "HuggingFace")
    if args.vram_limit is not None:
        os.environ["SSUI_QWEN_IMAGE_VRAM_LIMIT_GIB"] = str(args.vram_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw_output = args.output.with_name(f"{args.output.stem}-raw.png")

    started = time.perf_counter()
    model = QwenImageModel.load(low_vram=True)
    loaded = time.perf_counter()

    generate_config = SSUIConfig()("Qwen smoke generate")
    generate_config._update["Qwen smoke generate"] = {
        "seed": 20260828,
        "width": args.size,
        "height": args.size,
        "steps": args.steps,
        "CFG": 1.0,
        "tiled": False,
    }
    generated = QwenImageGenerate(
        generate_config,
        model,
        Prompt(args.prompt),
        Prompt("blurry, antialiasing, gradients, text, watermark"),
    )
    generated._image.save(raw_output)

    finish_config = SSUIConfig()("Pixel smoke finalize")
    finish_config._update["Pixel smoke finalize"] = {
        "width": 64,
        "height": 64,
        "colors": 24,
        "alpha_threshold": 128,
        "downsample": "box",
        "preview_scale": 4,
    }
    finalized = FinalizePixelArt(finish_config, generated)
    finalized._image.save(args.output)
    finished = time.perf_counter()

    print(
        json.dumps(
            {
                "load_seconds": round(loaded - started, 2),
                "generation_seconds": round(finished - loaded, 2),
                "total_seconds": round(finished - started, 2),
                "output": str(args.output.resolve()),
                "raw_output": str(raw_output.resolve()),
                "output_size": finalized._image.size,
                "available_ram_gib": round(psutil.virtual_memory().available / 2**30, 2),
                "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
