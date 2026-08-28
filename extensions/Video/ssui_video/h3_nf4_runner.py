"""MiniMax H3 pruned NF4 runner based on DiffSynth-Studio.

This runner lives in the isolated H3 environment. Install a current
DiffSynth-Studio checkout (or pass ``--diffsynth-root``) and bitsandbytes.
It writes the joint video/audio result directly so SSUI does not discard the
model's native audio track.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


NF4_FILES = (
    "minimax-h3-fl2va-pruned-nf4.safetensors",
    "minimax-h3-text-encoder-nf4.safetensors",
    "video_vae_nf4.safetensors",
    "audio_vae_nf4.safetensors",
)


def _prepend_diffsynth_root(root: str | None) -> None:
    if not root:
        return
    path = Path(root).expanduser().resolve()
    if not (path / "diffsynth").is_dir():
        raise FileNotFoundError(
            f"DiffSynth-Studio checkout not found at {path}; expected {path / 'diffsynth'}"
        )
    sys.path.insert(0, str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMax H3 pruned NF4 inference")
    parser.add_argument("--task", choices=["t2va", "fl2va"], default="t2va")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--image", default=None)
    parser.add_argument("--last-image", default=None)
    parser.add_argument("--num-frames", type=int, default=124)
    parser.add_argument("--num-inference-steps", type=int, default=50)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--width", type=int, default=1344)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--diffsynth-root", default=None)
    parser.add_argument("--processor-model-id", default="MiniMax/MiniMax-H3")
    parser.add_argument("--vram-reserve-gib", type=float, default=2.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        _prepend_diffsynth_root(args.diffsynth_root)

        import torch

        # The Windows ROCm build has a reduced distributed module. DiffSynth
        # only needs these helpers here to decide whether this process may log.
        if not hasattr(torch.distributed, "is_initialized"):
            torch.distributed.is_initialized = lambda: False
        if not hasattr(torch.distributed, "get_rank"):
            torch.distributed.get_rank = lambda: 0

        from diffsynth.pipelines.minimax_h3_audio_video import (
            MiniMaxH3Pipeline,
            ModelConfig,
        )
        from diffsynth.utils.data.audio_video import write_video_audio
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        print(
            "H3 NF4 运行环境不完整: %s\n"
            "请在独立 H3 venv 中安装当前 DiffSynth-Studio、bitsandbytes、"
            "transformers、PyAV 和 Pillow。" % exc,
            file=sys.stderr,
        )
        return 1

    try:
        if not torch.cuda.is_available():
            raise RuntimeError("PyTorch 未检测到 CUDA/ROCm GPU")

        model_root = Path(args.model_root).expanduser().resolve()
        missing = [name for name in NF4_FILES if not (model_root / name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"H3 NF4 权重不完整（目录 {model_root}），缺少: {', '.join(missing)}"
            )

        total_vram_gib = torch.cuda.mem_get_info("cuda")[1] / (1024**3)
        vram_limit = max(total_vram_gib - args.vram_reserve_gib, 1.0)
        print(
            f"加载 H3 pruned NF4：GPU={torch.cuda.get_device_name(0)}, "
            f"总显存={total_vram_gib:.2f} GiB, 常驻上限={vram_limit:.2f} GiB"
        )
        vram_config = {
            "offload_dtype": "disk",
            "offload_device": "disk",
            "onload_dtype": "disk",
            "onload_device": "disk",
            "preparing_dtype": torch.bfloat16,
            "preparing_device": "cuda",
            "computation_dtype": torch.bfloat16,
            "computation_device": "cuda",
        }
        pipe = MiniMaxH3Pipeline.from_pretrained(
            torch_dtype=torch.bfloat16,
            device="cuda",
            model_configs=[
                ModelConfig(path=str(model_root / name), **vram_config)
                for name in NF4_FILES
            ],
            processor_config=ModelConfig(
                model_id=args.processor_model_id,
                origin_file_pattern="FL2VA/processor/",
            ),
            vram_limit=vram_limit,
        )

        kwargs = {
            "prompt": args.prompt,
            "height": args.height,
            "width": args.width,
            "num_frames": args.num_frames,
            "num_inference_steps": args.num_inference_steps,
            "seed": args.seed,
        }
        if args.task == "fl2va":
            if not args.image:
                raise ValueError("fl2va 需要 --image 首帧")
            keyframes = [Image.open(args.image).convert("RGB")]
            keyframe_indices = [0]
            if args.last_image:
                keyframes.append(Image.open(args.last_image).convert("RGB"))
                keyframe_indices.append(-1)
            kwargs.update(
                keyframes=keyframes,
                keyframe_indices=keyframe_indices,
            )

        print("开始生成 H3 视频与音频...")
        torch.cuda.reset_peak_memory_stats()
        video, audio = pipe(**kwargs)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        write_video_audio(
            video=video,
            audio=audio,
            output_path=str(output),
            fps=24,
            audio_sample_rate=32000,
        )
        print(f"推理峰值显存: {torch.cuda.max_memory_allocated() / (1024**3):.2f} GiB")
        print(f"输出已写入: {output}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print("MiniMax H3 NF4 推理失败: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
