# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# Copyright contributors to the vLLM-Omni project.
# SPDX-License-Identifier: Apache-2.0
# Adapted for SSUI: standalone PyTorch, no vLLM runtime or distributed workers.
from __future__ import annotations
from dataclasses import dataclass
from logging import getLogger
import torch
from PIL import Image
from .model import NaiveCache
from .prompts import SYSTEM_PROMPTS
from .wan_vae import LanceWanVAE

logger = getLogger(__name__)


@dataclass
class DiffusionOutput:
    output: dict
    stage_durations: object = None


@dataclass(frozen=True)
class Defaults:
    timestep_shift: float = 3.5
    num_timesteps: int = 30
    max_num_video_latent_frames: int = 31


LANCE_DEFAULTS = Defaults()


def _extract_user_instruction(rendered: str) -> str:
    """Pull just the user instruction out of a chat-template-rendered prompt.

    ``render_lance_prompt`` wraps the instruction in:

        <|im_start|>system\\n{sys}<|im_end|>\\n
        <|im_start|>user\\n{vision_block}{user_text}<|im_end|>\\n
        <|im_start|>assistant\\n

    The ``image_edit`` pipeline rebuilds the chat template segment-by-segment
    (so the rope positions and segment boundaries match upstream Lance), and
    therefore needs only ``user_text`` — not the wrapped string.  This helper
    extracts it; if the input doesn't look templated it's returned as-is.
    """
    if "<|im_start|>user" not in rendered:
        return rendered.strip()
    after_user = rendered.split("<|im_start|>user", 1)[1]
    after_user = after_user.lstrip("\n")
    user_block = after_user.split("<|im_end|>", 1)[0]
    out = []
    i = 0
    while i < len(user_block):
        if user_block.startswith("<|vision_start|>", i):
            j = user_block.find("<|vision_end|>", i)
            if j == -1:
                break
            i = j + len("<|vision_end|>")
            continue
        out.append(user_block[i])
        i += 1
    return "".join(out).strip()


