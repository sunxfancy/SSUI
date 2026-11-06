# SPDX-License-Identifier: Apache-2.0
# RMSNorm adapted from DiffSynth-Studio; see NOTICE.
import torch
from torch import nn
from torch.nn import functional as F


class RMSNorm(nn.Module):
    def __init__(self, dim, eps):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        variance = x.float().square().mean(-1, keepdim=True)
        return (x * torch.rsqrt(variance + self.eps)).to(x.dtype) * self.weight


def attention_forward(q, k, v, **_patterns):
    # All MOSS callers use [batch, sequence, heads, head_dim].
    return F.scaled_dot_product_attention(
        q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
    ).transpose(1, 2)
