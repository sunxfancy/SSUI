"""Opt-in inference quantization shared by the 3D and video adapters.

FP8 is a storage cast, not FP8 activation computation. INT8 uses SSUI native per-channel weight-only storage. Numerical code is
loaded on demand, so workflow preparation does not require Torch.
"""


def validate_quantization(mode, supported):
    if mode not in supported:
        raise ValueError(f"Unsupported quantization {mode!r}; choose one of {supported}")
    return mode


def fp8_storage_dtype(mode, default_dtype, device=None):
    validate_quantization(mode, ("none", "fp8"))
    if mode == "none":
        return default_dtype
    import torch

    if device is not None and torch.device(device).type == "mps":
        raise RuntimeError("FP8 storage is not supported on MPS; select 'none'")

    dtype = getattr(torch, "float8_e4m3fn", None)
    if dtype is None:
        raise RuntimeError("FP8 storage requires a PyTorch build with float8_e4m3fn support")
    return dtype


def int8_quantizer(mode):
    """Preflight before downloading weights; return an in-place model transform."""
    validate_quantization(mode, ("none", "int8"))
    if mode == "none":
        return lambda model: model
    from ssui.native_quantization import quantize_model_int8
    def apply(model):
        import torch
        sparse_types = tuple({type(layer) for layer in model.modules()
                              if isinstance(layer, torch.nn.Linear) and type(layer).__name__ == 'SparseLinear'})
        return quantize_model_int8(model, linear_types=sparse_types)
    return apply


def load_dit_with_storage_dtype(manager, paths, *, quantization, torch_dtype, device):
    """Legacy DiffSynth loaders: only the first path (DiT) gets FP8 storage."""
    storage_dtype = fp8_storage_dtype(quantization, torch_dtype)
    if quantization == "none":
        manager.load_models(paths, torch_dtype=torch_dtype, device=device)
    else:
        manager.load_models(paths[:1], torch_dtype=storage_dtype, device=device)
        manager.load_models(paths[1:], torch_dtype=torch_dtype, device=device)


def quantize_manager_components(manager, quantizer, names):
    """Quantize explicitly selected components, leaving VAE/geometry untouched."""
    for name in names:
        model = manager.fetch_model(name)
        if model is None:
            raise RuntimeError(f"Cannot quantize missing model component {name!r}")
        quantizer(model)
