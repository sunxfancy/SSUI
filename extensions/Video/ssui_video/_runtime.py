"""Runtime policy for the Wan nodes."""
import sys
import torch
from backend.util.devices import TorchDevice


def configure_wan_blas(device):
    """Avoid Windows ROCm 7.2 hipBLASLt's native BF16 heuristic crash.

    PyTorch's BLAS preference is process-wide. On ROCm, 'cublas' selects
    regular hipBLAS; this also covers offloaded Linear layers in Wan nodes.
    """
    if (sys.platform == "win32" and torch.device(device).type == "cuda"
            and (torch.version.hip or "").startswith("7.2.")):
        torch.backends.cuda.preferred_blas_library("cublas")


def wan_runtime():
    device = TorchDevice.choose_torch_device()
    configure_wan_blas(device)
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    if device.type == "mps":
        # BF16 needs macOS 14+; FP16 may overflow the UMT5 text encoder.
        supports_bf16 = torch.backends.mps.is_available() and torch.backends.mps.is_macos_or_newer(14, 0)
        if TorchDevice.config.precision == "auto":
            dtype = torch.bfloat16 if supports_bf16 else torch.float32
        elif TorchDevice.config.precision == "bfloat16":
            if not supports_bf16:
                raise ValueError("Wan BF16 on MPS requires macOS 14 or newer")
            dtype = torch.bfloat16
        elif TorchDevice.config.precision == "float32":
            dtype = torch.float32
        else:
            raise ValueError("Wan on MPS supports float32 or bfloat16; float16 can overflow UMT5")
    return {"device": str(device), "torch_dtype": dtype}
