"""P3-SAM's inference-only SpConv API on source-built Windows ROCm kernels.

This is deliberately not a general spconv/cumm replacement. Sonata only uses
SparseConvTensor and stride-one SubMConv3d; checkpoint weights stay KRSC.
"""
import sys
import types


def configure_rocm():
    import torch
    from torch import nn
    import torch.nn.functional as F
    from flex_gemm.ops.spconv import sparse_submanifold_conv3d, set_algorithm, Algorithm

    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError("P3-SAM ROCm backend requires a working HIP PyTorch GPU")
    torch.cuda.reset_peak_memory_stats()
    # Native HIP neighbour-map kernel + ROCm torch GEMM. No CPU convolution.
    set_algorithm(Algorithm.EXPLICIT_GEMM)

    class SparseConvTensor:
        def __init__(self, features, indices, spatial_shape, batch_size, **kwargs):
            if not features.is_cuda or not indices.is_cuda:
                raise RuntimeError("ROCm sparse tensors must reside on the GPU")
            self.features = features
            self.indices = indices
            self.spatial_shape = spatial_shape
            self.batch_size = batch_size
            self.indice_dict = {}

        def replace_feature(self, features):
            output = SparseConvTensor(features, self.indices, self.spatial_shape, self.batch_size)
            output.indice_dict = self.indice_dict
            return output

    class SubMConv3d(nn.Module):
        def __init__(self, in_channels, out_channels, kernel_size, bias=True, indice_key=None, **kwargs):
            super().__init__()
            if kwargs:
                raise NotImplementedError(f"Unsupported Sonata convolution options: {kwargs}")
            kernel = (kernel_size,) * 3 if isinstance(kernel_size, int) else tuple(kernel_size)
            self.weight = nn.Parameter(torch.empty(out_channels, *kernel, in_channels))
            self.bias = nn.Parameter(torch.zeros(out_channels)) if bias else None
            self.indice_key = indice_key

        def forward(self, tensor):
            if torch.is_grad_enabled():
                raise RuntimeError("The P3-SAM ROCm adapter supports inference only")
            shape = torch.Size([tensor.batch_size, tensor.features.shape[1], *tensor.spatial_shape])
            cache_key = self.indice_key or id(self)
            output, cache = sparse_submanifold_conv3d(
                tensor.features.contiguous(), tensor.indices.contiguous(), shape,
                self.weight, self.bias, neighbor_cache=tensor.indice_dict.get(cache_key))
            tensor.indice_dict[cache_key] = cache
            return tensor.replace_feature(output)

    package = types.ModuleType("spconv")
    package.__path__ = []
    api = types.ModuleType("spconv.pytorch")
    api.SparseConvTensor = SparseConvTensor
    api.SubMConv3d = SubMConv3d
    api.modules = types.SimpleNamespace(is_spconv_module=lambda module: isinstance(module, SubMConv3d))
    package.pytorch = api
    sys.modules["spconv"] = package
    sys.modules["spconv.pytorch"] = api

    # Preserve Sonata's packed attention interface using PyTorch's ROCm SDPA.
    # This is GPU attention, not a CPU or geometric approximation.
    def packed_attention(qkv, cu_seqlens, max_seqlen, dropout_p=0, softmax_scale=None, **kwargs):
        if kwargs:
            raise NotImplementedError(f"Unsupported packed-attention options: {kwargs}")
        if not qkv.is_cuda:
            raise RuntimeError("ROCm attention input must reside on the GPU")
        boundaries = cu_seqlens.tolist()
        output = []
        for start, end in zip(boundaries, boundaries[1:]):
            q, k, v = qkv[start:end].permute(1, 2, 0, 3).unbind(0)
            output.append(F.scaled_dot_product_attention(q, k, v, dropout_p=dropout_p,
                scale=softmax_scale).transpose(0, 1))
        return torch.cat(output, dim=0)

    attention = types.ModuleType("flash_attn")
    attention.flash_attn_varlen_qkvpacked_func = packed_attention
    sys.modules["flash_attn"] = attention
    print("P3-SAM backend: native ROCm FlexGEMM HIP kernels + rebuilt torch-scatter + GPU SDPA", flush=True)
