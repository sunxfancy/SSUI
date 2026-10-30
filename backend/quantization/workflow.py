"""Opt-in inference quantization shared by the 3D and video adapters.

FP8 is a storage cast, not FP8 activation computation. INT8 uses TorchAO's
per-channel weight-only recipe and keeps the original Linear forward methods
(including Trellis SparseLinear). Optional dependencies are loaded on demand.
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
    try:
        from importlib import import_module
        from inspect import signature

        ao = import_module("torchao.quantization")
        quantize_ = ao.quantize_
        config = getattr(ao, "Int8WeightOnlyConfig", None)
        if config is None:
            # TorchAO releases compatible with the repository's PyTorch 2.4
            # expose the same recipe through a function instead of a config.
            recipe = ao.int8_weight_only()
        elif "version" in signature(config).parameters:
            # v1 retains FP32 scales when restoring the public weight dtype.
            # v2's generic Tensor.to currently ignores dtype changes, which
            # breaks models that derive activation dtype from Linear.weight.
            recipe = config(version=1)
        else:
            recipe = config()
    except (ImportError, AttributeError, RuntimeError, OSError, TypeError) as exc:
        raise RuntimeError(
            "INT8 requires an optional torchao installation compatible with PyTorch "
            "in the model's Python environment. Install torchao there, or select 'none'."
        ) from exc

    def apply(model):
        import torch

        original_dtypes = {}

        def linear_filter(module, name):
            if isinstance(module, torch.nn.Linear) and type(module.weight) is torch.nn.Parameter:
                original_dtypes[module] = module.weight.dtype
                # Compute quantization scales in FP32 one layer at a time.
                # BF16 scale rounding can otherwise saturate INT8 endpoints.
                module.weight = torch.nn.Parameter(module.weight.float(), requires_grad=False)
                return True
            return False

        # TorchAO changes Linear weights in place; it must not replace custom
        # SparseLinear.forward, nor quantize geometry/latent decoders.
        quantize_(model, recipe, filter_fn=linear_filter)
        for module, dtype in original_dtypes.items():
            module.weight = torch.nn.Parameter(module.weight.to(dtype=dtype), requires_grad=False)
        return model

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
