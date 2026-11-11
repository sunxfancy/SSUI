# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 The Qwen Team and The HuggingFace Inc. team. All rights reserved.
# Adapted text-only, cache-free Qwen3.5 inference. See NOTICE for sources.
from types import SimpleNamespace

import torch
from torch import nn
from torch.nn import functional as F

from .qwen_ops import (
    Qwen3_5RMSNorm, Qwen3_5RMSNormGated, apply_rotary_pos_emb,
    repeat_kv, torch_chunk_gated_delta_rule,
)


def text_config(values=None):
    values = values or {}
    values = values.get("text_config", values)
    defaults = dict(
        hidden_size=4096, intermediate_size=12288, num_hidden_layers=32,
        num_attention_heads=16, num_key_value_heads=4, head_dim=256,
        vocab_size=248320, rms_norm_eps=1e-6, attention_bias=False,
        linear_num_key_heads=16, linear_num_value_heads=32,
        linear_key_head_dim=128, linear_value_head_dim=128,
        linear_conv_kernel_dim=4, hidden_act="silu", full_attention_interval=4,
    )
    defaults.update(values)
    if defaults["hidden_act"] != "silu":
        raise ValueError("MOSS Qwen3.5 supports only silu activation")
    if not defaults.get("attn_output_gate", True):
        raise ValueError("MOSS requires gated Qwen3.5 full attention")
    defaults.setdefault("layer_types", [
        "full_attention" if (i + 1) % defaults["full_attention_interval"] == 0
        else "linear_attention" for i in range(defaults["num_hidden_layers"])
    ])
    if len(defaults["layer_types"]) != defaults["num_hidden_layers"]:
        raise ValueError("Qwen3.5 layer_types does not match num_hidden_layers")
    rope = defaults.setdefault("rope_parameters", {})
    if rope.get("rope_type", "default") != "default":
        raise ValueError("MOSS supports only default Qwen3.5 RoPE")
    defaults["rope_theta"] = rope.get("rope_theta", defaults.get("rope_theta", 10000000.0))
    defaults["partial_rotary_factor"] = rope.get("partial_rotary_factor", defaults.get("partial_rotary_factor", 0.25))
    return SimpleNamespace(**defaults)


