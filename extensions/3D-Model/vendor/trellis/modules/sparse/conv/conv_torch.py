"""Submanifold sparse convolution: cached GPU topology and feature arithmetic.

Weights retain spconv's [out, kx, ky, kz, in] checkpoint layout. No dense
voxel grid or CPU copy of feature/weight tensors is used in forward.
"""
import itertools
import math
import numpy as np
import torch
from torch import nn
from .. import SparseTensor
from ..topology import neighbor_pairs


def triple(value):
    return tuple(value) if isinstance(value, (tuple, list)) else (value,) * 3


class SparseConv3d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, dilation=1, padding=None, bias=True, indice_key=None):
        super().__init__()
        self.kernel = triple(kernel_size)
        self.dilation = triple(dilation)
        if triple(stride) != (1, 1, 1) or padding is not None or any(k % 2 == 0 for k in self.kernel):
            raise NotImplementedError('Torch sparse backend currently supports odd-kernel submanifold convolutions only')
        self.conv = nn.Module()
        self.conv.weight = nn.Parameter(torch.empty(out_channels, *self.kernel, in_channels))
        self.conv.bias = nn.Parameter(torch.empty(out_channels)) if bias else None
        nn.init.uniform_(self.conv.weight, -1/math.sqrt(in_channels*math.prod(self.kernel)), 1/math.sqrt(in_channels*math.prod(self.kernel)))
        if bias:
            nn.init.zeros_(self.conv.bias)

    def _pairs(self, x):
        key = ('torch_subm', self.kernel, self.dilation, x.coords.data_ptr(), (0 if x.coords.is_inference() else x.coords._version), str(x.device))
        cached = x.get_spatial_cache(key)
        if cached is not None and cached[0] is x.coords:
            return cached[1]
        if x.device.type == 'mps':
            pairs = neighbor_pairs(x.coords, self.kernel, self.dilation)
        else:
            coords = x.coords.detach().cpu().numpy().astype(np.int64)
            dims = coords.max(axis=0) + 1
            if (coords < 0).any():
                raise ValueError('Sparse convolution coordinates must be nonnegative')
            keys = np.ravel_multi_index(coords.T, dims)
            order = np.argsort(keys)
            sorted_keys = keys[order]
            if len(np.unique(keys)) != len(keys):
                raise ValueError('Sparse coordinates must be unique')
            pairs = []
            for offset in itertools.product(*(range(k) for k in self.kernel)):
                neighbor = coords.copy()
                neighbor[:, 1:] += (np.array(offset) - np.array(self.kernel)//2) * self.dilation
                valid = ((neighbor >= 0) & (neighbor < dims)).all(axis=1)
                dst = np.flatnonzero(valid)
                wanted = np.ravel_multi_index(neighbor[valid].T, dims)
                pos = np.searchsorted(sorted_keys, wanted)
                match = (pos < len(keys)) & (sorted_keys[np.minimum(pos, len(keys)-1)] == wanted)
                src = order[pos[match]]
                pairs.append((torch.as_tensor(src.copy(), device=x.device), torch.as_tensor(dst[match].copy(), device=x.device)))
        # Keep the coordinate tensor alive so its allocator address cannot be reused
        # for a different topology while this cache entry remains valid.
        x.register_spatial_cache(key, (x.coords, pairs))
        return pairs

    def forward(self, x):
        out = x.feats.new_zeros((len(x.feats), self.conv.weight.shape[0]))
        if len(x.feats):
            weights = self.conv.weight.flatten(1, 3)
            for index, (src, dst) in enumerate(self._pairs(x)):
                if src.numel():
                    out.index_add_(0, dst, x.feats[src] @ weights[:, index].T)
        if self.conv.bias is not None:
            out = out + self.conv.bias
        return x.replace(out)


class SparseInverseConv3d(nn.Module):
    def __init__(self, *args, **kwargs):
        super().__init__()
        raise NotImplementedError('Inverse sparse convolution requires a saved strided coordinate map; not yet supported by torch backend')
