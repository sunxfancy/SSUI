"""MiniMax H3 本地推理 runner。

此脚本在独立的 H3 虚拟环境中运行（需要 Python>=3.12 / torch>=2.7 /
带 ModularPipeline 的新版 diffusers / transformers / PyAV / Pillow），
由 ssui_video/MiniMaxH3.py 通过 subprocess 调用，不依赖 SSUI 主环境。

用法示例：
  python h3_runner.py --task t2va --prompt "..." --num-frames 124 --output out.mp4
  python h3_runner.py --task fl2va --prompt "..." --image first.png --last-image last.png --output out.mp4
"""

import os
import argparse
import json
from pathlib import Path
import time
import sys
import traceback


def _guard_mps_memory(pipe):
    """Bound queued work and fail before exhausting a small unified-memory Mac."""
    import torch
    import psutil
    initial_swap = psutil.swap_memory().used

    def before(name, index):
        def hook(module, inputs):
            available = psutil.virtual_memory().available
            if psutil.swap_memory().used - initial_swap > 2 * 1024**3:
                raise RuntimeError(f"H3 stopped before {name} block {index}: system swap grew by over 2 GiB")
            if available < 1.5 * 1024**3:
                raise RuntimeError(f"H3 stopped before {name} block {index}: less than 1.5 GiB system memory available")
            if index % 10 == 0:
                print(f"MPS {name} block {index}: available={available / 1024**3:.2f} GiB", flush=True)
        return hook

    def after(module, inputs, output):
        torch.mps.synchronize()
        torch.mps.empty_cache()

    for name, blocks in (("text", pipe.text_encoder.model.language_model.layers),
                         ("denoise", pipe.transformer.transformer_blocks),
                         ("video_decode", pipe.vae.decoder.transformer_blocks)):
        for index, block in enumerate(blocks):
            block.register_forward_pre_hook(before(name, index))
            block.register_forward_hook(after)


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


def _checkpoint_offload(model, checkpoint_dir):
    """Read each weight on demand instead of retaining the full CPU state dict."""
    import torch
    from accelerate import cpu_offload
    from accelerate.utils import OffloadedWeightsLoader
    from safetensors import safe_open

    state = model.state_dict()
    index = {}
    for path in sorted(Path(checkpoint_dir).glob("*.safetensors")):
        with safe_open(str(path), framework="pt", device="cpu") as archive:
            for key in archive.keys():
                if key in state:
                    index[key] = {"safetensors_file": str(path.resolve()), "weight_name": key,
                                  "dtype": str(state[key].dtype).removeprefix("torch.")}
    missing = set(dict(model.named_parameters())) - index.keys()
    if missing:
        raise ValueError(f"Checkpoint cannot stream all parameters: {sorted(missing)[:5]}")
    buffers = {key: value for key, value in state.items() if key not in index}
    del state
    weights = OffloadedWeightsLoader(state_dict=buffers, index=index, device="cpu")
    cpu_offload(model, execution_device=torch.device("mps"), offload_buffers=True, state_dict=weights)


def _enable_offload(pipe, device="cuda", model_root=None) -> None:
    import torch
    from diffusers.hooks import apply_group_offloading

    pipe.transformer.requires_grad_(False)
    pipe.text_encoder.requires_grad_(False)
    if torch.device(device).type == "mps":
        if model_root is None or not Path(model_root).is_dir():
            raise ValueError("H3 MPS requires a local checkpoint: run yarn test:h3:smoke --download-only first")
        for name in ("transformer", "text_encoder", "vae"):
            _checkpoint_offload(getattr(pipe, name), Path(model_root) / name)
        # Audio weight_norm pre-hooks require weights before the forward hook.
        # Keep this ~0.6GB decoder on MPS; its weights remain float32.
        pipe.audio_vae.to(device)
        return
    offload = dict(
        onload_device=torch.device(device),
        offload_device=torch.device("cpu"),
        use_stream=torch.device(device).type == "cuda",
    )
    pipe.transformer.enable_group_offload(
        offload_type="block_level", num_blocks_per_group=1, **offload
    )
    apply_group_offloading(pipe.text_encoder.model, offload_type="leaf_level", **offload)
    pipe.vae.to(device)
    pipe.audio_vae.to(device)


def main() -> int:
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
    parser = argparse.ArgumentParser(description="MiniMax H3 本地推理")
    parser.add_argument("--device", choices=["auto", "cuda", "mps"], default="auto")
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
        device = args.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps"
        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("H3 requires an available MPS accelerator; CPU fallback is disabled")
        if device == "mps" and args.quantization != "none":
            raise ValueError("H3 MPS requires --quantization none; CUDA int8/NF4 kernels are unsupported")
        if device == "mps":
            torch.set_num_threads(4)
            torch.mps.set_per_process_memory_fraction(0.35)
        manager = ComponentsManager()
        if device == "cuda" and args.cpu_offload and args.quantization == "none":
            manager.enable_auto_cpu_offload(device=device)
        pipe = ModularPipeline.from_pretrained(
            args.model_id, workflow=args.task, components_manager=manager
        )

        # from_pretrained already selected the workflow's sequential blocks.
        # Selecting it again is invalid on the resulting SequentialPipelineBlocks.
        # The released video VAE is FP32. Preserve its file-backed storage on
        # MPS instead of allocating several GiB of converted CPU BF16 weights.
        dtype = {"default": torch.bfloat16, "vae": torch.float32} if device == "mps" else torch.bfloat16
        pipe.load_components(dtype=dtype)

        if args.quantization == "int8":
            pipe = _apply_int8(pipe, args.quantizer_path)
        if device == "mps" or (args.cpu_offload and args.quantization == "int8"):
            _enable_offload(pipe, device=device, model_root=args.model_id)
        elif not args.cpu_offload:
            pipe.to(device)
        if device == "mps":
            _guard_mps_memory(pipe)

        observed = {"text": 0, "denoise": 0, "video_decode": 0, "audio_decode": 0}
        def check_device(name):
            def hook(module, inputs, output):
                if hasattr(output, "last_hidden_state"):
                    value = output.last_hidden_state
                elif hasattr(output, "sample"):
                    value = output.sample
                else:
                    value = output
                values = value if isinstance(value, tuple) else (value,)
                tensors = [item for item in values if isinstance(item, torch.Tensor)]
                for tensor in tensors:
                    if tensor.device.type != device:
                        raise RuntimeError(f"{name} executed on {tensor.device}, expected {device}")
                    if not torch.isfinite(tensor.flatten()).all().item():
                        raise RuntimeError(f"Non-finite output from {name}")
                if tensors:
                    observed[name] += 1
            return hook
        if device == "mps":
            for name, module in (("text", pipe.text_encoder.model), ("denoise", pipe.transformer),
                                 ("video_decode", pipe.vae.decoder), ("audio_decode", pipe.audio_vae.decoder)):
                module.register_forward_hook(check_device(name))
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()

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

        if device == "mps" and not all(observed.values()):
            raise RuntimeError(f"Missing MPS execution evidence: {observed}")
        encode_video(
            results["videos"][0],
            fps=24,
            output_path=args.output,
            audio=results["audio"][0],
            audio_sample_rate=results["sampling_rate"],
        )
        Path(args.output + ".json").write_text(json.dumps({
            "device": device, "torch": torch.__version__, "seconds": time.monotonic() - started,
            "observed": observed, "frames": args.num_frames, "steps": args.num_inference_steps,
            "model": args.model_id,
        }, indent=2))
        print("输出已写入: %s" % args.output)
        return 0
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        print("MiniMax H3 推理失败: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
