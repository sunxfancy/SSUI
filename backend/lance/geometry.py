# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# Copyright contributors to the vLLM-Omni project.
# SPDX-License-Identifier: Apache-2.0
# Adapted for SSUI: standalone PyTorch, no vLLM runtime or distributed workers.
from __future__ import annotations
import numpy as np
import torch
from torch import nn


class BagelRotaryEmbedding(nn.Module):
    """Standalone rotary embedding that generates cos/sin from position ids.

    Replaces HuggingFace's Qwen2RotaryEmbedding while preserving full
    ``rope_scaling`` support.  When ``config.rope_scaling`` is set (e.g.
    linear, dynamic-NTK, YaRN, …), we delegate the ``inv_freq`` /
    ``attention_scaling`` computation to HF's ``ROPE_INIT_FUNCTIONS`` so
    that the frequency basis and scaling factor are identical to the
    original checkpoint.

    For Qwen2.5-VL-style multimodal RoPE (``rope_scaling.rope_type == "mrope"``)
    the ``inv_freq`` basis is the standard default-rope one; the difference
    is that position ids are 3-D ``(t, h, w)`` per token and the
    ``mrope_section`` describes how the head dimension is split across axes.
    This module accepts either 2-D scalar position ids ``(B, S)`` or 3-D
    multimodal position ids ``(B, 3, S)`` and dispatches accordingly so the
    same module works for both BAGEL (1-D rope) and Lance (Qwen2.5-VL mrope).
    This module has no learnable parameters.
    """

    def __init__(self, config):
        super().__init__()
        rope_scaling = getattr(config, "rope_scaling", None) or {}
        rope_parameters = getattr(config, "rope_parameters", None) or {}
        rope_type = (
            rope_scaling.get("rope_type")
            or rope_scaling.get("type")
            or rope_parameters.get("rope_type")
            or "default"
        )
        self._mrope_section: list[int] | None = None
        if rope_type == "mrope":
            section = rope_scaling.get("mrope_section") or rope_parameters.get(
                "mrope_section"
            )
            if section is None:
                raise ValueError(
                    "rope_scaling.rope_type == 'mrope' requires 'mrope_section'."
                )
            self._mrope_section = list(section)
        if rope_type in ("default", "mrope"):
            rope_theta = (
                getattr(config, "rope_theta", None)
                or rope_parameters.get("rope_theta")
                or rope_scaling.get("rope_theta")
                or 10000.0
            )
            dim = config.hidden_size // config.num_attention_heads
            inv_freq = 1.0 / rope_theta ** (
                torch.arange(0, dim, 2, dtype=torch.float32) / dim
            )
            self.attention_scaling = 1.0
        else:
            from transformers.modeling_rope_utils import ROPE_INIT_FUNCTIONS

            rope_init_fn = ROPE_INIT_FUNCTIONS[rope_type]
            inv_freq, self.attention_scaling = rope_init_fn(config, device=None)
        self.register_buffer("inv_freq", inv_freq, persistent=False)

    @torch.no_grad()
    def forward(
        self, x: torch.Tensor, position_ids: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Generate cos/sin embeddings for given position ids.

        Args:
            x: Input tensor (only used for dtype inference).
            position_ids: Either 2-D scalar ``(batch_size, seq_len)`` for plain
                1-D RoPE, or 3-D multimodal ``(batch_size, 3, seq_len)`` for
                Qwen2.5-VL-style mRoPE.  The latter is auto-detected from
                ``position_ids.ndim``.

        Returns:
            cos, sin: Rotary embeddings, each of shape (batch_size, seq_len, dim).
        """
        if position_ids.ndim == 3 and self._mrope_section is not None:
            B = position_ids.shape[0]
            inv_freq_expanded = (
                self.inv_freq[None, None, :, None].float().expand(B, 3, -1, 1)
            )
            position_ids_expanded = position_ids[:, :, None, :].float()
            freqs = (inv_freq_expanded @ position_ids_expanded).transpose(2, 3)
            emb = torch.cat((freqs, freqs), dim=-1)
            cos_per_axis = emb.cos() * self.attention_scaling
            sin_per_axis = emb.sin() * self.attention_scaling
            sec_full = self._mrope_section * 2
            cos_split = cos_per_axis.split(sec_full, dim=-1)
            sin_split = sin_per_axis.split(sec_full, dim=-1)
            cos = torch.cat([c[:, i % 3] for i, c in enumerate(cos_split)], dim=-1)
            sin = torch.cat([s[:, i % 3] for i, s in enumerate(sin_split)], dim=-1)
            return (cos.to(dtype=x.dtype), sin.to(dtype=x.dtype))
        inv_freq_expanded = (
            self.inv_freq[None, :, None].float().expand(position_ids.shape[0], -1, 1)
        )
        position_ids_expanded = position_ids[:, None, :].float()
        freqs = (inv_freq_expanded @ position_ids_expanded).transpose(1, 2)
        emb = torch.cat((freqs, freqs), dim=-1)
        cos = emb.cos() * self.attention_scaling
        sin = emb.sin() * self.attention_scaling
        return (cos.to(dtype=x.dtype), sin.to(dtype=x.dtype))


def get_2d_sincos_pos_embed(embed_dim, grid_size, cls_token=False, extra_tokens=0):
    grid_h = np.arange(grid_size, dtype=np.float32)
    grid_w = np.arange(grid_size, dtype=np.float32)
    grid = np.meshgrid(grid_w, grid_h)
    grid = np.stack(grid, axis=0)
    grid = grid.reshape([2, 1, grid_size, grid_size])
    pos_embed = get_2d_sincos_pos_embed_from_grid(embed_dim, grid)
    if cls_token and extra_tokens > 0:
        pos_embed = np.concatenate(
            [np.zeros([extra_tokens, embed_dim]), pos_embed], axis=0
        )
    return pos_embed


def get_2d_sincos_pos_embed_from_grid(embed_dim, grid):
    assert embed_dim % 2 == 0
    emb_h = get_1d_sincos_pos_embed_from_grid(embed_dim // 2, grid[0])
    emb_w = get_1d_sincos_pos_embed_from_grid(embed_dim // 2, grid[1])
    emb = np.concatenate([emb_h, emb_w], axis=1)
    return emb


def get_1d_sincos_pos_embed_from_grid(embed_dim, pos):
    """
    embed_dim: output dimension for each position
    pos: a list of positions to be encoded: size (M,)
    out: (M, D)
    """
    assert embed_dim % 2 == 0
    omega = np.arange(embed_dim // 2, dtype=np.float64)
    omega /= embed_dim / 2.0
    omega = 1.0 / 10000**omega
    pos = pos.reshape(-1)
    out = np.einsum("m,d->md", pos, omega)
    emb_sin = np.sin(out)
    emb_cos = np.cos(out)
    emb = np.concatenate([emb_sin, emb_cos], axis=1)
    return emb


class PositionEmbedding(nn.Module):
    def __init__(self, max_num_patch_per_side, hidden_size):
        super().__init__()
        self.max_num_patch_per_side = max_num_patch_per_side
        self.hidden_size = hidden_size
        self.pos_embed = nn.Parameter(
            torch.zeros(max_num_patch_per_side**2, hidden_size), requires_grad=False
        )
        self._init_weights()

    def _init_weights(self):
        pos_embed = get_2d_sincos_pos_embed(
            self.hidden_size, self.max_num_patch_per_side
        )
        self.pos_embed.data.copy_(torch.from_numpy(pos_embed).float())

    def forward(self, position_ids):
        return self.pos_embed[position_ids]


def get_flattened_position_ids_extrapolate(
    img_h, img_w, patch_size, max_num_patches_per_side
):
    num_patches_h, num_patches_w = (img_h // patch_size, img_w // patch_size)
    coords_h = torch.arange(0, num_patches_h)
    coords_w = torch.arange(0, num_patches_w)
    pos_ids = (coords_h[:, None] * max_num_patches_per_side + coords_w).flatten()
    return pos_ids
