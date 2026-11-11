# SPDX-License-Identifier: Apache-2.0
"""Portable weight-only NF4 / per-output-channel INT8.

Weights remain packed between calls and are dequantized one projection at a
time for F.linear. This reduces persistent weight memory, not activation/KV
memory; it is not a fused low-bit GEMM and does not promise a speedup. Works
without bitsandbytes on CPU, CUDA, ROCm and MPS where PyTorch supports the ops.
"""

import torch
from torch import nn
from torch.nn import functional as F

NF4_VALUES = (
    -1.0,
    -0.6961928009986877,
    -0.5250730514526367,
    -0.39491748809814453,
    -0.28444138169288635,
    -0.18477343022823334,
    -0.09105003625154495,
    0.0,
    0.07958029955625534,
    0.16093020141124725,
    0.24611230194568634,
    0.33791524171829224,
    0.44070982933044434,
    0.5626170039176941,
    0.7229568362236023,
    1.0,
)
QUANTIZATION_MODES = ("none", "int8", "nf4")


class QuantizedLinear(nn.Module):
    """Inference-only packed linear; never retains a floating weight copy."""

    def __init__(self, weight, bias=None, *, mode="nf4", block_size=64):
        super().__init__()
        if mode not in ("int8", "nf4"):
            raise ValueError(f"Unsupported quantization: {mode}")
        if weight.ndim != 2 or not weight.is_floating_point():
            raise ValueError("Quantization requires a floating-point 2-D weight")
        if block_size <= 0 or block_size % 2:
            raise ValueError("NF4 block size must be a positive even number")
        self.out_features, self.in_features = weight.shape
        self.mode, self.block_size = mode, block_size
        self.register_buffer("bias", None if bias is None else bias.detach().clone())
        # Quantize on CPU in bounded chunks; no full BF16 GPU allocation.
        # Always keep scales in fp32 so .to(device) cannot lose zero/large scales.
        chunks, scales = [], []
        if mode == "int8":
            rows_per_chunk = max(1, 1048576 // self.in_features)
            for rows in weight.detach().split(rows_per_chunk):
                rows = rows.float()
                scale = (
                    rows.abs()
                    .amax(dim=1, keepdim=True)
                    .clamp_min(torch.finfo(torch.float32).tiny)
                    / 127
                )
                chunks.append((rows / scale).round().clamp(-127, 127).to(torch.int8))
                scales.append(scale)
        else:
            codebook = torch.tensor(NF4_VALUES, device=weight.device)
            boundaries = (codebook[:-1] + codebook[1:]) / 2
            for block in weight.detach().reshape(-1).split(block_size * 16384):
                block = F.pad(
                    block.float(), (0, (-block.numel()) % block_size)
                ).reshape(-1, block_size)
                scale = (
                    block.abs()
                    .amax(dim=1, keepdim=True)
                    .clamp_min(torch.finfo(torch.float32).tiny)
                )
                codes = (
                    torch.bucketize((block / scale).contiguous(), boundaries)
                    .to(torch.uint8)
                    .flatten()
                )
                chunks.append((codes[0::2] << 4) | codes[1::2])
                scales.append(scale)
        self.register_buffer("qweight", torch.cat(chunks))
        self.register_buffer("scales", torch.cat(scales))

    def dequantize(self, dtype=torch.float32):
        if self.mode == "int8":
            return (self.qweight.to(dtype) * self.scales.to(dtype)).reshape(
                self.out_features, self.in_features
            )
        # Interleave high / low nibble in the same order as packing.
        codes = (
            torch.stack((self.qweight >> 4, self.qweight & 15), dim=-1).flatten().long()
        )
        table = torch.tensor(NF4_VALUES, device=self.qweight.device, dtype=dtype)
        weight = table[codes].reshape(-1, self.block_size) * self.scales.to(dtype)
        return weight.flatten()[: self.out_features * self.in_features].reshape(
            self.out_features, self.in_features
        )

    def forward(self, x):
        bias = None if self.bias is None else self.bias.to(x.dtype)
        return F.linear(x, self.dequantize(x.dtype), bias)

    def extra_repr(self):
        return f"in_features={self.in_features}, out_features={self.out_features}, mode={self.mode}"


def storage_bytes(module):
    return sum(
        t.numel() * t.element_size() for t in (*module.parameters(), *module.buffers())
    )


def quantize_linear_layers(module, mode="nf4"):
    """In-place conversion for already materialized modules (e.g. tiny tests)."""
    if mode not in QUANTIZATION_MODES:
        raise ValueError(f"Unsupported quantization: {mode}")
    if mode == "none":
        return module
    for name, child in list(module.named_children()):
        if isinstance(child, nn.Linear):
            setattr(module, name, QuantizedLinear(child.weight, child.bias, mode=mode))
        else:
            quantize_linear_layers(child, mode)
    return module
