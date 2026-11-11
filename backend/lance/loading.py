# SPDX-License-Identifier: Apache-2.0
"""Strict, tensor-at-a-time checkpoint loading and quantization."""

import json
from pathlib import Path

import torch
from torch import nn

from .geometry import BagelRotaryEmbedding
from .quantization import QUANTIZATION_MODES, QuantizedLinear


class CheckpointReader:
    def __init__(self, folder):
        from safetensors import safe_open

        self.files = {}
        folder = Path(folder)
        indexes = list(folder.glob("*.safetensors.index.json"))
        if len(indexes) > 1:
            raise ValueError(f"Ambiguous safetensors indexes in {folder}")
        if indexes:
            index = json.loads(indexes[0].read_text())["weight_map"]
            candidates = sorted(set(index.values()))
            paths = [(folder / name).resolve() for name in candidates]
            if any(not p.is_relative_to(folder.resolve()) for p in paths):
                raise ValueError("Checkpoint shard path escapes model directory")
        else:
            paths = sorted(folder.glob("*.safetensors"))
        if not paths:
            raise FileNotFoundError(f"No safetensors checkpoint in {folder}")
        for path in paths:
            with safe_open(str(path), framework="pt", device="cpu") as handle:
                for key in handle.keys():
                    if key in self.files:
                        raise ValueError(f"Duplicate tensor in checkpoint: {key}")
                    self.files[key] = path

    def shape(self, key):
        from safetensors import safe_open

        with safe_open(str(self.files[key]), framework="pt", device="cpu") as handle:
            return tuple(handle.get_slice(key).get_shape())

    def tensor(self, key):
        from safetensors import safe_open

        with safe_open(str(self.files[key]), framework="pt", device="cpu") as handle:
            return handle.get_tensor(key)


def load_streamed(
    model,
    reader,
    *,
    quantization="nf4",
    device="cpu",
    dtype=torch.float32,
    quantize_vision=False,
):
    """Materialize each leaf independently, quantizing before its GPU transfer.

    ``reader`` must expose files/shape/tensor. All shapes and keys are validated
    before any mutation. The caller overlays separate ViT weights if needed.
    """
    if quantization not in QUANTIZATION_MODES:
        raise ValueError(f"Unsupported quantization: {quantization}")
    expected = dict(model.named_parameters())
    missing = expected.keys() - reader.files.keys()
    unexpected = reader.files.keys() - expected.keys()
    if missing or unexpected:
        raise ValueError(
            f"Lance checkpoint mismatch: missing={sorted(missing)[:8]}, unexpected={sorted(unexpected)[:8]}"
        )
    for name, parameter in expected.items():
        if reader.shape(name) != tuple(parameter.shape):
            raise ValueError(
                f"Lance checkpoint shape mismatch: {name}: {reader.shape(name)} != {tuple(parameter.shape)}"
            )
    quantized = 0
    for prefix, module in list(model.named_modules()):
        if not prefix:
            continue
        should_quantize = (
            isinstance(module, nn.Linear)
            and quantization != "none"
            and (
                prefix.startswith("language_model.model.layers.")
                or (quantize_vision and prefix.startswith("vit_model."))
            )
        )
        if should_quantize:
            weight = reader.tensor(prefix + ".weight")
            bias = reader.tensor(prefix + ".bias") if module.bias is not None else None
            replacement = QuantizedLinear(weight, bias, mode=quantization).to(device)
            parent_name, _, leaf = prefix.rpartition(".")
            setattr(model.get_submodule(parent_name), leaf, replacement)
            quantized += 1
            del weight, bias
        else:
            for name, _ in module.named_parameters(recurse=False):
                tensor = reader.tensor(prefix + "." + name).to(
                    device=device, dtype=dtype
                )
                setattr(module, name, nn.Parameter(tensor, requires_grad=False))
    if quantization != "none" and quantized == 0:
        raise ValueError(
            "Quantization requested but no transformer linear was converted"
        )
    # Rotary frequencies are non-persistent buffers and are not in checkpoints.
    model.language_model.model.rotary_emb = BagelRotaryEmbedding(
        model.config.llm_config
    ).to(device)
    if model.vit_model is not None:
        from .vision import Qwen2_5_VisionRotaryEmbedding

        vision = model.vit_model.vision_model
        vision.rotary_pos_emb = Qwen2_5_VisionRotaryEmbedding(
            vision.config.hidden_size // vision.config.num_heads // 2
        ).to(device)
    if any(p.is_meta for p in model.parameters()) or any(
        b.is_meta for b in model.buffers()
    ):
        raise RuntimeError("Unmaterialized Lance tensors after checkpoint load")
    model.eval().requires_grad_(False)
    return quantized


def resolve_bundle(model_path, *, variant="image", revision=None):
    if variant not in ("image", "video"):
        raise ValueError("variant must be image or video")
    ckpt_name = "Lance_3B_Video" if variant == "video" else "Lance_3B"
    root = Path(model_path).expanduser()
    if not root.exists():
        from huggingface_hub import snapshot_download

        root = Path(
            snapshot_download(
                repo_id=str(model_path),
                revision=revision,
                allow_patterns=[
                    ckpt_name + "/*",
                    "Qwen2.5-VL-ViT/*",
                    "Wan2.2_VAE.pth",
                    "LICENSE*",
                    "README*",
                ],
            )
        )
    if root.name in ("Lance_3B", "Lance_3B_Video"):
        if root.name != ckpt_name:
            raise ValueError(f"Requested {variant} but checkpoint path is {root.name}")
        root = root.parent
    ckpt = root / ckpt_name
    for required in (
        ckpt / "llm_config.json",
        root / "Qwen2.5-VL-ViT" / "config.json",
        root / "Wan2.2_VAE.pth",
    ):
        if not required.is_file():
            raise FileNotFoundError(f"Incomplete Lance bundle: {required}")
    return root, ckpt


class BundleReader:
    """Original transformer keys plus the authoritative separate ViT overlay."""

    def __init__(self, ckpt, vit_path):
        main, vit = CheckpointReader(ckpt), CheckpointReader(vit_path)
        self.sources = {
            k: (main, k) for k in main.files if not k.startswith("vit_model.")
        }
        for key in vit.files:
            self.sources["vit_model.vision_model." + key] = (vit, key)
        self.files = dict.fromkeys(self.sources)

    def shape(self, key):
        source, original = self.sources[key]
        return source.shape(original)

    def tensor(self, key):
        source, original = self.sources[key]
        return source.tensor(original)
