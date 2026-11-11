# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
"""Single-request Lance MoT transformer using PyTorch SDPA.

Parameter names match the original checkpoint, including separate understanding
and generation experts. KV caches contain only prefilled context; noise queries
never mutate them. No vLLM, flash-attn, or transformers private model APIs.
"""

from dataclasses import dataclass
from types import SimpleNamespace

import torch
from torch import nn
from torch.nn import functional as F

from .geometry import BagelRotaryEmbedding


class LanceConfig(SimpleNamespace):
    def __init__(self, **values):
        defaults = dict(
            vocab_size=151936,
            hidden_size=2048,
            intermediate_size=11008,
            num_hidden_layers=36,
            num_attention_heads=16,
            num_key_value_heads=2,
            rms_norm_eps=1e-6,
            rope_theta=1000000.0,
            rope_scaling={"rope_type": "mrope", "mrope_section": [16, 24, 24]},
            qk_norm=True,
            qk_norm_und=True,
            qk_norm_gen=True,
        )
        defaults.update(values)
        super().__init__(**defaults)
        if self.hidden_size % self.num_attention_heads:
            raise ValueError("hidden_size must be divisible by num_attention_heads")
        if self.num_attention_heads % self.num_key_value_heads:
            raise ValueError(
                "num_attention_heads must be divisible by num_key_value_heads"
            )


class NaiveCache:
    def __init__(self, num_layers):
        self.key_cache = {i: None for i in range(num_layers)}
        self.value_cache = {i: None for i in range(num_layers)}

    @property
    def seq_lens(self):
        key = self.key_cache[0]
        return 0 if key is None else key.shape[0]


@dataclass
class BaseNavitOutputWithPast:
    packed_query_sequence: torch.Tensor
    past_key_values: NaiveCache | None = None


class RMSNorm(nn.Module):
    def __init__(self, size, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(size))
        self.eps = eps

    def forward(self, x):
        normalized = x.float() * torch.rsqrt(
            x.float().square().mean(-1, keepdim=True) + self.eps
        )
        return normalized.to(x.dtype) * self.weight


