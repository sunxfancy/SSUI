from typing import Dict, Literal, Optional, Union
from dataclasses import dataclass
import torch

@dataclass
class TorchDeviceConfig:
    device: str = "auto"
    precision: str = "auto"


class TorchDevice:
    """Abstraction layer for torch devices."""

    CPU_DEVICE = torch.device("cpu")
    CUDA_DEVICE = torch.device("cuda")
    MPS_DEVICE = torch.device("mps")

    TorchPrecisionNames = Literal["float32", "float16", "bfloat16"]

    NAME_TO_PRECISION: Dict[TorchPrecisionNames, torch.dtype] = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }
    PRECISION_TO_NAME: Dict[torch.dtype, TorchPrecisionNames] = {v: k for k, v in NAME_TO_PRECISION.items()}
    config = TorchDeviceConfig()

    @classmethod
    def choose_torch_device(cls) -> torch.device:
        """Return the torch.device to use for accelerated inference."""
        if TorchDevice.config.device != "auto":
            device = torch.device(TorchDevice.config.device)
        elif torch.cuda.is_available():
            device = TorchDevice.CUDA_DEVICE
        elif torch.backends.mps.is_available():
            device = TorchDevice.MPS_DEVICE
        else:
            device = TorchDevice.CPU_DEVICE
        return cls.normalize(device)

    @classmethod
    def choose_torch_dtype(cls, device: Optional[torch.device] = None) -> torch.dtype:
        """Return the precision to use for accelerated inference."""
        device = device or cls.choose_torch_device()
        if device.type == "cuda" and torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(device)
            if "GeForce GTX 1660" in device_name or "GeForce GTX 1650" in device_name:
                # These GPUs have limited support for float16
                return cls._to_dtype("float32")
            elif TorchDevice.config.precision == "auto":
                # Default to float16 for CUDA devices
                return cls._to_dtype("float16")
            else:
                # Use the user-defined precision
                return cls._to_dtype(TorchDevice.config.precision)

        elif device.type == "mps" and torch.backends.mps.is_available():
            if TorchDevice.config.precision == "auto":
                # Default to float16 for MPS devices
                return cls._to_dtype("float16")
            else:
                # Use the user-defined precision
                return cls._to_dtype(TorchDevice.config.precision)
        # CPU / safe fallback
        return cls._to_dtype("float32")

    @classmethod
    def get_torch_device_name(cls) -> str:
        """Return the device name for the current torch device."""
        device = cls.choose_torch_device()
        return torch.cuda.get_device_name(device) if device.type == "cuda" else device.type.upper()

    @classmethod
    def normalize(cls, device: Union[str, torch.device]) -> torch.device:
        """Add the device index to CUDA devices."""
        device = torch.device(device)
        if device.index is None and device.type == "cuda" and torch.cuda.is_available():
            device = torch.device(device.type, torch.cuda.current_device())
        return device

    @classmethod
    def empty_cache(cls) -> None:
        """Clear the GPU device cache."""
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    @classmethod
    def _to_dtype(cls, precision_name: TorchPrecisionNames) -> torch.dtype:
        return TorchDevice.NAME_TO_PRECISION[precision_name]
