# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# Copyright contributors to the vLLM-Omni project.
# SPDX-License-Identifier: Apache-2.0
"""Lance multimodal body and sequential CFG denoising."""

import math
from types import SimpleNamespace

import torch
from torch import nn

from .conditioning import LanceBagel, LanceIdentityConnector, LanceZeroVitPosEmbed
from .geometry import get_flattened_position_ids_extrapolate
from .model import Qwen2MoTForCausalLM


class TimestepEmbedder(nn.Module):
    def __init__(self, hidden_size, frequency_embedding_size=256):
        super().__init__()
        self.frequency_embedding_size = frequency_embedding_size
        self.mlp = nn.Sequential(
            nn.Linear(frequency_embedding_size, hidden_size),
            nn.SiLU(),
            nn.Linear(hidden_size, hidden_size),
        )

    def forward(self, t):
        half = self.frequency_embedding_size // 2
        freqs = torch.exp(
            -math.log(10000)
            * torch.arange(half, dtype=torch.float32, device=t.device)
            / half
        )
        args = t[:, None].float() * freqs[None]
        emb = torch.cat((torch.cos(args), torch.sin(args)), dim=-1)
        return self.mlp(emb.to(self.mlp[0].weight.dtype))


class PositionTable(nn.Module):
    def __init__(self, rows, hidden_size):
        super().__init__()
        self.pos_embed = nn.Parameter(
            torch.zeros(rows, hidden_size), requires_grad=False
        )

    def forward(self, ids):
        return self.pos_embed[ids]


class LanceTransformer(LanceBagel):
    def __init__(
        self,
        llm_config,
        *,
        position_rows=4096,
        vit_model=None,
        max_latent_size=64,
        latent_channels=48,
    ):
        # Skip BAGEL construction: Lance has no connector/ViT position weights.
        nn.Module.__init__(self)
        self.language_model = Qwen2MoTForCausalLM(llm_config)
        self.hidden_size = llm_config.hidden_size
        self.use_moe = True
        self.latent_patch_size = 1
        self.latent_channel = latent_channels
        self.latent_downsample = 16
        self.max_latent_size = max_latent_size
        self.max_num_latent_frames = position_rows // max_latent_size**2
        self.time_embedder = TimestepEmbedder(self.hidden_size)
        self.vae2llm = nn.Linear(latent_channels, self.hidden_size)
        self.llm2vae = nn.Linear(self.hidden_size, latent_channels)
        self.latent_pos_embed = PositionTable(position_rows, self.hidden_size)
        self.vit_model = vit_model
        self.connector = LanceIdentityConnector()
        self.vit_pos_embed = LanceZeroVitPosEmbed()
        self.get_flattened_position_ids = get_flattened_position_ids_extrapolate
        self.config = SimpleNamespace(
            llm_config=llm_config,
            vae_config=SimpleNamespace(
                downsample_temporal=4, z_channels=latent_channels
            ),
            visual_und=vit_model is not None,
            visual_gen=True,
        )

    def forward_single_branch(
        self,
        x_t,
        timestep,
        packed_vae_token_indexes,
        packed_vae_position_ids,
        packed_text_ids,
        packed_text_indexes,
        packed_position_ids,
        packed_seqlens,
        past_key_values,
    ):
        text = self.language_model.model.embed_tokens(packed_text_ids)
        sequence = text.new_zeros((int(packed_seqlens.sum()), self.hidden_size))
        sequence[packed_text_indexes] = text
        latent = (
            self.vae2llm(x_t.to(text.dtype))
            + self.time_embedder(timestep)
            + self.latent_pos_embed(packed_vae_position_ids)
        )
        sequence[packed_vae_token_indexes] = latent.to(sequence.dtype)
        output = self.language_model(
            packed_query_sequence=sequence,
            query_lens=packed_seqlens,
            packed_query_position_ids=packed_position_ids,
            past_key_values=past_key_values,
            update_past_key_values=False,
            is_causal=False,
            mode="gen",
            packed_vae_token_indexes=packed_vae_token_indexes,
            packed_text_indexes=packed_text_indexes,
        )
        return self.llm2vae(output.packed_query_sequence[packed_vae_token_indexes])

    @torch.inference_mode()
    def generate_image(
        self,
        packed_init_noises,
        packed_position_ids,
        past_key_values,
        *,
        num_timesteps=30,
        timestep_shift=3.5,
        cfg_text_scale=4.0,
        cfg_text_packed_position_ids=None,
        cfg_text_past_key_values=None,
        cfg_img_scale=1.0,
        cfg_img_packed_position_ids=None,
        cfg_img_past_key_values=None,
        cfg_interval=(0.4, 1.0),
        cfg_renorm_type="global",
        cfg_renorm_min=0.0,
        frame_condition_token_indexes=None,
        **inputs,
    ):
        if num_timesteps < 1 or timestep_shift <= 0:
            raise ValueError("steps and timestep_shift must be positive")
        if cfg_img_scale != 1.0:
            raise ValueError("Image CFG above 1 is not supported; use text CFG")
        x = packed_init_noises
        pinned = (
            None
            if frame_condition_token_indexes is None
            else x[frame_condition_token_indexes].clone()
        )
        times = torch.linspace(
            1, 0, num_timesteps + 1, device=x.device, dtype=torch.float32
        )
        times = timestep_shift * times / (1 + (timestep_shift - 1) * times)
        for index in range(num_timesteps):
            t = times[index]
            timestep = t.expand(x.shape[0]).clone()
            if pinned is not None:
                timestep[frame_condition_token_indexes] = 0
            velocity = self.forward_single_branch(
                x,
                timestep,
                packed_position_ids=packed_position_ids,
                past_key_values=past_key_values,
                **inputs,
            )
            if cfg_text_scale > 1 and cfg_interval[0] < float(t) <= cfg_interval[1]:
                if (
                    cfg_text_past_key_values is None
                    or cfg_text_packed_position_ids is None
                ):
                    raise ValueError(
                        "Text CFG requires its own KV cache and RoPE positions"
                    )
                unconditional = self.forward_single_branch(
                    x,
                    timestep,
                    packed_position_ids=cfg_text_packed_position_ids,
                    past_key_values=cfg_text_past_key_values,
                    **inputs,
                )
                guided = unconditional + cfg_text_scale * (velocity - unconditional)
                if cfg_renorm_type == "global":
                    scale = velocity.float().norm() / (guided.float().norm() + 1e-8)
                elif cfg_renorm_type in ("channel", "text_channel"):
                    scale = velocity.float().norm(dim=-1, keepdim=True) / (
                        guided.float().norm(dim=-1, keepdim=True) + 1e-8
                    )
                else:
                    raise ValueError(f"Unknown CFG renorm type: {cfg_renorm_type}")
                velocity = guided * scale.clamp(min=cfg_renorm_min, max=1).to(
                    guided.dtype
                )
            x = x - velocity.to(x.dtype) * (times[index] - times[index + 1])
            if pinned is not None:
                x[frame_condition_token_indexes] = pinned
        return x.split((inputs["packed_seqlens"] - 2).tolist()), None, None, None
