"""Preserve TRELLIS spconv checkpoint keys/layout on the FlexGEMM backend."""
import torch.nn as nn
from pixal3d.modules.sparse.conv import SparseConv3d as FlexConv


class SparseConv3d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, dilation=1,
                 padding=None, bias=True, indice_key=None):
        super().__init__()
        if stride != 1 or padding is not None:
            raise ValueError("TRELLIS FlexGEMM currently supports submanifold convolutions only")
        self.conv = FlexConv(in_channels, out_channels, kernel_size, stride=stride,
                             dilation=dilation, padding=padding, bias=bias, indice_key=indice_key)

    def forward(self, tensor):
        return self.conv(tensor)


class SparseInverseConv3d(nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        raise ValueError("Inverse convolutions are not part of the supported TRELLIS inference decoders")
