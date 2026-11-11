"""Shared inference LoRA validation; adapters are applied before offload/quantization."""
import math
from pathlib import Path


def validate_lora(path: str = "", weight: float = 1.0) -> bool:
    if not math.isfinite(weight):
        raise ValueError("LoRA weight must be finite")
    if not path or weight == 0:
        return False
    if not Path(path).is_file():
        raise FileNotFoundError(f"LoRA checkpoint not found: {path}")
    return True


def apply_manager_lora(manager, path="", weight=1.0):
    if not validate_lora(path, weight):
        return
    from diffsynth.models.utils import load_state_dict
    from diffsynth.models.lora import get_lora_loaders, GeneralLoRAFromPeft
    state = load_state_dict(path)
    matches = []
    for model in manager.model:
        for loader in get_lora_loaders():
            # The legacy generic matcher accepts an empty adapter as a match.
            if isinstance(loader, GeneralLoRAFromPeft) and not loader.get_name_dict(state):
                continue
            result = loader.match(model, state)
            if result is not None:
                matches.append((loader, model, result))
                break
    if not matches:
        raise ValueError(f"LoRA has no compatible target layers: {path}")
    for loader, model, (prefix, resource) in matches:
        if isinstance(loader, GeneralLoRAFromPeft):
            apply_dit_lora(model, path, weight)
        else:
            loader.load(model, state, prefix, alpha=weight, model_resource=resource)


def apply_dit_lora(module, path="", weight=1.0):
    if not validate_lora(path, weight):
        return
    import torch
    from diffsynth.models.utils import load_state_dict
    from diffsynth.lora import GeneralLoRALoader
    state = load_state_dict(path)
    # Layer-by-layer FP32 arithmetic also handles FP8 storage on CPU. The loader
    # copies each result into the original parameter dtype before offload wraps it.
    loader = GeneralLoRALoader(device="cpu", torch_dtype=torch.float32)
    targets = loader.get_name_dict(state)
    modules = dict(module.named_modules())
    if not targets or any(name not in modules for name in targets):
        raise ValueError(f"LoRA target layers do not match this model: {path}")
    # Validate every pair before modifying the model.
    for name, (up, down) in targets.items():
        if down not in state:
            raise ValueError(f"Missing LoRA down tensor for {name}")
        a, b = state[up], state[down]
        target = modules[name].weight
        if a.ndim == b.ndim == 4:
            if a.shape[2:] != (1, 1) or b.shape[2:] != (1, 1):
                raise ValueError("Only 1x1 convolution LoRA is supported")
        elif a.ndim != 2 or b.ndim != 2:
            raise ValueError("Unsupported LoRA tensor dimensions")
        expected = (a.shape[0], b.shape[1], *a.shape[2:])
        if a.shape[1] != b.shape[0] or expected != tuple(target.shape):
            raise ValueError(f"LoRA shape mismatch for {name}")
    loader.load(module, state, alpha=weight)


def apply_diffusers_lora(pipeline, path="", weight=1.0):
    if not validate_lora(path, weight):
        return
    checkpoint = Path(path)
    pipeline.load_lora_weights(str(checkpoint.parent), weight_name=checkpoint.name,
                               adapter_name="ssui")
    pipeline.set_adapters(["ssui"], adapter_weights=[weight])