class LinearAttention(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.num_k_heads = c.linear_num_key_heads
        self.num_v_heads = c.linear_num_value_heads
        self.head_k_dim = c.linear_key_head_dim
        self.head_v_dim = c.linear_value_head_dim
        self.key_dim = self.num_k_heads * self.head_k_dim
        self.value_dim = self.num_v_heads * self.head_v_dim
        if self.num_v_heads % self.num_k_heads:
            raise ValueError("Linear value heads must be divisible by key heads")
        dim = self.key_dim * 2 + self.value_dim
        self.conv1d = nn.Conv1d(dim, dim, c.linear_conv_kernel_dim,
                                groups=dim, padding=c.linear_conv_kernel_dim - 1, bias=False)
        self.dt_bias = nn.Parameter(torch.ones(self.num_v_heads))
        self.A_log = nn.Parameter(torch.zeros(self.num_v_heads))
        self.norm = Qwen3_5RMSNormGated(self.head_v_dim, eps=c.rms_norm_eps)
        self.out_proj = nn.Linear(self.value_dim, c.hidden_size, bias=False)
        self.in_proj_qkv = nn.Linear(c.hidden_size, dim, bias=False)
        self.in_proj_z = nn.Linear(c.hidden_size, self.value_dim, bias=False)
        self.in_proj_b = nn.Linear(c.hidden_size, self.num_v_heads, bias=False)
        self.in_proj_a = nn.Linear(c.hidden_size, self.num_v_heads, bias=False)

    def forward(self, x, mask):
        # Inputs are unpadded individually by TextEncoder, matching training lengths.
        if mask is not None:
            x = (x * mask[:, :, None]).to(x.dtype)
        b, s, _ = x.shape
        qkv = F.silu(self.conv1d(self.in_proj_qkv(x).transpose(1, 2))[:, :, :s]).transpose(1, 2)
        q, k, v = qkv.split((self.key_dim, self.key_dim, self.value_dim), dim=-1)
        q = q.reshape(b, s, self.num_k_heads, self.head_k_dim)
        k = k.reshape_as(q)
        v = v.reshape(b, s, self.num_v_heads, self.head_v_dim)
        repeats = self.num_v_heads // self.num_k_heads
        q, k = q.repeat_interleave(repeats, 2), k.repeat_interleave(repeats, 2)
        beta = self.in_proj_b(x).sigmoid()
        g = -self.A_log.float().exp() * F.softplus(self.in_proj_a(x).float() + self.dt_bias)
        out, _ = torch_chunk_gated_delta_rule(q, k, v, g, beta, use_qk_l2norm_in_kernel=True)
        gate = self.in_proj_z(x).reshape(-1, self.head_v_dim)
        out = self.norm(out.reshape(-1, self.head_v_dim), gate).reshape(b, s, self.value_dim)
        return self.out_proj(out)


class FullAttention(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.head_dim = c.head_dim
        self.num_heads = c.num_attention_heads
        self.num_kv_heads = c.num_key_value_heads
        if self.num_heads % self.num_kv_heads:
            raise ValueError("Attention heads must be divisible by key/value heads")
        self.q_proj = nn.Linear(c.hidden_size, self.num_heads * self.head_dim * 2, bias=c.attention_bias)
        self.k_proj = nn.Linear(c.hidden_size, self.num_kv_heads * self.head_dim, bias=c.attention_bias)
        self.v_proj = nn.Linear(c.hidden_size, self.num_kv_heads * self.head_dim, bias=c.attention_bias)
        self.o_proj = nn.Linear(self.num_heads * self.head_dim, c.hidden_size, bias=c.attention_bias)
        self.q_norm = Qwen3_5RMSNorm(self.head_dim, eps=c.rms_norm_eps)
        self.k_norm = Qwen3_5RMSNorm(self.head_dim, eps=c.rms_norm_eps)

    def forward(self, x, rope):
        b, s, _ = x.shape
        q, gate = self.q_proj(x).view(b, s, self.num_heads, self.head_dim * 2).chunk(2, -1)
        q = self.q_norm(q).transpose(1, 2)
        k = self.k_norm(self.k_proj(x).view(b, s, self.num_kv_heads, self.head_dim)).transpose(1, 2)
        v = self.v_proj(x).view(b, s, self.num_kv_heads, self.head_dim).transpose(1, 2)
        q, k = apply_rotary_pos_emb(q, k, *rope)
        k, v = repeat_kv(k, self.num_heads // self.num_kv_heads), repeat_kv(v, self.num_heads // self.num_kv_heads)
        out = F.scaled_dot_product_attention(q, k, v, is_causal=True).transpose(1, 2).reshape(b, s, -1)
        return self.o_proj(out * gate.reshape(b, s, -1).sigmoid())


class MLP(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.gate_proj = nn.Linear(c.hidden_size, c.intermediate_size, bias=False)
        self.up_proj = nn.Linear(c.hidden_size, c.intermediate_size, bias=False)
        self.down_proj = nn.Linear(c.intermediate_size, c.hidden_size, bias=False)

    def forward(self, x):
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class TextLayer(nn.Module):
    def __init__(self, c, index):
        super().__init__()
        self.layer_type = c.layer_types[index]
        if self.layer_type == "linear_attention":
            self.linear_attn = LinearAttention(c)
        elif self.layer_type == "full_attention":
            self.self_attn = FullAttention(c)
        else:
            raise ValueError(f"Unsupported Qwen3.5 layer type: {self.layer_type}")
        self.input_layernorm = Qwen3_5RMSNorm(c.hidden_size, eps=c.rms_norm_eps)
        self.post_attention_layernorm = Qwen3_5RMSNorm(c.hidden_size, eps=c.rms_norm_eps)
        self.mlp = MLP(c)

    def forward(self, x, rope):
        h = self.input_layernorm(x)
        x = x + (self.linear_attn(h, None) if self.layer_type == "linear_attention" else self.self_attn(h, rope))
        return x + self.mlp(self.post_attention_layernorm(x))


class TextEncoder(nn.Module):
    """Qwen3.5 text backbone, retaining Hugging Face language_model weight keys."""
    def __init__(self, config=None):
        super().__init__()
        self.config = c = text_config(config)
        self.embed_tokens = nn.Embedding(c.vocab_size, c.hidden_size)
        self.layers = nn.ModuleList([TextLayer(c, i) for i in range(c.num_hidden_layers)])
        self.norm = Qwen3_5RMSNorm(c.hidden_size, eps=c.rms_norm_eps)

    def _forward_unpadded(self, ids):
        x = self.embed_tokens(ids)
        c = self.config
        dim = int(c.head_dim * c.partial_rotary_factor)
        # Text-only positions coincide along all three MRoPE axes. Recompute in
        # FP32 after device/dtype changes instead of downcasting a RoPE buffer.
        with torch.autocast(device_type=x.device.type, enabled=False):
            inv = 1.0 / (c.rope_theta ** (torch.arange(0, dim, 2, device=x.device).float() / dim))
            phase = torch.arange(ids.shape[1], device=x.device).float()[:, None] * inv
            emb = torch.cat((phase, phase), -1)[None]
            rope = emb.cos().to(x.dtype), emb.sin().to(x.dtype)
        for layer in self.layers:
            x = layer(x, rope)
        return self.norm(x)

    def forward(self, input_ids, attention_mask=None):
        if input_ids.ndim != 2 or input_ids.shape[1] == 0:
            raise ValueError("Expected nonempty [batch, sequence] token IDs")
        if attention_mask is None:
            return self._forward_unpadded(input_ids)
        if attention_mask.shape != input_ids.shape or not torch.all((attention_mask == 0) | (attention_mask == 1)):
            raise ValueError("Expected binary attention mask matching token IDs")
        outputs = []
        for ids, mask in zip(input_ids, attention_mask.bool()):
            if not mask.any():
                raise ValueError("Each prompt needs at least one valid token")
            encoded = self._forward_unpadded(ids[mask][None])[0]
            out = encoded.new_zeros((ids.shape[0], encoded.shape[-1]))
            out[mask] = encoded
            outputs.append(out)
        return torch.stack(outputs)
