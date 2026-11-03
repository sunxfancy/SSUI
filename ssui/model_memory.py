"""Opt-in inference memory policy shared by local model loaders.

INT8 quantizes Linear weights only (not activations, convolutions or embeddings).
CPU offload moves whole components at inference boundaries, including generators.
"""
from contextlib import contextmanager
from dataclasses import dataclass, InitVar
from functools import wraps
import inspect
import threading


@dataclass(frozen=True)
class ModelMemoryOptions:
    quantization: str = "none"
    cpu_offload: bool = False
    allow_fp8: InitVar[bool] = False

    def __post_init__(self, allow_fp8):
        if self.quantization not in (("none", "int8", "fp8") if allow_fp8 else ("none", "int8")):
            raise ValueError("quantization must be 'none', 'int8' or 'fp8'")
        if self.quantization == "fp8" and not self.cpu_offload:
            raise ValueError("FP8 requires the existing CPU offload/casting path; use none or int8 when disabling offload")
        if not isinstance(self.cpu_offload, bool):
            raise TypeError("cpu_offload must be a bool")

    def quantize(self, model):
        """Quantize a newly loaded component, before caching or moving to GPU."""
        if self.quantization != "int8":
            return model
        from ssui.native_quantization import quantize_model_int8
        return quantize_model_int8(model)

    def configure(self, modules, device="cuda"):
        """Configure independently callable components, deduplicating aliases."""
        import torch
        seen = set()
        for module in modules:
            if not isinstance(module, torch.nn.Module) or id(module) in seen:
                continue
            seen.add(id(module))
            self.quantize(module)
            if self.cpu_offload:
                offload_component(module, device)
            else:
                module.to(device)


def offload_component(module, device="cuda"):
    """Keep a component on CPU between calls; release even on errors/close.

    Wrap custom inference methods as well as forward: several vendored models
    bypass forward entirely. Nested calls share a residency scope. A component
    must not be moved externally after configuring this policy.
    """
    if getattr(module, "_ssui_cpu_offload", False):
        return
    lock = threading.RLock()
    depth = 0

    @contextmanager
    def resident():
        nonlocal depth
        with lock:
            outer = depth == 0
            try:
                if outer:
                    module.to(device)
                depth += 1
                try:
                    yield
                finally:
                    depth -= 1
            finally:
                if outer:
                    module.to("cpu")

    def move_inputs(args, kwargs):
        import torch
        from torch.utils._pytree import tree_map
        tensor = next(module.parameters(), None)
        if tensor is None:
            tensor = next(module.buffers(), None)
        if tensor is None:
            return args, kwargs
        return tree_map(lambda value: value.to(tensor.device) if isinstance(value, torch.Tensor) else value, (args, kwargs))

    def wrap(method):
        if inspect.isgeneratorfunction(inspect.unwrap(method)):
            @wraps(method)
            def streamed(*args, **kwargs):
                with resident():
                    args, kwargs = move_inputs(args, kwargs)
                    yield from method(*args, **kwargs)
            return streamed
        @wraps(method)
        def called(*args, **kwargs):
            with resident():
                args, kwargs = move_inputs(args, kwargs)
                return method(*args, **kwargs)
        return called

    for name in (
        "forward", "inference", "inference_bistream", "chat", "generate",
        "encode", "decode", "encode_video", "decode_video",
    ):
        method = getattr(module, name, None)
        if callable(method):
            setattr(module, name, wrap(method))
    module.to("cpu")
    module._ssui_cpu_offload = True


def configure_diffsynth_manager(manager, options, device="cuda", *, quantize=True):
    # DiffSynth's pipeline device describes computation, not weight residency.
    if quantize and options.quantization == "int8":
        for model in manager.model:
            options.quantize(model)
    manager.to("cpu" if options.cpu_offload else device)
    manager.device = str(device)
    manager.memory_options = options
    return manager


def model_memory(config, *, cpu_offload_default=False, allow_fp8=False):
    """Expose loader options as ordinary workflow controls, including prepare."""
    from ssui.controller import Select, Switch
    for name, controller, default in (
        ("quantization", Select(*(("none", "fp8", "int8") if allow_fp8 else ("none", "int8"))), "none"),
        ("cpu_offload", Switch(), cpu_offload_default),
    ):
        if name not in config:
            config.register(name, {
                "controller": controller.__class__.__name__,
                "args": controller,
                "default": default,
            })
    if config.is_prepare():
        return {"quantization": "none", "cpu_offload": cpu_offload_default}
    options = ModelMemoryOptions(config["quantization"], config["cpu_offload"], allow_fp8=allow_fp8)
    return {"quantization": options.quantization, "cpu_offload": options.cpu_offload}


def run_pipeline(pipe, *args, **kwargs):
    """Release stage-managed weights after success or failure."""
    try:
        return pipe(*args, **kwargs)
    finally:
        if getattr(pipe, "cpu_offload", False) or getattr(pipe, "vram_management_enabled", False):
            pipe.load_models_to_device([])
