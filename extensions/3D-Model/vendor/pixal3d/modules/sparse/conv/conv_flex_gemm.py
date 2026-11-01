import math
import sys
import torch
import torch.nn as nn
from .. import SparseTensor
from . import config
import flex_gemm
from flex_gemm.ops.spconv import sparse_submanifold_conv3d


def chunked_explicit_conv(feats, neighbor_map, weight, bias, max_buffer_bytes=64 * 1024 * 1024):
    """Inference im2col with bounded temporary storage, preserving kernel order."""
    channels_out, *kernel, channels_in = weight.shape
    volume = math.prod(kernel)
    rows = max(1, min(65536, max_buffer_bytes // (volume * channels_in * feats.element_size())))
    output = feats.new_empty((len(feats), channels_out))
    matrix = weight.reshape(channels_out, -1).t()
    for start in range(0, len(feats), rows):
        end = min(start + rows, len(feats))
        indices = neighbor_map[start:end].reshape(-1).long()
        valid = (indices >= 0) & (indices < len(feats))
        columns = feats.new_zeros(((end - start) * volume, channels_in))
        columns[valid] = feats[indices[valid]]
        columns = columns.reshape(end - start, -1)
        output[start:end] = torch.mm(columns, matrix) if bias is None else torch.addmm(bias, columns, matrix)
    return output


def sparse_conv3d_init(self, in_channels, out_channels, kernel_size, stride=1, dilation=1, padding=None, bias=True, indice_key=None):
    assert stride == 1 and (padding is None), 'Currently flex_gemm implementation only support submanifold sparse convolution (stride=1, padding=None)'
    
    self.in_channels = in_channels
    self.out_channels = out_channels
    self.kernel_size = tuple(kernel_size) if isinstance(kernel_size, (list, tuple)) else (kernel_size, ) * 3
    self.stride = tuple(stride) if isinstance(stride, (list, tuple)) else (stride, ) * 3
    self.dilation = tuple(dilation) if isinstance(dilation, (list, tuple)) else (dilation, ) * 3

    self.weight = nn.Parameter(torch.empty((out_channels, in_channels, *self.kernel_size)))
    if bias:
        self.bias = nn.Parameter(torch.empty(out_channels))
    else:
        self.register_parameter("bias", None)

    # initialize parameters
    torch.nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
    if self.bias is not None:
        fan_in, _ = torch.nn.init._calculate_fan_in_and_fan_out(self.weight)
        if fan_in != 0:
            bound = 1 / math.sqrt(fan_in)
            torch.nn.init.uniform_(self.bias, -bound, bound)

    # Permute weight (Co, Ci, Kd, Kh, Kw) -> (Co, Kd, Kh, Kw, Ci)
    self.weight = nn.Parameter(self.weight.permute(0, 2, 3, 4, 1).contiguous())


def sparse_conv3d_forward(self, x: SparseTensor) -> SparseTensor:
    flex_gemm.ops.spconv.set_algorithm(config.FLEX_GEMM_ALGO)
    flex_gemm.ops.spconv.set_hashmap_ratio(config.FLEX_GEMM_HASHMAP_RATIO)

    # check if neighbor map is already computed
    Co, Kd, Kh, Kw, Ci = self.weight.shape
    neighbor_cache_key = f'SubMConv3d_neighbor_cache_{Kw}x{Kh}x{Kd}_dilation{self.dilation}'
    neighbor_cache = x.get_spatial_cache(neighbor_cache_key)
    
    if (sys.platform == "win32" and torch.version.hip and
            config.FLEX_GEMM_ALGO == "explicit_gemm" and not torch.is_grad_enabled()):
        from flex_gemm.ops.spconv.submanifold_conv3d import SubMConv3dFunction
        neighbor_cache_ = neighbor_cache
        if neighbor_cache_ is None:
            neighbor_cache_ = SubMConv3dFunction._compute_neighbor_cache(
                x.coords, torch.Size([*x.shape, *x.spatial_shape]),
                (Kd, Kh, Kw), self.dilation, False,
            )
        out = chunked_explicit_conv(x.feats, neighbor_cache_["neighbor_map"], self.weight, self.bias)
    else:
        out, neighbor_cache_ = sparse_submanifold_conv3d(
            x.feats, x.coords, torch.Size([*x.shape, *x.spatial_shape]),
            self.weight, self.bias, neighbor_cache, self.dilation,
        )
    
    if neighbor_cache is None:
        x.register_spatial_cache(neighbor_cache_key, neighbor_cache_)
    
    out = x.replace(out)
    return out


def sparse_inverse_conv3d_init(self, *args, **kwargs):
    raise NotImplementedError('SparseInverseConv3d with flex_gemm is not implemented yet')


def sparse_inverse_conv3d_forward(self, x: SparseTensor) -> SparseTensor:
    raise NotImplementedError('SparseInverseConv3d with flex_gemm is not implemented yet')
