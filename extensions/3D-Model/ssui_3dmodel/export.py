"""Inference export adapters for Windows ROCm's native FlexGEMM build."""
import sys
from types import FunctionType
import torch


def sample_volume(feats, coords, shape, grid, mode="trilinear"):
    """Use HIP neighbor lookup and PyTorch reduction, without Triton JIT.

    Chunk queries so a 4096px atlas does not materialize all eight neighbors
    and feature channels at once. Missing sparse neighbors contribute zero.
    """
    from flex_gemm import kernels
    from flex_gemm.ops import utils
    if mode != "trilinear":
        raise ValueError("GLB export supports trilinear sampling only")
    keys, values = utils.init_hashmap(shape, max(1, 2 * len(coords)), coords.device)
    batch, count, _ = grid.shape
    output = []
    for start in range(0, count, 65536):
        indices, weights = kernels.cuda.hashmap_build_grid_sample_3d_trilinear_neighbor_map_weight(
            keys, values, coords.int(), grid[:, start:start + 65536].contiguous(), *shape[-3:]
        )
        indices = indices.reshape(-1, 8).long()
        weights = weights.reshape(-1, 8)
        valid = (indices >= 0) & (indices < len(feats))
        gathered = feats[indices.clamp(0, max(0, len(feats) - 1))]
        sampled = (gathered * weights[..., None] * valid[..., None]).sum(1)
        output.append(sampled.reshape(batch, -1, feats.shape[-1]))
    return torch.cat(output, dim=1) if output else feats.new_empty((batch, 0, feats.shape[-1]))


def to_glb(**kwargs):
    import o_voxel
    original = o_voxel.postprocess.to_glb
    if sys.platform != "win32" or not torch.version.hip:
        return original(**kwargs)
    # Keep upstream cleaning/UV/material behavior and isolate the sampler
    # substitution to this invocation; never mutate process-global module state.
    namespace = dict(original.__globals__, grid_sample_3d=sample_volume)
    export = FunctionType(original.__code__, namespace, original.__name__,
                          original.__defaults__, original.__closure__)
    export.__kwdefaults__ = original.__kwdefaults__
    return export(**kwargs)