class InferenceMixin:
    def _new_gen_context(self) -> dict:
        return {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }

    @staticmethod
    def _segment_strings(task: str, modality: str) -> tuple[str, str]:
        sys_prompt = SYSTEM_PROMPTS[task, modality]
        return (
            f"<|im_start|>system\n{sys_prompt}<|im_end|>\n<|im_start|>user\n",
            "<|im_end|>\n<|im_start|>assistant\n",
        )

    def _raw_text_prefill(self, ctx: dict, text_str: str) -> None:
        """Tokenize ``text_str`` (no bos/eos) and append to ``ctx`` KV cache."""
        text_ids = self.tokenizer.encode(text_str, add_special_tokens=False)
        if not text_ids:
            return
        curr_kvlen = ctx["kv_lens"][0]
        curr_rope = ctx["ropes"][0]
        seq_len = len(text_ids)
        inp = {
            "text_token_lens": torch.tensor(
                [seq_len], dtype=torch.int, device=self.device
            ),
            "packed_text_ids": torch.tensor(
                text_ids, dtype=torch.long, device=self.device
            ),
            "packed_text_position_ids": torch.arange(
                curr_rope, curr_rope + seq_len, dtype=torch.long, device=self.device
            ),
        }
        with torch.autocast(**self._autocast_kwargs()):
            ctx["past_key_values"] = self.bagel.forward_cache_update_text(
                ctx["past_key_values"], **inp
            )
        ctx["kv_lens"] = [curr_kvlen + seq_len]
        ctx["ropes"] = [curr_rope + seq_len]

    def _vit_image_prefill(self, ctx: dict, images: list, transforms) -> None:
        """ViT prefill from PIL images via ``prepare_vit_images``."""
        inp, new_kvlens, new_rope = self.bagel.prepare_vit_images(
            curr_kvlens=ctx["kv_lens"],
            curr_rope=ctx["ropes"],
            images=images,
            transforms=transforms,
            new_token_ids=self.new_token_ids,
        )
        for k, v in inp.items():
            if torch.is_tensor(v):
                inp[k] = v.to(self.device)
        for k in self._STALE_PREFILL_KEYS:
            inp.pop(k, None)
        with torch.autocast(**self._autocast_kwargs()):
            ctx["past_key_values"] = self.bagel.forward_cache_update_vit(
                ctx["past_key_values"], **inp
            )
        ctx["kv_lens"] = new_kvlens
        ctx["ropes"] = new_rope

    def _vit_video_prefill(
        self, ctx: dict, videos: list, precomputed_vit: list | None = None
    ) -> None:
        """ViT prefill from videos via ``prepare_vit_videos``.

        Pass ``precomputed_vit=[(pixels, grid_thw)]`` to bypass the
        Qwen2VLImageProcessor smart-resize and feed already-bucketed
        ViT patches directly (used by i2v / video_edit to keep grid
        dimensions aligned with the ref VAE block).  Omit it to let
        ``prepare_vit_videos`` run the processor itself (x2t_video).
        """
        kwargs = dict(
            curr_kvlens=ctx["kv_lens"],
            curr_rope=ctx["ropes"],
            videos=videos,
            new_token_ids=self.new_token_ids,
        )
        if precomputed_vit is not None:
            kwargs["precomputed_vit"] = precomputed_vit
        inp, new_kvlens, new_rope = self.bagel.prepare_vit_videos(**kwargs)
        for k, v in inp.items():
            if torch.is_tensor(v):
                inp[k] = v.to(self.device)
        for k in self._STALE_PREFILL_KEYS:
            inp.pop(k, None)
        with torch.autocast(**self._autocast_kwargs()):
            ctx["past_key_values"] = self.bagel.forward_cache_update_vit(
                ctx["past_key_values"], **inp
            )
        ctx["kv_lens"] = new_kvlens
        ctx["ropes"] = new_rope

    def _vae_ref_prefill(
        self, ctx: dict, images: list, transforms, *, is_video: bool, latent_cache: list
    ) -> None:
        """VAE prefill of a reference image / video at timestep 0.

        ``latent_cache`` is a single-slot list used to share the encoded
        posterior between the gen branch and the cfg_text branch — Wan2.2's
        ``mu + std * randn_like(std)`` samples a fresh latent every call,
        which otherwise drifts the two branches' KV caches.
        """
        inp, new_kvlens, new_rope = self.bagel._lance_native_prepare_vae_images(
            curr_kvlens=ctx["kv_lens"],
            curr_rope=ctx["ropes"],
            images=images,
            transforms=transforms,
            new_token_ids=self.new_token_ids,
            is_video=is_video,
        )
        for k, v in inp.items():
            if torch.is_tensor(v):
                inp[k] = v.to(self.device)
        if not latent_cache:
            latent_cache.append(self.vae.encode(inp["padded_images"].to(self.device)))
        inp["precomputed_latent"] = latent_cache[0]
        with torch.autocast(**self._autocast_kwargs()):
            ctx["past_key_values"] = self.bagel.forward_cache_update_vae(
                self.vae, ctx["past_key_values"], **inp
            )
        ctx["kv_lens"] = new_kvlens
        ctx["ropes"] = new_rope

    @torch.inference_mode()
    def _forward_t2v(self, req):
        """Minimal text-to-video forward: text prefill + 3-D latent denoising +
        Wan2.2 multi-frame decode.  Mirrors :meth:`BagelPipeline.forward`'s t2i
        branch but with 3-D latents (no image input, no x2t)."""
        from copy import deepcopy

        first_prompt = req.prompts[0]
        if isinstance(first_prompt, dict):
            prompt = first_prompt.get("prompt") or ""
            extra_args = first_prompt.get("extra_args") or {}
        else:
            prompt = str(first_prompt)
            extra_args = {}
        sp_extra = getattr(req.sampling_params, "extra_args", {}) or {}
        extra_args = {**extra_args, **sp_extra}
        T = int(extra_args.get("num_frames", 25))
        H = int(req.sampling_params.height or extra_args.get("video_height", 480))
        W = int(req.sampling_params.width or extra_args.get("video_width", 768))
        max_lat = self.bagel.max_latent_size
        max_hw = max_lat * self.bagel.latent_downsample
        if H > max_hw or W > max_hw:
            raise ValueError(
                f"Requested video resolution {H}x{W} exceeds Lance limit {max_hw}x{max_hw}"
            )
        downsample_t = int(
            getattr(self.bagel.config.vae_config, "downsample_temporal", 4)
        )
        max_T_lat = LANCE_DEFAULTS.max_num_video_latent_frames
        if (T - 1) // downsample_t + 1 > max_T_lat:
            raise ValueError(
                f"Requested num_frames={T} exceeds Lance video temporal limit {(max_T_lat - 1) * downsample_t + 1} (max_num_video_latent_frames={max_T_lat})"
            )
        video_shape = (T, H, W)
        logger.info("Lance t2v: video_shape=%s", video_shape)
        cfg_text_scale = float(extra_args.get("cfg_text_scale", 4.0))
        cfg_interval = tuple(extra_args.get("cfg_interval", (0.4, 1.0)))
        cfg_renorm_type = str(extra_args.get("cfg_renorm_type", "global"))
        cfg_renorm_min = float(extra_args.get("cfg_renorm_min", 0.0))
        timestep_shift = float(
            extra_args.get("timestep_shift", LANCE_DEFAULTS.timestep_shift)
        )
        num_timesteps = int(
            req.sampling_params.num_inference_steps or LANCE_DEFAULTS.num_timesteps
        )
        if req.sampling_params.seed is not None:
            torch.manual_seed(req.sampling_params.seed)
            if self.device.type == "cuda":
                torch.cuda.manual_seed(req.sampling_params.seed)
        gen_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        cfg_text_context = deepcopy(gen_context)
        gen_input_text, newlens, new_rope = self.bagel.prepare_prompts(
            curr_kvlens=gen_context["kv_lens"],
            curr_rope=gen_context["ropes"],
            prompts=[prompt],
            tokenizer=self.tokenizer,
            new_token_ids=self.new_token_ids,
        )
        for k, v in gen_input_text.items():
            if torch.is_tensor(v):
                gen_input_text[k] = v.to(self.device)
        with torch.autocast(
            device_type=self.device.type,
            enabled=self.device.type != "cpu",
            dtype=self.od_config.dtype,
        ):
            gen_context["past_key_values"] = self.bagel.forward_cache_update_text(
                gen_context["past_key_values"], **gen_input_text
            )
        gen_context["kv_lens"] = newlens
        gen_context["ropes"] = new_rope
        if cfg_text_scale > 1.0:
            neg_prompt = str(extra_args.get("negative_prompt") or "")
            neg_input, neg_newlens, neg_rope = self.bagel.prepare_prompts(
                curr_kvlens=cfg_text_context["kv_lens"],
                curr_rope=cfg_text_context["ropes"],
                prompts=[neg_prompt],
                tokenizer=self.tokenizer,
                new_token_ids=self.new_token_ids,
            )
            for k, v in neg_input.items():
                if torch.is_tensor(v):
                    neg_input[k] = v.to(self.device)
            with torch.autocast(
                device_type=self.device.type,
                enabled=self.device.type != "cpu",
                dtype=self.od_config.dtype,
            ):
                cfg_text_context["past_key_values"] = (
                    self.bagel.forward_cache_update_text(
                        cfg_text_context["past_key_values"], **neg_input
                    )
                )
            cfg_text_context["kv_lens"] = neg_newlens
            cfg_text_context["ropes"] = neg_rope
        gen_input_lat = self.bagel.prepare_video_latent(
            curr_kvlens=gen_context["kv_lens"],
            curr_rope=gen_context["ropes"],
            video_shapes=[video_shape],
            new_token_ids=self.new_token_ids,
        )
        for k, v in gen_input_lat.items():
            if torch.is_tensor(v):
                gen_input_lat[k] = v.to(self.device)
        cfg_text_lat = self.bagel.prepare_video_latent_cfg(
            curr_kvlens=cfg_text_context["kv_lens"],
            curr_rope=cfg_text_context["ropes"],
            video_shapes=[video_shape],
        )
        for k, v in cfg_text_lat.items():
            if torch.is_tensor(v):
                cfg_text_lat[k] = v.to(self.device)
        self._regen_init_noise_on_device(gen_input_lat, req.sampling_params.seed)
        with torch.autocast(
            device_type=self.device.type,
            enabled=self.device.type != "cpu",
            dtype=self.od_config.dtype,
        ):
            for _drop in (
                "key_values_lens",
                "packed_indexes",
                "packed_key_value_indexes",
            ):
                gen_input_lat.pop(_drop, None)
            latents, *_ = self.bagel.generate_image(
                past_key_values=gen_context["past_key_values"],
                cfg_text_past_key_values=cfg_text_context["past_key_values"],
                cfg_img_past_key_values=None,
                num_timesteps=num_timesteps,
                timestep_shift=timestep_shift,
                cfg_text_scale=cfg_text_scale,
                cfg_img_scale=1.0,
                cfg_interval=cfg_interval,
                cfg_renorm_type=cfg_renorm_type,
                cfg_renorm_min=cfg_renorm_min,
                **gen_input_lat,
                cfg_text_packed_position_ids=cfg_text_lat["cfg_packed_position_ids"],
                cfg_img_packed_position_ids=None,
            )
        frames_np = self._decode_video_from_latent(
            self.bagel, self.vae, latents[0], video_shape
        )
        frames = [Image.fromarray(f) for f in frames_np]
        logger.info(
            "Lance t2v: decoded %d frames at %dx%d",
            len(frames),
            frames[0].width,
            frames[0].height,
        )
        return DiffusionOutput(
            output={
                "payload": {"video": frames},
                "metadata": {"video": {"shape": video_shape}},
            },
            stage_durations=self.stage_durations
            if hasattr(self, "stage_durations")
            else None,
        )

    @torch.inference_mode()
    def _forward_image_edit(self, req):
        """Image edit (img2img): reference image + text prompt → modified image.

        Matches upstream Lance's image_edit prefill structure (see
        ``Lance.validation_gen_KVcache`` and ``validation_dataset.py``).  The
        sequence is laid out as 5 prefill segments + 1 noise QUERY:

          seg1 (causal, modality=system_prompt):
              ``<|im_start|>system\\n{sys}<|im_end|>\\n<|im_start|>user\\n``
          seg2 (full,   modality=ref_vit):
              ViT(ref) — ref image through Qwen2.5-VL ViT
          seg3 (full_noise, modality=ref_source):
              VAE(ref) — ref image through Wan2.2 VAE, time_embed(t=0)
          seg4 (causal, modality=text):  the user instruction
          seg5 (causal, modality=system_prompt):
              ``<|im_end|>\\n<|im_start|>assistant\\n``
          seg6 (noise QUERY): the gen latent to denoise

        cfg_text_context skips ONLY seg4 (the user text instruction) — every
        other segment, including the system header, ViT and VAE prefill, the
        separator and the noise query, is shared between gen_context and
        cfg_text_context.  The rope counter still advances by seg4's length
        for cfg_text_context so that seg5's rope position matches between
        the two branches.

        cfg_img is OFF by default (``cfg_img_scale=1.0`` matches upstream's
        ``cfg_vit_scale=1.0``).
        """
        import numpy as np

        first_prompt = req.prompts[0]
        assert isinstance(first_prompt, dict), "image_edit requires dict-style prompt"
        user_text = first_prompt.get("user_text")
        rendered = first_prompt.get("prompt") or ""
        if not user_text:
            user_text = _extract_user_instruction(rendered)
        mm_data = first_prompt.get("multi_modal_data") or {}
        image_input = mm_data.get("img2img") or mm_data.get("image")
        if image_input is None:
            raise ValueError(
                "image_edit requires multi_modal_data.img2img (or .image)."
            )
        if not isinstance(image_input, list):
            image_input = [image_input]
        image_input = [
            Image.open(im) if isinstance(im, str) else im for im in image_input
        ]
        extra_args = first_prompt.get("extra_args") or {}
        sp_extra = getattr(req.sampling_params, "extra_args", {}) or {}
        extra_args = {**extra_args, **sp_extra}
        cfg_text_scale = float(extra_args.get("cfg_text_scale", 4.0))
        cfg_img_scale = float(extra_args.get("cfg_img_scale", 1.0))
        cfg_interval = tuple(extra_args.get("cfg_interval", (0.4, 1.0)))
        cfg_renorm_type = str(extra_args.get("cfg_renorm_type", "global"))
        cfg_renorm_min = float(extra_args.get("cfg_renorm_min", 0.0))
        timestep_shift = float(
            extra_args.get("timestep_shift", LANCE_DEFAULTS.timestep_shift)
        )
        num_timesteps = int(
            req.sampling_params.num_inference_steps or LANCE_DEFAULTS.num_timesteps
        )
        stride = self.bagel.latent_downsample
        max_hw = int(self.bagel.max_latent_size * stride)

        def _resize_to_stride(img):
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            scale = min(max_hw / max(w, h), 1.0)
            scale = max(scale, min(256, max_hw) / min(w, h))
            new_w = max(stride, int(round(w * scale / stride) * stride))
            new_h = max(stride, int(round(h * scale / stride) * stride))
            new_w = min(new_w, max_hw)
            new_h = min(new_h, max_hw)
            if new_w != w or new_h != h:
                img = img.resize((new_w, new_h), Image.BICUBIC)
            return img

        image_input = [_resize_to_stride(im) for im in image_input]
        resized_w, resized_h = image_input[0].size
        image_shape = (resized_h, resized_w)
        logger.info(
            "Lance image_edit: ref image %dx%d, user_text=%r",
            resized_w,
            resized_h,
            user_text,
        )

        def vae_transforms(img):
            arr = torch.from_numpy(np.array(img)).float() / 127.5 - 1.0
            return arr.permute(2, 0, 1)

        def vit_transforms(img):
            return self.image_processor(images=img, return_tensors="pt").pixel_values[0]

        if req.sampling_params.seed is not None:
            torch.manual_seed(req.sampling_params.seed)
            if self.device.type == "cuda":
                torch.cuda.manual_seed(req.sampling_params.seed)
        gen_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        cfg_text_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        ref_latent_cache: list = []
        seg1_str, seg5_str = self._segment_strings("image_edit", "image")
        self._raw_text_prefill(gen_context, seg1_str)
        if cfg_text_scale > 1.0:
            self._raw_text_prefill(cfg_text_context, seg1_str)
        self._vit_image_prefill(gen_context, image_input, vit_transforms)
        if cfg_text_scale > 1.0:
            self._vit_image_prefill(cfg_text_context, image_input, vit_transforms)
        rope_before_vae = gen_context["ropes"][0]
        cfg_rope_before_vae = (
            cfg_text_context["ropes"][0] if cfg_text_scale > 1.0 else rope_before_vae
        )
        self._vae_ref_prefill(
            gen_context,
            image_input,
            vae_transforms,
            is_video=False,
            latent_cache=ref_latent_cache,
        )
        if cfg_text_scale > 1.0:
            self._vae_ref_prefill(
                cfg_text_context,
                image_input,
                vae_transforms,
                is_video=False,
                latent_cache=ref_latent_cache,
            )
        self._raw_text_prefill(gen_context, user_text)
        self._raw_text_prefill(gen_context, seg5_str)
        if cfg_text_scale > 1.0:
            self._raw_text_prefill(cfg_text_context, seg5_str)
        gen_input_lat = self.bagel.prepare_vae_latent(
            curr_kvlens=gen_context["kv_lens"],
            curr_rope=[rope_before_vae],
            image_sizes=[image_shape],
            new_token_ids=self.new_token_ids,
        )
        for k, v in gen_input_lat.items():
            if torch.is_tensor(v):
                gen_input_lat[k] = v.to(self.device)
        cfg_text_lat = self.bagel.prepare_vae_latent_cfg(
            curr_kvlens=cfg_text_context["kv_lens"],
            curr_rope=[cfg_rope_before_vae],
            image_sizes=[image_shape],
        )
        for k, v in cfg_text_lat.items():
            if torch.is_tensor(v):
                cfg_text_lat[k] = v.to(self.device)
        cfg_img_lat = cfg_text_lat if cfg_img_scale > 1.0 else None
        self._regen_init_noise_on_device(gen_input_lat, req.sampling_params.seed)
        with torch.autocast(**self._autocast_kwargs()):
            for _drop in (
                "key_values_lens",
                "packed_indexes",
                "packed_key_value_indexes",
            ):
                gen_input_lat.pop(_drop, None)
            latents, *_ = self.bagel.generate_image(
                past_key_values=gen_context["past_key_values"],
                cfg_text_past_key_values=cfg_text_context["past_key_values"]
                if cfg_text_scale > 1.0
                else gen_context["past_key_values"],
                cfg_img_past_key_values=gen_context["past_key_values"],
                num_timesteps=num_timesteps,
                timestep_shift=timestep_shift,
                cfg_text_scale=cfg_text_scale,
                cfg_img_scale=cfg_img_scale,
                cfg_interval=cfg_interval,
                cfg_renorm_type=cfg_renorm_type,
                cfg_renorm_min=cfg_renorm_min,
                **gen_input_lat,
                cfg_text_packed_position_ids=cfg_text_lat["cfg_packed_position_ids"],
                cfg_img_packed_position_ids=cfg_img_lat["cfg_packed_position_ids"]
                if cfg_img_lat is not None
                else None,
            )
        img = self._decode_image_from_latent(
            self.bagel, self.vae, latents[0], image_shape
        )
        return DiffusionOutput(
            output={
                "payload": {"image": img},
                "metadata": {"image": {"shape": image_shape}},
            },
            stage_durations=self.stage_durations
            if hasattr(self, "stage_durations")
            else None,
        )

    @torch.inference_mode()
    @torch.inference_mode()
    def _forward_i2v(self, req):
        """Image-to-Video (upstream-faithful first-frame conditioning).

        Mirrors upstream Lance PR #33's ``ff2v_sample`` + ``validation_gen_KVcache``
        math byte-for-byte at the algorithmic level:

          1. Treat the input image as 4 replicated pixel frames
             ``(3, 4, H, W)``.  This matches upstream
             ``vae_tensor[:, :4, :, :] = vae_image_tensor[:, 0:1, :, :].repeat(1, 4, 1, 1)``
             — required because Wan2.2 VAE has temporal stride 4, so 4
             pixel frames collapse to 1 latent frame.

          2. VAE-encode → first latent frame at the image content.

          3. Inject the encoded latent into ``packed_init_noises`` at
             the first ``h_lat × w_lat`` token slice (frame 0).

          4. Pass ``frame_condition_token_indexes = arange(0, h_lat*w_lat)``
             to ``Bagel.generate_image`` so that:
               * ``timestep[cond] = 0`` every iter (clean signal),
               * ``x_t[cond]`` is restored verbatim after each
                 velocity update (never denoised).

        Plus a ViT+VAE-ref prefill of the same image (so the LLM also
        attends to it through KV cache, matching upstream's
        gen-pre-condition pass).
        """
        import numpy as _np
        from PIL import Image as _PILImage

        first_prompt = req.prompts[0]
        assert isinstance(first_prompt, dict), "i2v requires dict-style prompt"
        user_text = first_prompt.get("user_text")
        rendered = first_prompt.get("prompt") or ""
        if not user_text:
            user_text = _extract_user_instruction(rendered)
        mm_data = first_prompt.get("multi_modal_data") or {}
        image_input = mm_data.get("first_frame")
        if image_input is None:
            raise ValueError("i2v requires multi_modal_data.first_frame.")
        if isinstance(image_input, _PILImage.Image):
            image_raw = _np.array(image_input.convert("RGB"))
        elif isinstance(image_input, str):
            image_raw = _np.array(_PILImage.open(image_input).convert("RGB"))
        elif isinstance(image_input, _np.ndarray):
            image_raw = image_input if image_input.ndim == 3 else image_input.squeeze()
        else:
            raise ValueError(f"Unsupported first_frame type {type(image_input)}")
        video_raw = image_raw[None]
        extra_args = first_prompt.get("extra_args") or {}
        sp_extra = getattr(req.sampling_params, "extra_args", {}) or {}
        extra_args = {**extra_args, **sp_extra}
        num_frames_out = int(extra_args.get("num_frames", 61))
        out_H = int(extra_args.get("video_height", 480))
        out_W = int(extra_args.get("video_width", 848))
        origin_fps = float(extra_args.get("origin_fps", 24.0))
        cfg_text_scale = float(extra_args.get("cfg_text_scale", 4.0))
        cfg_img_scale = float(extra_args.get("cfg_img_scale", 1.0))
        cfg_interval = tuple(extra_args.get("cfg_interval", (0.4, 1.0)))
        cfg_renorm_type = str(extra_args.get("cfg_renorm_type", "global"))
        cfg_renorm_min = float(extra_args.get("cfg_renorm_min", 0.0))
        timestep_shift = float(
            extra_args.get("timestep_shift", LANCE_DEFAULTS.timestep_shift)
        )
        num_timesteps = int(
            req.sampling_params.num_inference_steps or LANCE_DEFAULTS.num_timesteps
        )
        from .conditioning import LanceBagel as _LanceBagel

        vae_video, _, _, _ = _LanceBagel._lance_video_preprocess(video_raw, origin_fps)
        T_ref = int(vae_video.shape[1])
        H_ref = int(vae_video.shape[2])
        W_ref = int(vae_video.shape[3])
        out_shape = (num_frames_out, out_H, out_W)
        logger.info(
            "Lance i2v: ref image %dx%d → 1-frame VAE %dx%dx%d, target output %dx%dx%d (T,H,W), user_text=%r",
            image_raw.shape[0],
            image_raw.shape[1],
            T_ref,
            H_ref,
            W_ref,
            num_frames_out,
            out_H,
            out_W,
            user_text,
        )
        if req.sampling_params.seed is not None:
            torch.manual_seed(req.sampling_params.seed)
            if self.device.type == "cuda":
                torch.cuda.manual_seed(req.sampling_params.seed)
        gen_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        cfg_text_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        seg1_str, seg5_str = self._segment_strings("i2v", "video")
        self._raw_text_prefill(gen_context, seg1_str)
        if cfg_text_scale > 1.0:
            self._raw_text_prefill(cfg_text_context, seg1_str)
        rope_before_vae = gen_context["ropes"][0]
        cfg_rope_before_vae = (
            cfg_text_context["ropes"][0] if cfg_text_scale > 1.0 else rope_before_vae
        )
        self._raw_text_prefill(gen_context, user_text)
        self._raw_text_prefill(gen_context, seg5_str)
        if cfg_text_scale > 1.0:
            self._raw_text_prefill(cfg_text_context, seg5_str)
        gen_input_lat = self.bagel.prepare_video_latent(
            curr_kvlens=gen_context["kv_lens"],
            curr_rope=[rope_before_vae],
            video_shapes=[out_shape],
            new_token_ids=self.new_token_ids,
        )
        for k, v in gen_input_lat.items():
            if torch.is_tensor(v):
                gen_input_lat[k] = v.to(self.device)
        cfg_text_lat = self.bagel.prepare_video_latent_cfg(
            curr_kvlens=cfg_text_context["kv_lens"],
            curr_rope=[cfg_rope_before_vae],
            video_shapes=[out_shape],
        )
        for k, v in cfg_text_lat.items():
            if torch.is_tensor(v):
                cfg_text_lat[k] = v.to(self.device)
        cfg_img_lat = cfg_text_lat if cfg_img_scale > 1.0 else None
        self._regen_init_noise_on_device(gen_input_lat, req.sampling_params.seed)
        h_lat = int(out_H // self.bagel.latent_downsample)
        w_lat = int(out_W // self.bagel.latent_downsample)
        first_slice_n = h_lat * w_lat
        from torchvision.transforms.functional import resize as _tv_resize

        img_chw = torch.from_numpy(image_raw).permute(2, 0, 1).float() / 127.5 - 1.0
        img_chw = _tv_resize(img_chw, [out_H, out_W], antialias=True)
        full_pixel_tensor = torch.randn(
            (3, num_frames_out, out_H, out_W), dtype=torch.float32, device=self.device
        )
        full_pixel_tensor[:, :4, :, :] = (
            img_chw.to(self.device).unsqueeze(1).repeat(1, 4, 1, 1)
        )
        full_pixel_5d = full_pixel_tensor.unsqueeze(0)
        with torch.autocast(**self._autocast_kwargs()):
            image_latent_5d = self.vae.encode(full_pixel_5d)
        if image_latent_5d.dim() == 5:
            image_latent = image_latent_5d[0, :, 0, :, :]
        elif image_latent_5d.dim() == 4:
            image_latent = image_latent_5d[0]
        else:
            raise RuntimeError(
                f"Unexpected VAE-encoded shape {tuple(image_latent_5d.shape)}"
            )
        image_latent_packed = image_latent.permute(1, 2, 0).reshape(first_slice_n, -1)
        init_noises = gen_input_lat["packed_init_noises"]
        image_latent_packed = image_latent_packed.to(
            device=init_noises.device, dtype=init_noises.dtype
        )
        init_noises[:first_slice_n] = image_latent_packed
        gen_input_lat["packed_init_noises"] = init_noises
        frame_condition_token_indexes = torch.arange(
            first_slice_n, dtype=torch.long, device=self.device
        )
        logger.info(
            "Lance i2v cond: latent grid h_lat=%d w_lat=%d -> pinning first %d tokens (frame 0) at VAE-encoded image",
            h_lat,
            w_lat,
            first_slice_n,
        )
        with torch.autocast(**self._autocast_kwargs()):
            for _drop in (
                "key_values_lens",
                "packed_indexes",
                "packed_key_value_indexes",
            ):
                gen_input_lat.pop(_drop, None)
            latents, *_ = self.bagel.generate_image(
                past_key_values=gen_context["past_key_values"],
                cfg_text_past_key_values=cfg_text_context["past_key_values"]
                if cfg_text_scale > 1.0
                else gen_context["past_key_values"],
                cfg_img_past_key_values=gen_context["past_key_values"],
                num_timesteps=num_timesteps,
                timestep_shift=timestep_shift,
                cfg_text_scale=cfg_text_scale,
                cfg_img_scale=cfg_img_scale,
                cfg_interval=cfg_interval,
                cfg_renorm_type=cfg_renorm_type,
                cfg_renorm_min=cfg_renorm_min,
                **gen_input_lat,
                cfg_text_packed_position_ids=cfg_text_lat["cfg_packed_position_ids"],
                cfg_img_packed_position_ids=cfg_img_lat["cfg_packed_position_ids"]
                if cfg_img_lat is not None
                else None,
                frame_condition_token_indexes=frame_condition_token_indexes,
            )
        frames_np = self._decode_video_from_latent(
            self.bagel, self.vae, latents[0], out_shape
        )
        frames = [Image.fromarray(f) for f in frames_np]
        return DiffusionOutput(
            output={
                "payload": {"video": frames},
                "metadata": {"video": {"shape": out_shape}},
            },
            stage_durations=self.stage_durations
            if hasattr(self, "stage_durations")
            else None,
        )

    def _forward_video_edit(self, req):
        """Video edit: reference video + text prompt → modified video.

        Mirrors :meth:`_forward_image_edit`'s segmented prefill layout with
        a temporal axis threaded through both prefill and the gen latent.
        Verified against upstream Lance's ``Lance.validation_gen_KVcache`` for
        ``--task video_edit --resolution video_480p``:

          seg1 (causal, modality=system_prompt):
              ``<|im_start|>system\\n{sys}<|im_end|>\\n<|im_start|>user\\n``
          seg2 (full,   modality=ref_vit):
              ViT(video) — ref video through Qwen2.5-VL ViT, t-axis +1000
          seg3 (full_noise, modality=ref_source):
              VAE(video) — ref video through Wan2.2 VAE, time_embed(t=0).
              Rope shares range with the gen noise latent (modality 1==2
              trick) so the model can align ref↔output per ``(t,h,w)``.
          seg4 (causal, modality=text):  the user instruction
          seg5 (causal, modality=system_prompt):
              ``<|im_end|>\\n<|im_start|>assistant\\n``
          seg6 (noise QUERY): 3-D gen latent at the SAME rope as seg3.

        cfg_text_context skips ONLY seg4 (user text), matching upstream's
        ``uncond_split_pro_kvcache``.  cfg_img defaults to off
        (``cfg_img_scale=1.0`` → upstream's ``cfg_vit_scale=1.0``).

        Replaces the previous shifted-rope layout (``_EDIT_SHIFT=10000``)
        which kept ViT/text at a far-away rope range — that caused 15.5%
        rel_l2 divergence at layer 0 output (cond) vs upstream because the
        noise query attended to a cached K/V at rope (0..47) while upstream
        attends at rope (111..159).
        """
        import numpy as _np

        first_prompt = req.prompts[0]
        assert isinstance(first_prompt, dict), "video_edit requires dict-style prompt"
        user_text = first_prompt.get("user_text")
        rendered = first_prompt.get("prompt") or ""
        if not user_text:
            user_text = _extract_user_instruction(rendered)
        mm_data = first_prompt.get("multi_modal_data") or {}
        video_input = mm_data.get("video")
        if video_input is None:
            raise ValueError("video_edit requires multi_modal_data.video.")
        extra_args = first_prompt.get("extra_args") or {}
        sp_extra = getattr(req.sampling_params, "extra_args", {}) or {}
        extra_args = {**extra_args, **sp_extra}
        origin_fps_default = float(extra_args.get("origin_fps", 24.0))
        if isinstance(video_input, str):
            try:
                import decord as _decord
                from decord import VideoReader as _VideoReader

                vr = _VideoReader(video_input, ctx=_decord.cpu(0))
                origin_fps = float(vr.get_avg_fps()) or origin_fps_default
                idx_all = list(range(len(vr)))
                video_raw = vr.get_batch(idx_all).asnumpy()
            except ImportError:
                import cv2 as _cv2

                cap = _cv2.VideoCapture(video_input)
                origin_fps = float(cap.get(_cv2.CAP_PROP_FPS) or origin_fps_default)
                frames_bgr = []
                while True:
                    ok, f = cap.read()
                    if not ok:
                        break
                    frames_bgr.append(_cv2.cvtColor(f, _cv2.COLOR_BGR2RGB))
                cap.release()
                video_raw = _np.stack(frames_bgr, axis=0)
        elif isinstance(video_input, (list, tuple)):
            video_raw = _np.stack([_np.asarray(frame) for frame in video_input])
            origin_fps = origin_fps_default
        elif isinstance(video_input, _np.ndarray):
            video_raw = video_input
            origin_fps = origin_fps_default
        elif torch.is_tensor(video_input):
            arr = video_input.detach().cpu().numpy()
            if arr.max() <= 1.5:
                arr = (arr * 255.0).clip(0, 255).astype(_np.uint8)
            video_raw = arr
            origin_fps = origin_fps_default
        else:
            raise ValueError(f"Unsupported video_input type {type(video_input)}")
        cfg_text_scale = float(extra_args.get("cfg_text_scale", 4.0))
        cfg_img_scale = float(extra_args.get("cfg_img_scale", 1.0))
        cfg_interval = tuple(extra_args.get("cfg_interval", (0.0, 1.0)))
        cfg_renorm_type = str(extra_args.get("cfg_renorm_type", "global"))
        cfg_renorm_min = float(extra_args.get("cfg_renorm_min", 0.0))
        timestep_shift = float(
            extra_args.get("timestep_shift", LANCE_DEFAULTS.timestep_shift)
        )
        num_timesteps = int(
            req.sampling_params.num_inference_steps or LANCE_DEFAULTS.num_timesteps
        )
        from .conditioning import LanceBagel as _LanceBagel

        vae_video, vit_pixels, vit_grid_thw, sampled_T = (
            _LanceBagel._lance_video_preprocess(video_raw, origin_fps)
        )
        video_chw = vae_video
        T_sampled = int(video_chw.shape[1])
        H_vae = int(video_chw.shape[2])
        W_vae = int(video_chw.shape[3])
        video_shape = (T_sampled, H_vae, W_vae)
        logger.info(
            "Lance video_edit: input %dx%dx%d → sampled %dx%dx%d (T,H,W) @ %.2ffps, ViT grid_thw=%s, user_text=%r",
            video_raw.shape[0],
            video_raw.shape[1],
            video_raw.shape[2],
            T_sampled,
            H_vae,
            W_vae,
            origin_fps,
            tuple(vit_grid_thw[0].tolist()),
            user_text,
        )
        if req.sampling_params.seed is not None:
            torch.manual_seed(req.sampling_params.seed)
            if self.device.type == "cuda":
                torch.cuda.manual_seed(req.sampling_params.seed)
        gen_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        cfg_text_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        ref_latent_cache: list = []

        def _vae_transforms(_):
            return video_chw

        seg1_str, seg5_str = self._segment_strings("video_edit", "video")
        self._raw_text_prefill(gen_context, seg1_str)
        if cfg_text_scale > 1.0:
            self._raw_text_prefill(cfg_text_context, seg1_str)
        precomputed_vit = [(vit_pixels, vit_grid_thw)]
        self._vit_video_prefill(
            gen_context, [video_raw], precomputed_vit=precomputed_vit
        )
        if cfg_text_scale > 1.0:
            self._vit_video_prefill(
                cfg_text_context, [video_raw], precomputed_vit=precomputed_vit
            )
        rope_before_vae = gen_context["ropes"][0]
        cfg_rope_before_vae = (
            cfg_text_context["ropes"][0] if cfg_text_scale > 1.0 else rope_before_vae
        )
        self._vae_ref_prefill(
            gen_context,
            [video_chw],
            _vae_transforms,
            is_video=True,
            latent_cache=ref_latent_cache,
        )
        if cfg_text_scale > 1.0:
            self._vae_ref_prefill(
                cfg_text_context,
                [video_chw],
                _vae_transforms,
                is_video=True,
                latent_cache=ref_latent_cache,
            )
        self._raw_text_prefill(gen_context, user_text)
        self._raw_text_prefill(gen_context, seg5_str)
        if cfg_text_scale > 1.0:
            self._raw_text_prefill(cfg_text_context, seg5_str)
        gen_input_lat = self.bagel.prepare_video_latent(
            curr_kvlens=gen_context["kv_lens"],
            curr_rope=[rope_before_vae],
            video_shapes=[video_shape],
            new_token_ids=self.new_token_ids,
        )
        for k, v in gen_input_lat.items():
            if torch.is_tensor(v):
                gen_input_lat[k] = v.to(self.device)
        cfg_text_lat = self.bagel.prepare_video_latent_cfg(
            curr_kvlens=cfg_text_context["kv_lens"],
            curr_rope=[cfg_rope_before_vae],
            video_shapes=[video_shape],
        )
        for k, v in cfg_text_lat.items():
            if torch.is_tensor(v):
                cfg_text_lat[k] = v.to(self.device)
        cfg_img_lat = cfg_text_lat if cfg_img_scale > 1.0 else None
        self._regen_init_noise_on_device(gen_input_lat, req.sampling_params.seed)
        with torch.autocast(**self._autocast_kwargs()):
            for _drop in (
                "key_values_lens",
                "packed_indexes",
                "packed_key_value_indexes",
            ):
                gen_input_lat.pop(_drop, None)
            latents, *_ = self.bagel.generate_image(
                past_key_values=gen_context["past_key_values"],
                cfg_text_past_key_values=cfg_text_context["past_key_values"]
                if cfg_text_scale > 1.0
                else gen_context["past_key_values"],
                cfg_img_past_key_values=gen_context["past_key_values"],
                num_timesteps=num_timesteps,
                timestep_shift=timestep_shift,
                cfg_text_scale=cfg_text_scale,
                cfg_img_scale=cfg_img_scale,
                cfg_interval=cfg_interval,
                cfg_renorm_type=cfg_renorm_type,
                cfg_renorm_min=cfg_renorm_min,
                **gen_input_lat,
                cfg_text_packed_position_ids=cfg_text_lat["cfg_packed_position_ids"],
                cfg_img_packed_position_ids=cfg_img_lat["cfg_packed_position_ids"]
                if cfg_img_lat is not None
                else None,
            )
        frames_np = self._decode_video_from_latent(
            self.bagel, self.vae, latents[0], video_shape
        )
        frames = [Image.fromarray(f) for f in frames_np]
        return DiffusionOutput(
            output={
                "payload": {"video": frames},
                "metadata": {"video": {"shape": video_shape}},
            },
            stage_durations=self.stage_durations
            if hasattr(self, "stage_durations")
            else None,
        )

    @torch.inference_mode()
    def _forward_x2t_video(self, req):
        """Video understanding (x2t_video): video → text caption / VQA answer.

        Builds the prefill in three segments matching upstream's chat
        template — see :meth:`_forward_x2t_image` for the rationale on
        why naïve concatenation (text prompt → ViT) lands the EOS / vit
        markers in the wrong place and degrades the answer format.
        """
        first_prompt = req.prompts[0]
        assert isinstance(first_prompt, dict), "x2t_video requires dict-style prompt"
        video_input = (first_prompt.get("multi_modal_data") or {}).get("video")
        if video_input is None:
            raise ValueError(
                "x2t_video requires multi_modal_data.video to be a video tensor/array/path."
            )
        if isinstance(video_input, str):
            import imageio.v3 as iio

            video_input = iio.imread(video_input)
        videos = [video_input]
        extra_args = first_prompt.get("extra_args") or {}
        sp_extra = getattr(req.sampling_params, "extra_args", {}) or {}
        extra_args = {**extra_args, **sp_extra}
        max_text_tokens = int(extra_args.get("max_think_tokens", 200))
        do_sample = bool(extra_args.get("do_sample", False))
        text_temperature = float(extra_args.get("text_temperature", 0.3))
        prefix_text, suffix_text = self._split_x2t_prompt(
            first_prompt.get("prompt") or "",
            user_text_override=extra_args.get("user_text"),
            system_prompt_override=extra_args.get("system_prompt"),
            default_system_prompt="Watch the video carefully and answer the question.",
        )
        if req.sampling_params.seed is not None:
            torch.manual_seed(req.sampling_params.seed)
            if self.device.type == "cuda":
                torch.cuda.manual_seed(req.sampling_params.seed)
        gen_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        self._raw_text_prefill(gen_context, prefix_text)
        self._vit_video_prefill(gen_context, videos)
        self._raw_text_prefill(gen_context, suffix_text)
        start_input = self._x2t_prepare_assistant_start(gen_context)
        for k, v in start_input.items():
            if torch.is_tensor(v):
                start_input[k] = v.to(self.device)
        with torch.autocast(**self._autocast_kwargs()):
            token_ids = self.bagel.generate_text(
                past_key_values=gen_context["past_key_values"],
                max_length=max_text_tokens,
                do_sample=do_sample,
                temperature=text_temperature,
                end_token_id=self.new_token_ids["eos_token_id"],
                **start_input,
            )
        decoded = self.tokenizer.decode(token_ids[:, 0].tolist())
        text_output = decoded.split("<|im_end|>")[0]
        if "<|im_start|>" in text_output:
            text_output = text_output.split("<|im_start|>")[-1]
        text_output = text_output.lstrip("\n")
        logger.info("Lance x2t_video: generated %d tokens", token_ids.shape[0])
        return DiffusionOutput(
            output={
                "payload": {"text": text_output},
                "metadata": {"text": {"text_output": text_output}},
            },
            stage_durations=self.stage_durations
            if hasattr(self, "stage_durations")
            else None,
        )

    @torch.inference_mode()
    def _forward_x2t_image(self, req):
        """Image understanding (x2t_image): image + question → text answer.

        Builds the prefill in three text/vit segments matching upstream's
        chat-template layout::

            <|im_start|>system\\n{system}<|im_end|>\\n<|im_start|>user\\n
            <|vision_start|>{N×ViT}<|vision_end|>
            {question}<|im_end|>\\n<|im_start|>assistant\\n

        ``prepare_prompts`` wraps the *whole* string with ``[bos]…[eos]``
        and ``prepare_vit_images`` adds ``<|vision_start|>``/``<|vision_end|>``
        of its own — concatenating them naïvely (text first, then vit)
        produced ``…assistant\\n[eos]<|vision_start|>{ViT}<|vision_end|>``,
        so the model saw an EOS right after the assistant tag and a
        bare ``<|video_pad|>`` token inside the user message.  Segmenting
        the text into prefix/suffix and sliding the vit prefill between
        them puts the markers exactly where Lance was trained on.
        """
        from PIL import Image as _PIL_Image

        first_prompt = req.prompts[0]
        assert isinstance(first_prompt, dict), "x2t_image requires dict-style prompt"
        image_input = (first_prompt.get("multi_modal_data") or {}).get("image")
        if image_input is None:
            raise ValueError(
                "x2t_image requires multi_modal_data.image to be a PIL image / array / path."
            )
        if isinstance(image_input, str):
            image_input = _PIL_Image.open(image_input).convert("RGB")
        images = [image_input]
        extra_args = first_prompt.get("extra_args") or {}
        sp_extra = getattr(req.sampling_params, "extra_args", {}) or {}
        extra_args = {**extra_args, **sp_extra}
        max_text_tokens = int(extra_args.get("max_think_tokens", 256))
        do_sample = bool(extra_args.get("do_sample", False))
        text_temperature = float(extra_args.get("text_temperature", 0.3))
        prefix_text, suffix_text = self._split_x2t_prompt(
            first_prompt.get("prompt") or "",
            user_text_override=extra_args.get("user_text"),
            system_prompt_override=extra_args.get("system_prompt"),
            default_system_prompt="Look at the image carefully and answer the question.",
        )
        if req.sampling_params.seed is not None:
            torch.manual_seed(req.sampling_params.seed)
            if self.device.type == "cuda":
                torch.cuda.manual_seed(req.sampling_params.seed)

        def vit_transforms(img):
            return self.image_processor(images=img, return_tensors="pt").pixel_values[0]

        gen_context = {
            "kv_lens": [0],
            "ropes": [0],
            "past_key_values": NaiveCache(
                self.bagel.config.llm_config.num_hidden_layers
            ),
        }
        self._raw_text_prefill(gen_context, prefix_text)
        self._vit_image_prefill(gen_context, images, vit_transforms)
        self._raw_text_prefill(gen_context, suffix_text)
        start_input = self._x2t_prepare_assistant_start(gen_context)
        for k, v in start_input.items():
            if torch.is_tensor(v):
                start_input[k] = v.to(self.device)
        with torch.autocast(**self._autocast_kwargs()):
            token_ids = self.bagel.generate_text(
                past_key_values=gen_context["past_key_values"],
                max_length=max_text_tokens,
                do_sample=do_sample,
                temperature=text_temperature,
                end_token_id=self.new_token_ids["eos_token_id"],
                **start_input,
            )
        decoded = self.tokenizer.decode(token_ids[:, 0].tolist())
        text_output = decoded.split("<|im_end|>")[0]
        if "<|im_start|>" in text_output:
            text_output = text_output.split("<|im_start|>")[-1]
        text_output = text_output.lstrip("\n")
        logger.info("Lance x2t_image: generated %d tokens", token_ids.shape[0])
        return DiffusionOutput(
            output={
                "payload": {"text": text_output},
                "metadata": {"text": {"text_output": text_output}},
            },
            stage_durations=self.stage_durations
            if hasattr(self, "stage_durations")
            else None,
        )

    @staticmethod
    def _split_x2t_prompt(
        rendered_prompt: str,
        *,
        user_text_override: str | None,
        system_prompt_override: str | None,
        default_system_prompt: str,
    ) -> tuple[str, str]:
        """Split a rendered Lance x2t chat template at the vision block.

        Accepts either a pre-rendered template containing
        ``<|vision_start|>…<|vision_end|>`` (the historical
        ``render_lance_prompt`` output) or recovers prefix/suffix from
        ``user_text_override`` + ``system_prompt_override`` when the
        template was not pre-rendered.  Returns ``(prefix, suffix)`` such
        that the segmented prefill is ``prefix + ViT + suffix``.

        ``suffix`` deliberately ends at ``assistant`` (NOT ``assistant\\n``):
        :meth:`Bagel.prepare_start_tokens` injects ``<|im_start|>`` (Qwen
        bos == 151644) as the first generation step, and ``\\n<|im_start|>``
        right after ``assistant\\n`` tells the model "begin a new
        message" — it answers with an immediate ``<|im_end|>`` and
        produces an empty caption.  Holding the trailing ``\\n`` out of
        the prefill (it gets re-applied via ``_x2t_prepare_assistant_start``)
        lets the next forward step start *inside* the assistant turn
        instead of opening a fresh one.
        """
        sys_prompt = system_prompt_override or default_system_prompt
        if user_text_override is not None:
            user_text = user_text_override
        elif (
            "<|vision_start|>" in rendered_prompt
            and "<|vision_end|>" in rendered_prompt
        ):
            _, _, after_vis_end = rendered_prompt.partition("<|vision_end|>")
            user_text, _, _ = after_vis_end.partition("<|im_end|>")
        else:
            user_text = rendered_prompt
        prefix = f"<|im_start|>system\n{sys_prompt}<|im_end|>\n<|im_start|>user\n"
        suffix = f"{user_text}<|im_end|>\n<|im_start|>assistant"
        return (prefix, suffix)

    def _x2t_prepare_assistant_start(self, gen_context):
        """Build a ``generate_text`` start input where the first fed token
        is the newline that closes ``<|im_start|>assistant\\n``.

        :meth:`Bagel.prepare_start_tokens` would instead feed
        ``<|im_start|>``, opening a fresh message right after the
        assistant tag and triggering an immediate EOS on Lance_3B (the
        image-only checkpoint is stricter about chat-turn framing than
        the video model, which happens to recover).  Feeding ``\\n``
        keeps the model *inside* the assistant turn so the next argmax
        is the first answer token.
        """
        newline_ids = self.tokenizer.encode("\n", add_special_tokens=False)
        assert len(newline_ids) == 1, (
            f"expected single token for '\\n', got {newline_ids!r}"
        )
        nl_id = newline_ids[0]
        curr_kvlens = gen_context["kv_lens"]
        curr_ropes = gen_context["ropes"]
        packed_key_value_indexes: list[int] = []
        packed_query_position_ids: list[int] = []
        packed_start_tokens: list[int] = []
        curr = 0
        for curr_kvlen, curr_position_id in zip(curr_kvlens, curr_ropes):
            packed_key_value_indexes.extend(range(curr, curr + curr_kvlen))
            packed_start_tokens.append(nl_id)
            packed_query_position_ids.append(curr_position_id)
            curr += curr_kvlen
        return {
            "packed_start_tokens": torch.tensor(packed_start_tokens, dtype=torch.long),
            "packed_query_position_ids": torch.tensor(
                packed_query_position_ids, dtype=torch.long
            ),
        }

    @staticmethod
    def _decode_video_from_latent(
        bagel, vae: LanceWanVAE, latent: torch.Tensor, video_shape: tuple[int, int, int]
    ):
        """Pack a flat Lance latent into ``(B, 48, t, h, w)`` and decode to a
        ``(T_lat, H, W, 3)`` numpy frame list via :meth:`LanceWanVAE.decode_video`.
        """
        T, H, W = video_shape
        downsample_t = int(getattr(bagel.config.vae_config, "downsample_temporal", 4))
        t_lat = (T - 1) // downsample_t + 1
        h_lat = H // bagel.latent_downsample
        w_lat = W // bagel.latent_downsample
        p = bagel.latent_patch_size
        c = bagel.latent_channel
        latent = latent.reshape(t_lat, h_lat, w_lat, p, p, c)
        latent = torch.einsum("thwpqc->cthpwq", latent)
        latent = latent.reshape(1, c, t_lat, h_lat * p, w_lat * p)
        vae_dtype = next(vae.parameters()).dtype
        latent = latent.to(vae_dtype)
        video = vae.decode_video(latent)
        video = (video[0] * 0.5 + 0.5).clamp(0, 1).permute(1, 2, 3, 0) * 255
        return video.to(torch.uint8).cpu().numpy()

    @staticmethod
    def _decode_image_from_latent(
        bagel, vae: LanceWanVAE, latent: torch.Tensor, image_shape: tuple[int, int]
    ) -> Image.Image:
        H, W = image_shape
        h, w = (H // bagel.latent_downsample, W // bagel.latent_downsample)
        p = bagel.latent_patch_size
        c = bagel.latent_channel
        latent = latent.reshape(1, h, w, p, p, c)
        latent = torch.einsum("nhwpqc->nchpwq", latent)
        latent = latent.reshape(1, c, h * p, w * p)
        vae_dtype = next(vae.parameters()).dtype
        latent = latent.to(vae_dtype)
        image = vae.decode(latent)
        image = (image * 0.5 + 0.5).clamp(0, 1)[0].permute(1, 2, 0) * 255
        return Image.fromarray(image.to(torch.uint8).cpu().numpy())

    def _regen_init_noise_on_device(self, gen_input: dict, seed: int | None) -> None:
        """Resample ``gen_input["packed_init_noises"]`` on-device with a fresh
        per-call ``torch.Generator``.

        ``Bagel.prepare_input`` (and the Lance video equivalent) call
        ``torch.randn`` with no device or generator, falling back to CPU+fp32
        via the global RNG.  Upstream Lance samples directly on CUDA+bf16 via
        ``torch.Generator(device=cuda).manual_seed(seed)`` (lance.py:1536),
        so for the same seed the two sides land on different noise streams.
        Mutates ``gen_input`` in place; no-op if seed is unset or device is CPU.
        """
        if seed is None or self.device.type != "cuda":
            return
        ref = gen_input["packed_init_noises"]
        gen_input["packed_init_noises"] = torch.randn(
            ref.shape,
            generator=torch.Generator(device=self.device).manual_seed(int(seed)),
            device=self.device,
            dtype=self.od_config.dtype,
        )
