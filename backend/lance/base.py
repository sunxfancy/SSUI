# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# Copyright contributors to the vLLM-Omni project.
# SPDX-License-Identifier: Apache-2.0
# Adapted for SSUI: standalone PyTorch, no vLLM runtime or distributed workers.
from __future__ import annotations
import torch
from torch import nn
from .model import NaiveCache


class Bagel(nn.Module):
    def prepare_prompts(
        self, curr_kvlens, curr_rope, prompts, tokenizer, new_token_ids
    ):
        packed_text_ids = list()
        packed_text_position_ids = list()
        text_token_lens = list()
        newlens, new_rope = (list(), list())
        for prompt, curr_kvlen, curr_position_id in zip(
            prompts, curr_kvlens, curr_rope
        ):
            text_ids = tokenizer.encode(prompt, add_special_tokens=False)
            text_ids = (
                [new_token_ids["bos_token_id"]]
                + text_ids
                + [new_token_ids["eos_token_id"]]
            )
            text_token_lens.append(len(text_ids))
            packed_text_ids.extend(text_ids)
            packed_text_position_ids.extend(
                range(curr_position_id, curr_position_id + len(text_ids))
            )
            newlens.append(curr_kvlen + len(text_ids))
            new_rope.append(curr_position_id + len(text_ids))
        generation_input = {
            "text_token_lens": torch.tensor(text_token_lens, dtype=torch.int),
            "packed_text_ids": torch.tensor(packed_text_ids, dtype=torch.long),
            "packed_text_position_ids": torch.tensor(
                packed_text_position_ids, dtype=torch.long
            ),
        }
        return (generation_input, newlens, new_rope)

    def forward_cache_update_text(
        self,
        past_key_values: NaiveCache,
        packed_text_ids: torch.IntTensor,
        packed_text_position_ids: torch.LongTensor,
        text_token_lens: torch.LongTensor,
    ):
        extra_inputs = {}
        if self.use_moe:
            extra_inputs = {"mode": "und"}
        output = self.language_model.forward(
            packed_text_ids=packed_text_ids,
            query_lens=text_token_lens,
            packed_query_position_ids=packed_text_position_ids,
            past_key_values=past_key_values,
            update_past_key_values=True,
            is_causal=True,
            **extra_inputs,
        )
        past_key_values = output.past_key_values
        return past_key_values

    def forward_cache_update_vit(
        self,
        past_key_values: NaiveCache,
        packed_text_ids: torch.LongTensor,
        packed_text_indexes: torch.LongTensor,
        packed_vit_tokens: torch.Tensor,
        packed_vit_token_indexes: torch.LongTensor,
        packed_vit_position_ids: torch.LongTensor,
        vit_token_seqlens: torch.IntTensor,
        packed_position_ids: torch.LongTensor,
        packed_seqlens: torch.IntTensor,
    ):
        packed_text_embedding = self.language_model.forward(
            packed_text_ids=packed_text_ids, return_embeddings_only=True
        ).packed_query_sequence
        packed_sequence = packed_text_embedding.new_zeros(
            (sum(packed_seqlens), self.hidden_size)
        )
        packed_sequence[packed_text_indexes] = packed_text_embedding
        cu_seqlens = torch.nn.functional.pad(
            torch.cumsum(vit_token_seqlens, dim=0), (1, 0)
        )
        cu_seqlens = cu_seqlens.to(torch.int32)
        max_seqlen = torch.max(vit_token_seqlens).item()
        packed_vit_token_embed = self.vit_model(
            packed_pixel_values=packed_vit_tokens,
            packed_flattened_position_ids=packed_vit_position_ids,
            cu_seqlens=cu_seqlens,
            max_seqlen=max_seqlen,
        )
        packed_vit_token_embed = self.connector(packed_vit_token_embed)
        pos_emb = self.vit_pos_embed(packed_vit_position_ids)
        packed_vit_token_embed = packed_vit_token_embed + pos_emb
        if packed_vit_token_embed.dtype != packed_sequence.dtype:
            packed_vit_token_embed = packed_vit_token_embed.to(packed_sequence.dtype)
        packed_sequence[packed_vit_token_indexes] = packed_vit_token_embed
        extra_inputs = {}
        if self.use_moe:
            extra_inputs = {"mode": "und"}
        output = self.language_model.forward(
            packed_query_sequence=packed_sequence,
            query_lens=packed_seqlens,
            packed_query_position_ids=packed_position_ids,
            past_key_values=past_key_values,
            update_past_key_values=True,
            is_causal=False,
            **extra_inputs,
        )
        past_key_values = output.past_key_values
        return past_key_values

    def prepare_input(self, curr_kvlens, curr_rope, image_sizes, new_token_ids=None):
        packed_text_ids, packed_text_indexes = (list(), list())
        packed_vae_position_ids, packed_vae_token_indexes, packed_init_noises = (
            list(),
            list(),
            list(),
        )
        packed_position_ids, packed_seqlens = (list(), list())
        query_curr = 0
        for (H, W), curr_kvlen, curr_position_id in zip(
            image_sizes, curr_kvlens, curr_rope
        ):
            packed_text_ids.append(new_token_ids["start_of_image"])
            packed_text_indexes.append(query_curr)
            query_curr += 1
            vae_position_ids = self.get_flattened_position_ids(
                H,
                W,
                self.latent_downsample,
                max_num_patches_per_side=self.max_latent_size,
            )
            packed_vae_position_ids.append(vae_position_ids)
            h, w = (H // self.latent_downsample, W // self.latent_downsample)
            num_image_tokens = h * w
            packed_init_noises.append(
                torch.randn(
                    num_image_tokens, self.latent_channel * self.latent_patch_size**2
                )
            )
            packed_vae_token_indexes.extend(
                range(query_curr, query_curr + num_image_tokens)
            )
            packed_seqlens.append(num_image_tokens + 2)
            query_curr += num_image_tokens
            packed_text_ids.append(new_token_ids["end_of_image"])
            packed_text_indexes.append(query_curr)
            query_curr += 1
            packed_position_ids.extend([curr_position_id] * (num_image_tokens + 2))
        generation_input = {
            "packed_text_ids": torch.tensor(packed_text_ids, dtype=torch.long),
            "packed_text_indexes": torch.tensor(packed_text_indexes, dtype=torch.long),
            "packed_init_noises": torch.cat(packed_init_noises, dim=0),
            "packed_vae_position_ids": torch.cat(packed_vae_position_ids, dim=0),
            "packed_vae_token_indexes": torch.tensor(
                packed_vae_token_indexes, dtype=torch.long
            ),
            "packed_seqlens": torch.tensor(packed_seqlens, dtype=torch.int),
            "packed_position_ids": torch.tensor(packed_position_ids, dtype=torch.long),
        }
        return generation_input

    def prepare_vae_latent(self, curr_kvlens, curr_rope, image_sizes, new_token_ids):
        return self.prepare_input(curr_kvlens, curr_rope, image_sizes, new_token_ids)

    def prepare_vae_latent_cfg(self, curr_kvlens, curr_rope, image_sizes):
        packed_position_ids = list()
        for (H, W), curr_kvlen, curr_position_id in zip(
            image_sizes, curr_kvlens, curr_rope
        ):
            h, w = (H // self.latent_downsample, W // self.latent_downsample)
            num_image_tokens = h * w
            packed_position_ids.extend([curr_position_id] * (num_image_tokens + 2))
        generation_input = {
            "cfg_packed_position_ids": torch.tensor(
                packed_position_ids, dtype=torch.long
            )
        }
        return generation_input

    def prepare_start_tokens(self, curr_kvlens, curr_rope, new_token_ids):
        """Prepare start tokens for autoregressive text generation.

        Ported from the original BAGEL ``Bagel.prepare_start_tokens``.
        """
        packed_start_tokens = list()
        packed_query_position_ids = list()
        for curr_kvlen, curr_position_id in zip(curr_kvlens, curr_rope):
            packed_start_tokens.append(new_token_ids["bos_token_id"])
            packed_query_position_ids.append(curr_position_id)
        generation_input = {
            "packed_start_tokens": torch.tensor(packed_start_tokens, dtype=torch.long),
            "packed_query_position_ids": torch.tensor(
                packed_query_position_ids, dtype=torch.long
            ),
        }
        return generation_input

    @torch.no_grad()
    def generate_text(
        self,
        past_key_values: NaiveCache,
        packed_start_tokens: torch.LongTensor,
        packed_query_position_ids: torch.LongTensor,
        max_length: int,
        do_sample: bool = False,
        temperature: float = 1.0,
        end_token_id: int | None = None,
    ):
        """Autoregressive text generation (ported from original BAGEL).

        Decodes tokens one at a time, appending to ``past_key_values``
        until ``max_length`` is reached or ``end_token_id`` is generated.
        """
        step = 0
        generated_sequence = []
        curr_tokens = packed_start_tokens
        while step < max_length:
            generated_sequence.append(curr_tokens)
            query_lens = torch.ones_like(curr_tokens)
            output = self.language_model(
                packed_text_ids=curr_tokens,
                query_lens=query_lens,
                packed_query_position_ids=packed_query_position_ids,
                past_key_values=past_key_values,
                update_past_key_values=True,
                is_causal=True,
                mode="und",
            )
            past_key_values = output.past_key_values
            packed_query_sequence = output.packed_query_sequence
            pred_logits = self.language_model.lm_head(packed_query_sequence)
            if do_sample:
                probs = nn.functional.softmax(pred_logits / temperature, dim=-1)
                curr_tokens = torch.multinomial(probs, num_samples=1).squeeze(1)
            else:
                curr_tokens = torch.argmax(pred_logits, dim=-1)
            packed_query_position_ids = packed_query_position_ids + 1
            step += 1
            if end_token_id is not None and curr_tokens[0] == end_token_id:
                break
        output_device = generated_sequence[0].device
        return torch.stack([i.to(output_device) for i in generated_sequence], dim=0)
