"""MiniMax H3 本地推理 runner。

此脚本在独立的 H3 虚拟环境中运行（需要 Python>=3.12 / torch>=2.7 /
带 ModularPipeline 的新版 diffusers / transformers / torchao / PyAV / Pillow），
由 ssui_video/MiniMaxH3.py 通过 subprocess 调用，不依赖 SSUI 主环境。

用法示例：
  python h3_runner.py --task t2va --prompt "..." --num-frames 124 --output out.mp4
  python h3_runner.py --task fl2va --prompt "..." --image first.png --last-image last.png --output out.mp4
"""

import argparse
import sys


def _apply_int8(pipe, model_id: str, task: str) -> None:
    """按 diffusers 官方文档在加载前把 transformer / text encoder 切成 int8 并做组级 offload。
    仅用于消费级显卡（24-32GB）；80GB 大显存建议直接用 bf16（--quantization none）。
    """
    import torch
    from diffusers import MiniMaxH3Transformer3DModel, TorchAoConfig
    from diffusers.hooks import apply_group_offloading
    from torchao.quantization import Int8WeightOnlyConfig
    from transformers import Qwen3VLForConditionalGeneration
    from transformers import TorchAoConfig as TransformersTorchAoConfig

    transformer_subfolder = "transformer" if task in ("t2va", "fl2va") else "transformer_ref"
    pipe.update_components(
        transformer=MiniMaxH3Transformer3DModel.from_pretrained(
            model_id,
            subfolder=transformer_subfolder,
            dtype=torch.bfloat16,
            quantization_config=TorchAoConfig(
                Int8WeightOnlyConfig(version=2),
                modules_to_not_convert=[
                    "proj_in", "audio_proj_in", "context_embedder", "time_embedder", "time_proj",
                    "token_refiner", "norm_out", "proj_out", "audio_proj_out",
                ],
            ),
            low_cpu_mem_usage=False,
        ),
        text_encoder=Qwen3VLForConditionalGeneration.from_pretrained(
            model_id,
            subfolder="text_encoder",
            dtype=torch.bfloat16,
            quantization_config=TransformersTorchAoConfig(
                Int8WeightOnlyConfig(version=2),
                modules_to_not_convert=[
                    "model.visual",
                    "model.language_model.embed_tokens",
                    "model.language_model.norm",
                    "lm_head",
                ],
            ),
        ),
    )
    # 上面只替换了组件定义，实际加载在 load_components 里完成
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
    parser.add_argument("--height", type=int, default=None, help="短边建议 768，需为 32 的倍数")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quantization", choices=["none", "int8"], default="none")
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
            "torch>=2.7、transformers、torchao、PyAV、Pillow。" % exc,
            file=sys.stderr,
        )
        return 1

    try:
        manager = ComponentsManager()
        manager.enable_auto_cpu_offload(device="cuda")
        pipe = ModularPipeline.from_pretrained(
            args.model_id, workflow=args.task, components_manager=manager
        )

        if args.quantization == "int8":
            print("应用 int8 量化（transformer / text encoder）...")
            pipe = _apply_int8(pipe, args.model_id, args.task)

        pipe.load_components(dtype=torch.bfloat16)

        if args.quantization == "int8":
            _enable_group_offload(pipe)

        image = Image.open(args.image) if args.image else None
        last_image = Image.open(args.last_image) if args.last_image else None

        call_kwargs = dict(
            prompt=args.prompt,
            num_frames=args.num_frames,
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
