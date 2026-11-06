"""Convert a local tensor-only checkpoint in a separate PyTorch >= 2.6 environment.

Usage: python scripts/convert_checkpoint_safetensors.py path/pytorch_model.bin
The inference environment can retain its CUDA/native-extension-compatible Torch.
"""
import argparse
from pathlib import Path


def main():
    import torch
    from safetensors.torch import save_file

    if tuple(int(part) for part in torch.__version__.split('+')[0].split('.')[:2]) < (2, 6):
        raise RuntimeError("Conversion requires PyTorch >= 2.6; use a separate CPU environment")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    output = args.checkpoint.with_name("model.safetensors")
    if output.exists():
        raise FileExistsError(output)
    tensors = torch.load(args.checkpoint, map_location="cpu", weights_only=True, mmap=True)
    if not isinstance(tensors, dict) or not all(isinstance(v, torch.Tensor) for v in tensors.values()):
        raise ValueError("Expected a flat tensor state dict")
    temporary = output.with_suffix('.safetensors.partial')
    try:
        save_file(tensors, str(temporary), metadata={"format": "pt"})
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(output)


if __name__ == "__main__":
    main()