class MLP(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.gate_proj = nn.Linear(
            config.hidden_size, config.intermediate_size, bias=False
        )
        self.up_proj = nn.Linear(
            config.hidden_size, config.intermediate_size, bias=False
        )
        self.down_proj = nn.Linear(
            config.intermediate_size, config.hidden_size, bias=False
        )

    def forward(self, x):
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


def route(x, understanding, generation, gen_indexes):
    """Route only VAE body tokens to the generation expert, including references."""
    if gen_indexes is None or gen_indexes.numel() == 0:
        return understanding(x)
    mask = torch.ones(x.shape[0], dtype=torch.bool, device=x.device)
    mask[gen_indexes] = False
    # Infer output width without invoking an expert on the other modality.
    gen = generation(x[gen_indexes])
    out = gen.new_empty((x.shape[0], *gen.shape[1:]))
    out[gen_indexes] = gen
    if mask.any():
        out[mask] = understanding(x[mask]).to(out.dtype)
    return out


def apply_rope(x, cos, sin):
    a, b = x.chunk(2, dim=-1)
    return x * cos[:, None] + torch.cat((-b, a), dim=-1) * sin[:, None]


class PackedAttentionMoT(nn.Module):
    def __init__(self, config, layer_idx):
        super().__init__()
        self.layer_idx = layer_idx
        self.num_heads = config.num_attention_heads
        self.num_kv_heads = config.num_key_value_heads
        self.head_dim = config.hidden_size // self.num_heads
        for suffix in ("", "_moe_gen"):
            for name, heads in (
                ("q", self.num_heads),
                ("k", self.num_kv_heads),
                ("v", self.num_kv_heads),
            ):
                setattr(
                    self,
                    f"{name}_proj{suffix}",
                    nn.Linear(config.hidden_size, heads * self.head_dim, bias=True),
                )
            setattr(
                self,
                f"o_proj{suffix}",
                nn.Linear(config.hidden_size, config.hidden_size, bias=False),
            )
            enabled = getattr(
                config, "qk_norm_gen" if suffix else "qk_norm_und", config.qk_norm
            )
            for name in ("q", "k"):
                setattr(
                    self,
                    f"{name}_norm{suffix}",
                    RMSNorm(self.head_dim, config.rms_norm_eps)
                    if enabled
                    else nn.Identity(),
                )

    def forward(
        self, x, positions, cache, gen_indexes=None, *, update=True, causal=True
    ):
        def project(name, heads):
            return route(
                x,
                getattr(self, name + "_proj"),
                getattr(self, name + "_proj_moe_gen"),
                gen_indexes,
            ).view(-1, heads, self.head_dim)

        q, k, v = (
            project("q", self.num_heads),
            project("k", self.num_kv_heads),
            project("v", self.num_kv_heads),
        )
        q = route(q, self.q_norm, self.q_norm_moe_gen, gen_indexes)
        k = route(k, self.k_norm, self.k_norm_moe_gen, gen_indexes)
        cos, sin = positions
        q, k = apply_rope(q, cos, sin), apply_rope(k, cos, sin)
        old_k = cache.key_cache[self.layer_idx] if cache is not None else None
        old_len = 0 if old_k is None else old_k.shape[0]
        if old_k is not None:
            k = torch.cat((old_k, k), dim=0)
            v = torch.cat((cache.value_cache[self.layer_idx], v), dim=0)
        if update and cache is not None:
            cache.key_cache[self.layer_idx], cache.value_cache[self.layer_idx] = k, v
        # Bottom-right causal alignment is essential for cached text decoding.
        mask = None
        if causal and old_len and q.shape[0] > 1:
            mask = (
                torch.arange(k.shape[0], device=x.device)[None, :]
                <= old_len + torch.arange(q.shape[0], device=x.device)[:, None]
            )
        groups = self.num_heads // self.num_kv_heads
        # repeat_interleave works on torch 2.4 as well as newer GQA backends.
        k = k.repeat_interleave(groups, dim=1)
        v = v.repeat_interleave(groups, dim=1)
        out = (
            F.scaled_dot_product_attention(
                q.transpose(0, 1).unsqueeze(0),
                k.transpose(0, 1).unsqueeze(0),
                v.transpose(0, 1).unsqueeze(0),
                attn_mask=mask,
                is_causal=causal and not old_len,
                dropout_p=0.0,
            )[0]
            .transpose(0, 1)
            .reshape(x.shape[0], -1)
        )
        return route(out, self.o_proj, self.o_proj_moe_gen, gen_indexes)


class Qwen2MoTDecoderLayer(nn.Module):
    def __init__(self, config, index):
        super().__init__()
        self.self_attn = PackedAttentionMoT(config, index)
        self.mlp, self.mlp_moe_gen = MLP(config), MLP(config)
        for name in ("input_layernorm", "post_attention_layernorm"):
            for suffix in ("", "_moe_gen"):
                setattr(
                    self,
                    name + suffix,
                    RMSNorm(config.hidden_size, config.rms_norm_eps),
                )

    def forward(self, x, positions, cache, gen_indexes, update, causal):
        normed = route(
            x, self.input_layernorm, self.input_layernorm_moe_gen, gen_indexes
        )
        x = x + self.self_attn(
            normed, positions, cache, gen_indexes, update=update, causal=causal
        )
        normed = route(
            x,
            self.post_attention_layernorm,
            self.post_attention_layernorm_moe_gen,
            gen_indexes,
        )
        return x + route(normed, self.mlp, self.mlp_moe_gen, gen_indexes)


class Qwen2MoTModel(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size)
        self.layers = nn.ModuleList(
            [Qwen2MoTDecoderLayer(config, i) for i in range(config.num_hidden_layers)]
        )
        self.norm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        self.norm_moe_gen = RMSNorm(config.hidden_size, config.rms_norm_eps)
        self.rotary_emb = BagelRotaryEmbedding(config)


class Qwen2MoTForCausalLM(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.model = Qwen2MoTModel(config)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)

    def forward(
        self,
        packed_query_sequence=None,
        query_lens=None,
        packed_query_position_ids=None,
        past_key_values=None,
        update_past_key_values=True,
        is_causal=True,
        mode="und",
        packed_vae_token_indexes=None,
        packed_text_indexes=None,
        packed_text_ids=None,
        return_embeddings_only=False,
    ):
        if query_lens is not None and query_lens.numel() != 1:
            raise ValueError("Lance backend currently supports one request at a time")
        x = (
            self.model.embed_tokens(packed_text_ids)
            if packed_query_sequence is None
            else packed_query_sequence
        )
        if return_embeddings_only:
            return BaseNavitOutputWithPast(x, past_key_values)
        if packed_query_position_ids.shape[-1] != x.shape[0]:
            raise ValueError("RoPE position count must match query tokens")
        cos, sin = self.model.rotary_emb(x, packed_query_position_ids.unsqueeze(0))
        positions = cos[0], sin[0]
        gen_indexes = packed_vae_token_indexes if mode == "gen" else None
        for layer in self.model.layers:
            x = layer(
                x,
                positions,
                past_key_values,
                gen_indexes,
                update_past_key_values,
                is_causal,
            )
        x = route(x, self.model.norm, self.model.norm_moe_gen, gen_indexes)
        return BaseNavitOutputWithPast(x, past_key_values)
