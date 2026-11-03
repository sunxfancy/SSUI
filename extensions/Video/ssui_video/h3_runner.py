"""MiniMax H3 本地推理 runner。

此脚本在独立的 H3 虚拟环境中运行（需要 Python>=3.12 / torch>=2.7 /
带 ModularPipeline 的新版 diffusers / transformers / PyAV / Pillow），
由 ssui_video/MiniMaxH3.py 通过 subprocess 调用，不依赖 SSUI 主环境。

用法示例：
  python h3_runner.py --task t2va --prompt "..." --num-frames 124 --output out.mp4
  python h3_runner.py --task fl2va --prompt "..." --image first.png --last-image last.png --output out.mp4
"""

import argparse
import sys


def _apply_int8(pipe, quantizer_path=None):
    """Use SSUI's portable INT8 implementation in the independent H3 venv."""
    import importlib.util
    from pathlib import Path

    path = Path(quantizer_path) if quantizer_path else Path(__file__).resolve().parents[3] / "ssui" / "native_quantization.py"
    if not path.is_file():
        raise RuntimeError("SSUI quantizer not found; pass --quantizer-path /path/to/ssui/quantization.py")
    spec = importlib.util.spec_from_file_location("ssui_native_quantization", path)
    quantizer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = quantizer
    spec.loader.exec_module(quantizer)
    quantizer.quantize_model_int8(pipe.transformer, exclude=(
        "proj_in", "audio_proj_in", "context_embedder", "time_embedder", "time_proj",
        "token_refiner", "norm_out", "proj_out", "audio_proj_out",
    ))
    quantizer.quantize_model_int8(pipe.text_encoder, exclude=(
        "model.visual", "model.language_model.embed_tokens", "model.language_model.norm", "lm_head",
    ))
    return pipe


def _enable_group_offload(pipe) -> None:
    import torch
    from diffusers.hooks import apply_group_offloading

    pipe.transformer.requires_grad_(False)
    pipe.text_encoder.requires_grad_(False)
    offload = dict(
        onload_device=torch.device("cuda"),
        offload_device=torch.device("cpu"),
        use_stream=True,
    )
    pipe.transformer.enable_group_offload(
        offload_type="block_level", num_blocks_per_group=1, **offload
    )
    apply_group_offloading(pipe.text_encoder.model, offload_type="leaf_level", **offload)
    pipe.vae.to("cuda")
    pipe.audio_vae.to("cuda")


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMax H3 本地推理")
    parser.add_argument("--task", choices=["t2va", "fl2va", "ref2va"], default="t2va")
    parser.add_argument("--model-id", default="MiniMaxAI/MiniMax-H3")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--image", default=None, help="首帧图片路径（fl2va）")
    parser.add_argument("--last-image", default=None, help="尾帧图片路径（fl2va）")
    parser.add_argument("--num-frames", type=int, default=124, help="帧数（自动取整到 17n+5，5-15 秒@24fps）")
    parser.add_argument("--num-inference-steps", type=int, default=50)
    parser.add_argument("--height", type=int, default=None, help="短边建议 768，需为 32 的倍数")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quantization", choices=["none", "int8"], default="none")
    parser.add_argument("--quantizer-path", default=None, help="SSUI quantization.py path")
    parser.add_argument("--cpu-offload", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output", required=True, help="输出 mp4 路径")
    args = parser.parse_args()

    try:
        import torch
        from diffusers import ComponentsManager, ModularPipeline
        from diffusers.utils.export_utils import encode_video
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        print(
            "H3 venv 依赖不完整: %s\n"
            "请安装最新 diffusers（含 ModularPipeline / MiniMax-H3 支持）、"
            "torch>=2.7、transformers、PyAV、Pillow。" % exc,
            file=sys.stderr,
        )
        return 1

    try:
        manager = ComponentsManager()
        if args.cpu_offload and args.quantization == "none":
            manager.enable_auto_cpu_offload(device="cuda")
        pipe = ModularPipeline.from_pretrained(
            args.model_id, workflow=args.task, components_manager=manager
        )

        pipe.load_components(dtype=torch.bfloat16)
        if args.quantization == "int8":
            print("应用 SSUI int8 权重量化（transformer / text encoder）...")
            pipe = _apply_int8(pipe, args.quantizer_path)

        if args.cpu_offload and args.quantization == "int8":
            _enable_group_offload(pipe)
        elif not args.cpu_offload:
            pipe.to("cuda")

        image = Image.open(args.image) if args.image else None
        last_image = Image.open(args.last_image) if args.last_image else None

        call_kwargs = dict(
            prompt=args.prompt,
            num_frames=args.num_frames,
            num_inference_steps=args.num_inference_steps,
            generator=torch.Generator().manual_seed(args.seed),
            output=["videos", "audio", "sampling_rate"],
        )
        if args.height is not None:
            call_kwargs["height"] = args.height
        if args.width is not None:
            call_kwargs["width"] = args.width
        if args.task == "fl2va":
            if image is not None:
                call_kwargs["image"] = image
            if last_image is not None:
                call_kwargs["last_image"] = last_image

        print("开始生成（33B 全模态 DiT，本地较慢，请耐心等待）...")
        results = pipe(**call_kwargs)

        encode_video(
            results["videos"][0],
            fps=24,
            output_path=args.output,
            audio=results["audio"][0],
            audio_sample_rate=results["sampling_rate"],
        )
        print("输出已写入: %s" % args.output)
        return 0
    except Exception as exc:  # noqa: BLE001
        print("MiniMax H3 推理失败: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
