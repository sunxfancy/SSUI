"""Device-aware memory accounting for inference/offload decisions."""
import psutil
import torch

GIB = 1024 ** 3


def device_memory(device):
    """Return (budget, used) bytes; MPS shares physical RAM with CPU models."""
    device = torch.device(device)
    if device.type == "cuda":
        free, total = torch.cuda.mem_get_info(device)
        return total, total - free
    if device.type == "mps":
        recommended = getattr(torch.mps, "recommended_max_memory", None)
        # Torch 2.4 lacks recommended_max_memory. Leave half the shared memory
        # for CPU-side weights, activations and the rest of the system.
        total = recommended() if recommended is not None else psutil.virtual_memory().total // 2
        return total, torch.mps.driver_allocated_memory()
    if device.type == "cpu":
        memory = psutil.virtual_memory()
        return memory.total, memory.total - memory.available
    raise ValueError(f"Unsupported inference device: {device}")


def empty_device_cache(device):
    device = torch.device(device)
    if device.type == "cuda":
        torch.cuda.empty_cache()
    elif device.type == "mps":
        torch.mps.empty_cache()
