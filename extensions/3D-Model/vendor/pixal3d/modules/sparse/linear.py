import torch
import torch.nn as nn
import sys
from . import VarLenTensor

__all__ = [
    'SparseLinear'
]


def apply_rowwise(module, feats):
    """Bound tall inference GEMMs while preserving dtype and checkpoint keys."""
    if (sys.platform == 'win32' and torch.version.hip and
            not torch.is_grad_enabled() and len(feats) > 65536):
        output = None
        for start in range(0, len(feats), 65536):
            part = module(feats[start:start + 65536])
            if output is None:
                output = part.new_empty((len(feats), *part.shape[1:]))
            output[start:start + len(part)] = part
        return output
    return module(feats)


class SparseLinear(nn.Linear):
    def __init__(self, in_features, out_features, bias=True):
        super(SparseLinear, self).__init__(in_features, out_features, bias)

    def forward(self, input: VarLenTensor) -> VarLenTensor:
        return input.replace(apply_rowwise(super().forward, input.feats))
