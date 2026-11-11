"""Read local safetensors bundles without executing downloaded Python code."""
import json
from pathlib import Path


def read_config(directory):
    return json.loads((Path(directory) / "config.json").read_text(encoding="utf-8"))


def weight_shards(directory, stem):
    directory = Path(directory).resolve()
    index = directory / f"{stem}.safetensors.index.json"
    if index.is_file():
        mapping = json.loads(index.read_text(encoding="utf-8"))["weight_map"]
        if not mapping or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise ValueError("Invalid safetensors weight map")
        names = sorted(set(mapping.values()))
    else:
        mapping = None
        names = [f"{stem}.safetensors"]
    shards = []
    for name in names:
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or path.suffix != ".safetensors":
            raise ValueError(f"Shard path escapes component directory or is not safetensors: {name}")
        if not path.is_file():
            raise FileNotFoundError(path)
        expected = {k for k, v in mapping.items() if v == name} if mapping is not None else None
        shards.append((path, expected))
    return shards


def text_weight_key(key):
    # Official bundles contain a multimodal Qwen3.5 model. Image generation uses
    # only the language backbone, never visual/LM-head/MTP weights.
    for prefix in ("model.language_model.", "language_model."):
        if key.startswith(prefix):
            return key[len(prefix):]
    if key.startswith(("visual.", "model.visual.", "lm_head.", "mtp.", "model.mtp.")):
        return None
    return key


def load_component(model, directory, stem, dtype, key_transform=None):
    import torch
    from safetensors.torch import load_file

    expected = set(model.state_dict())
    loaded = set()
    for path, shard_keys in weight_shards(directory, stem):
        state = load_file(str(path), device="cpu")
        if shard_keys is not None and set(state) != shard_keys:
            raise ValueError(f"Shard contents do not match index: {path.name}")
        selected = {}
        for key, tensor in state.items():
            target = key_transform(key) if key_transform else key
            if target is None:
                continue
            if target not in expected or target in loaded:
                raise ValueError(f"Unexpected or duplicate weight: {key}")
            selected[target] = tensor.to(dtype) if tensor.is_floating_point() else tensor
            loaded.add(target)
        model.load_state_dict(selected, strict=False, assign=True)
        del selected, state
    if missing := expected - loaded:
        raise ValueError(f"Missing weights in {directory}: {sorted(missing)[:10]}")
    if any(p.device.type == "meta" for p in model.parameters()):
        raise ValueError("Component still contains uninitialized weights")
    return model.eval().requires_grad_(False)
