# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# Copyright contributors to the vLLM-Omni project.
# SPDX-License-Identifier: Apache-2.0
"""Native Lance pipeline with mandatory, selectable quantization support."""

import gc
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image

from .inference import InferenceMixin
from .model import LanceConfig
from .prompts import render_lance_prompt
from .quantization import QUANTIZATION_MODES, storage_bytes


@dataclass
class LanceOutput:
    images: list[Image.Image] = field(default_factory=list)
    frames: list[Image.Image] = field(default_factory=list)
    text: str = ""


class _VideoProcessor:
    def __init__(self, processor):
        self.processor = processor

    def __call__(self, *, videos, **kwargs):
        return self.processor.preprocess(images=None, videos=videos, **kwargs)


class LancePipeline(InferenceMixin):
    TASKS = ("t2i", "image_edit", "t2v", "i2v", "video_edit", "x2t_image", "x2t_video")
    _STALE_PREFILL_KEYS = (
        "packed_indexes",
        "packed_key_value_indexes",
        "key_values_lens",
    )
    # Inherited task paths use torch's global RNG; serialize calls across instances.
    _inference_lock = threading.RLock()

    @classmethod
    def from_pretrained(
        cls,
        model_path="bytedance-research/Lance",
        *,
        variant="image",
        quantization="nf4",
        quantize_vision=False,
        device=None,
        torch_dtype=None,
        revision=None,
    ):
        from transformers import Qwen2TokenizerFast, Qwen2VLImageProcessor
        from .conditioning import LanceQwen2_5_VLNaViTWrapper
        from .loading import BundleReader, load_streamed, resolve_bundle
        from .transformer import LanceTransformer
        from .vision import Qwen2_5_VisionTransformerPretrainedModel
        from .wan_vae import LanceWanVAE

        if quantization not in QUANTIZATION_MODES:
            raise ValueError(f"Unsupported quantization: {quantization}")
        device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        dtype = torch_dtype or (
            torch.bfloat16 if device.type == "cuda" else torch.float32
        )
        if dtype not in (torch.float32, torch.float16, torch.bfloat16):
            raise ValueError("Compute dtype must be float32, float16 or bfloat16")
        if (
            device.type == "cuda"
            and dtype == torch.bfloat16
            and not torch.cuda.is_bf16_supported()
        ):
            raise ValueError(
                "This CUDA GPU does not support BF16; select torch_dtype=torch.float16"
            )
        root, ckpt = resolve_bundle(model_path, variant=variant, revision=revision)
        reader = BundleReader(ckpt, root / "Qwen2.5-VL-ViT")
        llm_config = LanceConfig(**json.loads((ckpt / "llm_config.json").read_text()))
        # Original inference_lance.sh enables both Q/K norm expert branches.
        llm_config.qk_norm = llm_config.qk_norm_und = llm_config.qk_norm_gen = True
        vit_values = json.loads((root / "Qwen2.5-VL-ViT" / "config.json").read_text())
        vit_values["_attn_implementation"] = "sdpa"
        rows, hidden = reader.shape("latent_pos_embed.pos_embed")
        if hidden != llm_config.hidden_size or rows % 4096:
            raise ValueError("Unsupported Lance latent position table")
        # Meta construction avoids allocating a second full floating model.
        with torch.device("meta"):
            vision = Qwen2_5_VisionTransformerPretrainedModel(
                SimpleNamespace(**vit_values)
            )
            wrapped_vision = LanceQwen2_5_VLNaViTWrapper(
                vision, spatial_merge_size=vit_values.get("spatial_merge_size", 2)
            )
            model = LanceTransformer(
                llm_config, position_rows=rows, vit_model=wrapped_vision
            )
        count = load_streamed(
            model,
            reader,
            quantization=quantization,
            device=device,
            dtype=dtype,
            quantize_vision=quantize_vision,
        )
        # Lance_3B ships tokenizer.json/vocab/merges but no config.json or
        # tokenizer_config.json. AutoTokenizer cannot infer its model class.
        tokenizer = Qwen2TokenizerFast.from_pretrained(str(ckpt), local_files_only=True)
        special = {
            "bos_token_id": "<|im_start|>",
            "eos_token_id": "<|im_end|>",
            "start_of_image": "<|vision_start|>",
            "end_of_image": "<|vision_end|>",
        }
        token_ids = {
            name: tokenizer.convert_tokens_to_ids(token)
            for name, token in special.items()
        }
        if any(
            value is None
            or value == tokenizer.unk_token_id
            or not 0 <= value < llm_config.vocab_size
            for value in token_ids.values()
        ):
            raise ValueError("Lance tokenizer lacks valid checkpoint framing tokens")
        processor = Qwen2VLImageProcessor()
        model._lance_image_processor = processor
        # Older transformers combines image/video processing in this class.
        model._lance_video_processor = _VideoProcessor(processor)
        instance = cls()
        instance.bagel, instance.tokenizer = model, tokenizer
        instance.image_processor = processor
        instance.new_token_ids = token_ids
        instance.vae = LanceWanVAE(
            str(root / "Wan2.2_VAE.pth"), dtype=dtype, device=device
        )
        instance.device, instance.dtype = device, dtype
        instance.od_config = SimpleNamespace(dtype=dtype)
        instance.variant, instance.quantization = variant, quantization
        instance.quantized_linear_count = count
        instance.weight_bytes = storage_bytes(model) + storage_bytes(instance.vae)
        return instance

    def _autocast_kwargs(self):
        return dict(
            device_type=self.device.type,
            dtype=self.dtype,
            enabled=self.device.type != "cpu" and self.dtype != torch.float32,
        )

    def unload(self):
        """Release all model references, including packed weights and VAE caches."""
        with self._inference_lock:
            self.bagel = None
            self.vae = None
            self.tokenizer = None
            self.image_processor = None
            gc.collect()
            if self.device.type == "cuda":
                with torch.cuda.device(self.device):
                    torch.cuda.empty_cache()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.unload()

    @torch.inference_mode()
    def __call__(
        self,
        prompt="",
        *,
        task="t2i",
        image=None,
        video=None,
        width=768,
        height=768,
        num_frames=61,
        num_inference_steps=30,
        guidance_scale=4.0,
        seed=42,
        negative_prompt="",
        timestep_shift=3.5,
        max_new_tokens=256,
        do_sample=True,
        temperature=0.8,
        origin_fps=12.0,
    ):
        if self.bagel is None:
            raise RuntimeError("Lance pipeline has been unloaded")
        if task not in self.TASKS:
            raise ValueError(f"Unsupported Lance task: {task}")
        video_task = task in ("t2v", "i2v", "video_edit", "x2t_video")
        if video_task and self.variant != "video":
            raise ValueError(
                "Video tasks require variant='video' and Lance_3B_Video weights"
            )
        if (
            width % 16
            or height % 16
            or not 16 <= width <= 1024
            or not 16 <= height <= 1024
        ):
            raise ValueError("Width/height must be multiples of 16 between 16 and 1024")
        if video_task and (not 1 <= num_frames <= 121 or (num_frames - 1) % 4):
            raise ValueError("num_frames must be 4n+1, between 1 and 121")
        if task == "i2v" and num_frames < 5:
            raise ValueError("i2v requires at least 5 frames")
        if num_inference_steps < 1 or timestep_shift <= 0 or guidance_scale < 1:
            raise ValueError(
                "steps/shift must be positive and guidance_scale must be >= 1"
            )
        if max_new_tokens < 1 or temperature <= 0 or origin_fps <= 0:
            raise ValueError(
                "max_new_tokens, temperature and origin_fps must be positive"
            )
        if task in ("image_edit", "i2v", "x2t_image") and image is None:
            raise ValueError(f"{task} requires an image")
        if task in ("video_edit", "x2t_video") and video is None:
            raise ValueError(f"{task} requires a video")
        if isinstance(image, (str, Path)):
            with Image.open(image) as opened:
                image = opened.convert("RGB")
        if image is not None and not isinstance(image, Image.Image):
            raise TypeError("image must be a PIL image or path")
        if isinstance(video, Path):
            video = str(video)
        if isinstance(video, list):
            video = np.stack(
                [
                    np.asarray(frame.convert("RGB"))
                    if isinstance(frame, Image.Image)
                    else frame
                    for frame in video
                ]
            )
        extras = dict(
            num_frames=num_frames,
            video_width=width,
            video_height=height,
            cfg_text_scale=guidance_scale,
            cfg_img_scale=1.0,
            negative_prompt=negative_prompt,
            timestep_shift=timestep_shift,
            max_think_tokens=max_new_tokens,
            do_sample=do_sample,
            text_temperature=temperature,
            origin_fps=origin_fps,
            user_text=prompt,
        )
        request = SimpleNamespace(
            prompts=[
                dict(
                    prompt=prompt,
                    user_text=prompt,
                    multi_modal_data=dict(image=image, first_frame=image, video=video),
                    extra_args=extras,
                )
            ],
            sampling_params=SimpleNamespace(
                height=height,
                width=width,
                seed=seed,
                num_inference_steps=num_inference_steps,
                extra_args=extras,
            ),
        )
        # torch.manual_seed also touches CUDA RNGs even for CPU inference.
        devices = (
            list(range(torch.cuda.device_count())) if torch.cuda.is_available() else []
        )
        with self._inference_lock, torch.random.fork_rng(devices=devices):
            # Recheck under the same lock used by unload().
            if self.bagel is None:
                raise RuntimeError("Lance pipeline has been unloaded")
            if seed is not None:
                torch.manual_seed(seed)
            with torch.autocast(**self._autocast_kwargs()):
                if task in ("t2i", "t2v"):
                    return self._generate(
                        prompt,
                        task,
                        width,
                        height,
                        num_frames,
                        num_inference_steps,
                        guidance_scale,
                        seed,
                        negative_prompt,
                        timestep_shift,
                    )
                output = getattr(self, "_forward_" + task)(request).output["payload"]
        return LanceOutput(
            images=[output["image"]] if "image" in output else [],
            frames=output.get("video", []),
            text=output.get("text", ""),
        )

    def _generate(
        self,
        prompt,
        task,
        width,
        height,
        frames,
        steps,
        guidance,
        seed,
        negative,
        shift,
    ):
        positive, unconditional = self._new_gen_context(), self._new_gen_context()
        self._raw_text_prefill(positive, render_lance_prompt(task, prompt))
        if guidance > 1:
            self._raw_text_prefill(unconditional, render_lance_prompt(task, negative))
        if task == "t2i":
            inputs = self.bagel.prepare_vae_latent(
                positive["kv_lens"],
                positive["ropes"],
                [(height, width)],
                self.new_token_ids,
            )
            cfg = self.bagel.prepare_vae_latent_cfg(
                unconditional["kv_lens"], unconditional["ropes"], [(height, width)]
            )
        else:
            inputs = self.bagel.prepare_video_latent(
                positive["kv_lens"],
                positive["ropes"],
                [(frames, height, width)],
                self.new_token_ids,
            )
            cfg = self.bagel.prepare_video_latent_cfg(
                unconditional["kv_lens"],
                unconditional["ropes"],
                [(frames, height, width)],
            )
        for key in self._STALE_PREFILL_KEYS:
            inputs.pop(key, None)
        inputs = {
            k: v.to(self.device) if torch.is_tensor(v) else v for k, v in inputs.items()
        }
        self._regen_init_noise_on_device(inputs, seed)
        latents, *_ = self.bagel.generate_image(
            **inputs,
            past_key_values=positive["past_key_values"],
            cfg_text_past_key_values=unconditional["past_key_values"],
            cfg_text_packed_position_ids=cfg["cfg_packed_position_ids"].to(self.device),
            cfg_text_scale=guidance,
            num_timesteps=steps,
            timestep_shift=shift,
        )
        if task == "t2i":
            return LanceOutput(
                images=[
                    self._decode_image_from_latent(
                        self.bagel, self.vae, latents[0], (height, width)
                    )
                ]
            )
        decoded = self._decode_video_from_latent(
            self.bagel, self.vae, latents[0], (frames, height, width)
        )
        return LanceOutput(frames=[Image.fromarray(frame) for frame in decoded])
