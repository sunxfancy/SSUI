"""Machine resources and conservative model placement decisions (all sizes are bytes)."""
import psutil

GiB = 2**30


def snapshot():
    ram = psutil.virtual_memory()
    result = {"ram": {"total": ram.total, "available": ram.available,
                      "used": ram.total - ram.available}, "gpus": [], "gpu_error": None}
    try:
        import torch
        if torch.cuda.is_available():
            for index in range(torch.cuda.device_count()):
                free, total = torch.cuda.mem_get_info(index)
                result["gpus"].append({"index": index, "name": torch.cuda.get_device_name(index),
                                       "total": total, "available": free, "used": total - free})
    except Exception as exc:
        result["gpu_error"] = str(exc)
    return result


def placement(weight_bytes, resources, device_index=0, working_bytes=3 * GiB):
    """Reserve runtime headroom; unknown VRAM is never treated as unlimited."""
    if weight_bytes < 0 or working_bytes < 0:
        raise ValueError("Memory estimates must be non-negative")
    reserve = max(GiB, int(resources["ram"]["total"] * .1))
    # This cache retains a CPU copy even when all weights fit on the GPU.
    if weight_bytes + reserve > resources["ram"]["available"]:
        return "disk_confirmation"
    gpu = next((g for g in resources["gpus"] if g["index"] == device_index), None)
    if gpu and weight_bytes + working_bytes <= gpu["available"]:
        return "device"
    return "cpu_offload"
