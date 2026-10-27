"""Block-diagonal sparse attention using PyTorch's GPU SDPA implementation."""
import torch
import torch.nn.functional as F


def variable_attention(q, k, v, q_lengths, kv_lengths):
    pieces = []
    q_start = k_start = 0
    for q_len, k_len in zip(q_lengths, kv_lengths):
        qi = q[q_start:q_start + q_len].transpose(0, 1).unsqueeze(0)
        ki = k[k_start:k_start + k_len].transpose(0, 1).unsqueeze(0)
        vi = v[k_start:k_start + k_len].transpose(0, 1).unsqueeze(0)
        pieces.append(F.scaled_dot_product_attention(qi, ki, vi)[0].transpose(0, 1))
        q_start += q_len
        k_start += k_len
    return torch.cat(pieces, dim=0)


def packed_attention(qkv, lengths):
    q, k, v = qkv.unbind(dim=1)
    return variable_attention(q, k, v, lengths, lengths)
