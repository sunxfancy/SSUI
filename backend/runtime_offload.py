"""Shared placement policy for extension model loaders and independent runners."""
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
import torch

from backend.resource_monitor import GiB, placement, snapshot
from backend.disk_offload import confirm_disk_offload, disk_back_model

_WEIGHT_SUFFIXES = {'.safetensors', '.pt', '.pth', '.bin', '.ckpt'}


def weight_size(paths):
    """Conservative on-disk estimate; deduplicate shards and exclude tokenizer/config files."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    files = set()
    for value in paths:
        path = Path(value)
        if path.is_dir():
            files.update(p.resolve() for p in path.rglob('*') if p.suffix in _WEIGHT_SUFFIXES and p.is_file())
        elif path.is_file() and path.suffix in _WEIGHT_SUFFIXES:
            files.add(path.resolve())
    return sum(p.stat().st_size for p in files)


@dataclass
class LoadPlan:
    mode: str
    device: str
    estimated_bytes: int


def plan_load(label, paths=(), device='cuda', requested=None, estimated_bytes=None):
    """Ask before CPU staging starts. A request authorizes only this load invocation."""
    size = weight_size(paths) if estimated_bytes is None else estimated_bytes
    if size <= 0:
        raise MemoryError(f'{label}: 无法估算模型权重大小，已停止自动加载。')
    target = torch.device(device)
    resources = snapshot()
    index = target.index if target.index is not None else (torch.cuda.current_device() if target.type == 'cuda' and torch.cuda.is_available() else 0)
    mode = placement(size, resources, device_index=index)
    if requested == 'disk' or mode == 'disk_confirmation':
        confirm_disk_offload(label, size)
        mode = 'disk_offload'
    elif requested == 'cpu' or target.type != 'cuda':
        mode = 'cpu_offload'
    return LoadPlan(mode, str(target), size)


def configure_model(model, plan):
    """Use Accelerate layer hooks; keep the execution device separate from meta weights.

    Disk mode supplies mmap-backed CPU tensors to the same hooks. Offload weights are
    never moved en masse by pipeline stage transitions. Custom tensor subclasses are
    rejected before hooks are installed: silently dequantizing them is unsafe.
    """
    if getattr(model, '_ssui_residency', None) is not None:
        return model
    if plan.mode == 'device':
        model.to(plan.device)
        return model
    if any(type(p) is not torch.nn.Parameter for p in model.parameters()):
        raise MemoryError('该模型的自定义量化权重不支持自动 offload，请使用框架原生 offload。')
    from accelerate import cpu_offload
    model.cpu()
    backing = None
    try:
        size = sum(t.numel() * t.element_size() for t in model.state_dict().values())
        if plan.mode == 'disk_offload':
            backing = disk_back_model(model, size)
        # Some attention implementations read a child's weights directly.
        preload = ['MultiheadAttention']
        cpu_offload(model, execution_device=torch.device(plan.device), offload_buffers=False,
                    state_dict=model.state_dict(), preload_module_classes=preload)
        # Accelerate's forward wrapper does not run post_forward after an exception.
        # PyTorch always_call hooks release the failing layer and its ancestors.
        handles = []
        def release_on_failure(module, args, output):
            if output is None and hasattr(module, '_hf_hook'):
                module._hf_hook.post_forward(module, None)
        for module in model.modules():
            if hasattr(module, '_hf_hook'):
                handles.append(module.register_forward_hook(release_on_failure, always_call=True))
        model._ssui_failure_hooks = handles
        model._ssui_plan = plan
        model._ssui_execution_device = torch.device(plan.device)
        model._ssui_residency = plan.mode
        model._ssui_disk_backing = backing
    except Exception:
        # Remove partially installed hooks and restore CPU weights before cleaning files.
        from accelerate.hooks import remove_hook_from_module
        remove_hook_from_module(model, recurse=True)
        if backing is not None:
            backing.cleanup()
        raise
    return model


def is_managed(model):
    return getattr(model, '_ssui_residency', None) in ('cpu_offload', 'disk_offload')


def remote_weight_size(repo_id, prefixes=()):
    """Read Hub file metadata without downloading the checkpoint to RAM."""
    local = Path(repo_id)
    if local.exists():
        return weight_size(local)
    from huggingface_hub import HfApi
    info = HfApi().model_info(repo_id, files_metadata=True)
    files = [f for f in info.siblings if Path(f.rfilename).suffix in _WEIGHT_SUFFIXES
             and (not prefixes or any(f.rfilename.startswith(p + '/') for p in prefixes))]
    if not files or any(f.size is None for f in files):
        raise MemoryError(f'{repo_id}: 无法读取权重大小，已停止自动加载。')
    return sum(f.size for f in files)


def materialize_for_update(method):
    """Temporarily restore managed weights for existing DiffSynth LoRA editors."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        from accelerate.hooks import remove_hook_from_module
        managed = [(m, m._ssui_plan, getattr(m, '_ssui_disk_backing', None))
                   for m in self.model if is_managed(m) and hasattr(m, "_ssui_plan")]
        for model, plan, backing in managed:
            for handle in model._ssui_failure_hooks:
                handle.remove()
            remove_hook_from_module(model, recurse=True)
            model._ssui_residency = None
        try:
            return method(self, *args, **kwargs)
        finally:
            for model, plan, backing in managed:
                configure_model(model, plan)
                if backing is not None:
                    backing.cleanup()
    return wrapped


def configure_pending(model, device, force_cpu=False):
    """Finalize after LoRA/quantization; checkpoint loaders only stage on CPU."""
    pending = getattr(model, '_ssui_load_plan', None)
    if pending is None or is_managed(model):
        return is_managed(model)
    from dataclasses import replace
    plan = replace(pending, device=str(device))
    if force_cpu and plan.mode == 'device':
        plan = replace(plan, mode='cpu_offload')
    if any('float8' in str(p.dtype) for p in model.parameters()):
        if plan.mode == 'disk_offload':
            raise MemoryError('FP8 存储使用框架原生精度转换；自动磁盘卸载请改用 none/int8。')
        del model._ssui_load_plan
        return False
    if getattr(model, '_ssui_int8', False):
        # Native packed Linear stores weights in buffers and exposes a computed
        # weight property. Keep its native method/generator residency wrapper.
        from ssui.model_memory import offload_component
        model.cpu()
        if plan.mode != 'device':
            backing = disk_back_model(model, sum(t.numel()*t.element_size() for t in model.state_dict().values())) if plan.mode == 'disk_offload' else None
            offload_component(model, device, cpu_state=model.state_dict() if backing else None)
            model._ssui_disk_backing = backing
            model._ssui_residency = plan.mode
            model._ssui_execution_device = torch.device(device)
        else:
            model.to(device)
    else:
        configure_model(model, plan)
    del model._ssui_load_plan
    return is_managed(model)


def finalize_pipeline(pipe):
    for module in pipe.children():
        configure_pending(module, pipe.device)
    return any(is_managed(m) for m in pipe.children())
