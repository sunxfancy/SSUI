# Copyright 2025 ByteDance Ltd. and/or its affiliates.
# Copyright contributors to the vLLM-Omni project.
# SPDX-License-Identifier: Apache-2.0
# Adapted for SSUI: standalone PyTorch, no vLLM runtime or distributed workers.
from __future__ import annotations
import numpy as np
import torch
from torch import nn
from .base import Bagel
from .geometry import get_1d_sincos_pos_embed_from_grid

LANCE_TOKENS_PER_SECOND = 2

LANCE_SECONDS_PER_GRID = 1.0

LANCE_VIT_BUCKET_RESOLUTION = 672

LANCE_VIT_BUCKET_STRIDE = 16

LANCE_VIT_DIVISIBLE_CROP = 28

LANCE_VIT_ASPECT_RATIOS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")

LANCE_VIDEO_VAE_RESOLUTION = 640

LANCE_VIDEO_VAE_DIVISIBLE_CROP = 16

LANCE_VIDEO_VIT_RESOLUTION = 616

LANCE_VIDEO_VIT_DIVISIBLE_CROP = 28

LANCE_VIDEO_BUCKET_STRIDE = 16

LANCE_VIDEO_TEMPORAL_STRIDE = 4

LANCE_VIDEO_SAMPLE_FPS = 12

LANCE_VIDEO_MAX_DURATION = 6.0

LANCE_VIT_PATCH_SIZE = 14

LANCE_VIT_TEMPORAL_PATCH_SIZE = 2

LANCE_VIT_SPATIAL_MERGE = 2

LANCE_VIT_NORM_MEAN = (0.48145466, 0.4578275, 0.40821073)

LANCE_VIT_NORM_STD = (0.26862954, 0.26130258, 0.27577711)


def get_3d_sincos_pos_embed_from_grid(embed_dim: int, grid: np.ndarray) -> np.ndarray:
    """3-D sin-cos positional embedding (t, h, w), matching the upstream Lance
    ``modeling/lance/modeling_utils.py`` dimension split exactly."""
    assert embed_dim % 2 == 0, "Embedding dimension must be even for 3D embeddings"
    d = embed_dim // 3
    d = d if d % 2 == 0 else d - 1
    dim_t, dim_h = (d, d)
    dim_w = embed_dim - 2 * d
    assert dim_w % 2 == 0
    emb_t = get_1d_sincos_pos_embed_from_grid(dim_t, grid[0])
    emb_h = get_1d_sincos_pos_embed_from_grid(dim_h, grid[1])
    emb_w = get_1d_sincos_pos_embed_from_grid(dim_w, grid[2])
    return np.concatenate([emb_t, emb_h, emb_w], axis=1)


def get_3d_sincos_pos_embed(embed_dim: int, t: int, h: int, w: int) -> np.ndarray:
    grid_t = np.arange(t, dtype=np.float32)
    grid_h = np.arange(h, dtype=np.float32)
    grid_w = np.arange(w, dtype=np.float32)
    tt, hh, ww = np.meshgrid(grid_t, grid_h, grid_w, indexing="ij")
    grid = np.stack([tt, hh, ww], axis=0)
    return get_3d_sincos_pos_embed_from_grid(embed_dim, grid)


class LancePositionEmbedding3D(nn.Module):
    """Frozen 3-D sin-cos latent position embedding for the video path.

    BAGEL only ships a 2-D ``PositionEmbedding`` (image latents).  Lance's
    ``Lance_3B_Video`` checkpoint adds a temporal axis; this mirrors upstream
    ``modeling/lance/modeling_utils.py::PositionEmbedding3D``.  The image path
    uses ``t=1`` and is numerically equivalent to the 2-D embedding.
    """

    def __init__(
        self, max_num_frames: int, max_num_patch_per_side: int, hidden_size: int
    ):
        super().__init__()
        self.max_num_frames = max_num_frames
        self.max_num_patch_per_side = max_num_patch_per_side
        self.hidden_size = hidden_size
        n = max_num_frames * max_num_patch_per_side * max_num_patch_per_side
        self.pos_embed = nn.Parameter(torch.zeros(n, hidden_size), requires_grad=False)
        self._init_weights()

    def _init_weights(self) -> None:
        pe = get_3d_sincos_pos_embed(
            self.hidden_size,
            self.max_num_frames,
            self.max_num_patch_per_side,
            self.max_num_patch_per_side,
        )
        self.pos_embed.data.copy_(torch.from_numpy(pe).float())

    def forward(self, position_ids: torch.Tensor) -> torch.Tensor:
        return self.pos_embed[position_ids]


class LanceIdentityConnector(nn.Module):
    """No-op connector for Lance.

    BAGEL's ``connector`` projects the ViT hidden size to the LLM hidden size.
    Qwen2.5-VL's vision tower (which Lance uses) already projects to the LLM
    hidden size internally via ``merger`` (``out_hidden_size = hidden_size``),
    and the released Lance safetensors carry no ``connector.*`` weights.  We
    therefore plug in an ``Identity`` connector so ``forward_cache_update_vit``
    keeps its existing call site without a separate code path.
    """

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x


class LanceZeroVitPosEmbed(nn.Module):
    """No-op positional embedding for Lance's ViT tokens.

    BAGEL adds an extra 2-D sin-cos ``vit_pos_embed`` on top of the ViT output.
    Qwen2.5-VL's vision tower already carries its own (rotary) positional
    encoding, and the released Lance safetensors carry no
    ``vit_pos_embed.*`` weights.  This module returns a broadcast-friendly
    zero so the addition in ``forward_cache_update_vit`` is a no-op without
    requiring a code-path branch.
    """

    def forward(self, position_ids: torch.Tensor) -> torch.Tensor:
        return torch.zeros((), device=position_ids.device)


class LanceQwen2_5_VLNaViTWrapper(nn.Module):
    """Packed (NaViT-style) wrapper around the Qwen2.5-VL vision tower.

    Bridges BAGEL's ``vit(packed_pixel_values, ...) -> [num_tokens, vit_hidden]``
    surface to the HF ``Qwen2_5_VisionTransformerPretrainedModel`` which
    consumes ``(hidden_states, grid_thw)``.  The packed call additionally needs
    a per-image ``image_grid_thw`` so non-square images (and the
    spatial-merge token count) line up — :class:`LanceBagel` stashes the grid
    on the wrapper before invoking the ViT.
    """

    def __init__(self, vision_model: nn.Module, spatial_merge_size: int = 2):
        super().__init__()
        self.vision_model = getattr(vision_model, "visual", vision_model)
        self.spatial_merge_size = spatial_merge_size
        self._pending_grid_thw: torch.Tensor | None = None

    @property
    def config(self):
        return self.vision_model.config

    def set_pending_grid_thw(self, grid_thw: torch.Tensor) -> None:
        self._pending_grid_thw = grid_thw

    def forward(
        self,
        packed_pixel_values: torch.Tensor,
        packed_flattened_position_ids: torch.Tensor,
        cu_seqlens: torch.Tensor,
        max_seqlen: int,
    ) -> torch.Tensor:
        if self._pending_grid_thw is not None:
            grid_thw_t = self._pending_grid_thw.to(packed_pixel_values.device)
            self._pending_grid_thw = None
        else:
            cu = cu_seqlens.tolist()
            grid_thw = []
            for i in range(len(cu) - 1):
                n = cu[i + 1] - cu[i]
                side = int(round(float(n) ** 0.5))
                grid_thw.append([1, side, side])
            grid_thw_t = torch.tensor(
                grid_thw, dtype=torch.long, device=packed_pixel_values.device
            )
        hidden = packed_pixel_values
        if hasattr(self.vision_model, "dtype"):
            hidden = hidden.to(self.vision_model.dtype)
        out = self.vision_model(hidden_states=hidden, grid_thw=grid_thw_t)
        if hasattr(out, "pooler_output") and out.pooler_output is not None:
            return out.pooler_output
        if isinstance(out, tuple):
            return out[0]
        return out


class LanceBagel(Bagel):
    """Bagel subclass with Lance-specific ViT handling.

    The released Lance checkpoint pairs BAGEL's Qwen2-MoT trunk with the
    Qwen2.5-VL vision tower (whose ``merger`` already projects to LLM
    ``hidden_size`` and which carries its own rotary positional encoding).
    Two BAGEL assumptions therefore break for Lance:

    1.  ``prepare_vit_images`` calls ``transforms(image) -> (C, H, W)`` and
        then ``patchify(...)``; Lance's image processor returns
        ``(num_patches_flat, patch_features) + image_grid_thw`` already.
    2.  ``forward_cache_update_vit`` adds a ``connector`` projection plus a
        2-D ``vit_pos_embed`` that has no checkpoint weights and would
        also double-count the ViT's own positional encoding.

    This subclass overrides exactly those two methods.  Everything else —
    LLM trunk, VAE flow, generation loop, ``forward_cache_update_text`` /
    ``forward_cache_update_vae`` — is reused unchanged.
    """

    _denoise_schedule_extra_step: bool = True

    @staticmethod
    def _lance_compute_vit_buckets():
        """Replicate upstream Lance's ``BucketResize.init_buckets`` for the ViT path.

        Returns a list of ``((bucket_h, bucket_w), bucket_ratio)`` pairs in the
        same order as :data:`LANCE_VIT_ASPECT_RATIOS`.  Stays in sync with
        upstream lance ``data/video/transforms/bucket_resize.py``.
        """
        import math

        max_area = LANCE_VIT_BUCKET_RESOLUTION * LANCE_VIT_BUCKET_RESOLUTION
        stride = LANCE_VIT_BUCKET_STRIDE
        buckets: list[tuple[tuple[int, int], float]] = []
        for name in LANCE_VIT_ASPECT_RATIOS:
            w_s, h_s = (int(v) for v in name.split(":"))
            aspect = w_s / h_s
            rw1 = math.sqrt(max_area * aspect)
            bw1 = round(rw1 / stride) * stride
            bh1 = round(bw1 / aspect / stride) * stride
            br1 = bw1 / bh1
            rh2 = math.sqrt(max_area / aspect)
            bh2 = round(rh2 / stride) * stride
            bw2 = round(bh2 * aspect / stride) * stride
            br2 = bw2 / bh2
            if abs(br1 - aspect) < abs(br2 - aspect):
                bh, bw = (bh1, bw1)
            elif abs(br1 - aspect) > abs(br2 - aspect):
                bh, bw = (bh2, bw2)
            else:
                area1 = bh1 * bw1
                area2 = bh2 * bw2
                if abs(area1 - max_area) <= abs(area2 - max_area):
                    bh, bw = (bh1, bw1)
                else:
                    bh, bw = (bh2, bw2)
            buckets.append(((bh, bw), bw / bh))
        return buckets

    @staticmethod
    def _lance_bucket_resize_pil(image):
        """Apply upstream Lance's ViT preprocessing to a PIL image.

        Pipeline (matches lance-upstream's ``VideoTransform`` for the ViT path):

        1. ``BucketResize``: pick the aspect-ratio bucket nearest to the input
           and resize via ``RandomResizedCrop(scale=(1,1), ratio=fixed)``,
           which for fixed ratio is a deterministic center-crop + resize.
        2. ``DivisibleCrop(28)``: center-crop to dims divisible by
           ``patch_size * spatial_merge_size`` so the resulting ViT grid is
           clean.

        Returns the post-pipeline PIL image (still RGB, just resized).  Doing
        this BEFORE the Qwen2VLImageProcessor means smart-resize is a no-op
        and the ViT sees exactly upstream Lance's input.
        """
        import numpy as _np
        from torchvision.transforms import InterpolationMode, RandomResizedCrop

        if image.mode != "RGB":
            image = image.convert("RGB")
        w, h = image.size
        img_ratio = w / h
        buckets = LanceBagel._lance_compute_vit_buckets()
        diffs = _np.array([abs(img_ratio - br) for _, br in buckets])
        bh, bw = buckets[int(diffs.argmin())][0]
        bratio = bw / bh
        rrc = RandomResizedCrop(
            size=(bh, bw),
            scale=(1.0, 1.0),
            ratio=(bratio, bratio),
            interpolation=InterpolationMode.BICUBIC,
        )
        out = rrc(image)
        ow, oh = out.size
        cropped_w = ow - ow % LANCE_VIT_DIVISIBLE_CROP
        cropped_h = oh - oh % LANCE_VIT_DIVISIBLE_CROP
        if cropped_w != ow or cropped_h != oh:
            left = (ow - cropped_w) // 2
            top = (oh - cropped_h) // 2
            out = out.crop((left, top, left + cropped_w, top + cropped_h))
        return out

    @staticmethod
    def _lance_compute_video_buckets(resolution: int, stride: int):
        """Generic version of :meth:`_lance_compute_vit_buckets` for arbitrary
        ``resolution`` / ``stride`` (the video VAE uses 640/16, the video ViT
        uses 616/16, both with the same 6 aspect-ratio table)."""
        import math

        max_area = resolution * resolution
        buckets: list[tuple[tuple[int, int], float]] = []
        for name in LANCE_VIT_ASPECT_RATIOS:
            w_s, h_s = (int(v) for v in name.split(":"))
            aspect = w_s / h_s
            rw1 = math.sqrt(max_area * aspect)
            bw1 = round(rw1 / stride) * stride
            bh1 = round(bw1 / aspect / stride) * stride
            br1 = bw1 / bh1
            rh2 = math.sqrt(max_area / aspect)
            bh2 = round(rh2 / stride) * stride
            bw2 = round(bh2 * aspect / stride) * stride
            br2 = bw2 / bh2
            if abs(br1 - aspect) < abs(br2 - aspect):
                bh, bw = (bh1, bw1)
            elif abs(br1 - aspect) > abs(br2 - aspect):
                bh, bw = (bh2, bw2)
            else:
                area1 = bh1 * bw1
                area2 = bh2 * bw2
                bh, bw = (
                    (bh1, bw1)
                    if abs(area1 - max_area) <= abs(area2 - max_area)
                    else (bh2, bw2)
                )
            buckets.append(((bh, bw), bw / bh))
        return buckets

    @staticmethod
    def _lance_sample_frame_indices(
        num_input_frames: int, origin_fps: float
    ) -> list[int]:
        """Replicate upstream's ``MultiClipsFrameSampler`` (single-clip path).

        Upstream config (validation_dataset.py:110):
            temporal=4, sample_fps=12, truncate=False, max_duration=6.0,
            length_type="kn+1", assert_seconds=False.

        For a single clip covering the full input video this reduces to:

            duration = min(num_input_frames / origin_fps, max_duration)
            n_frames = round(duration * sample_fps)
            # round to k*temporal + 1 (or -temporal+1 if already a multiple)
            if n_frames % temporal != 0:
                n_frames = (n_frames // temporal) * temporal + 1
            else:
                n_frames = (n_frames // temporal) * temporal + 1 - temporal
            indices = np.linspace(0, num_input_frames - 1, n_frames, dtype=int)

        Verified against upstream for car (93 frames @ 24fps → 45 sampled) and
        woman (121 frames @ 24fps → 57 sampled).
        """
        import numpy as _np

        duration = num_input_frames / origin_fps
        duration = min(duration, LANCE_VIDEO_MAX_DURATION)
        n_frames = int(round(duration * LANCE_VIDEO_SAMPLE_FPS))
        t = LANCE_VIDEO_TEMPORAL_STRIDE
        if n_frames % t != 0:
            n_frames = n_frames // t * t + 1
        else:
            n_frames = n_frames // t * t + 1 - t
        n_frames = max(n_frames, 1)
        return _np.linspace(0, num_input_frames - 1, n_frames, dtype=int).tolist()

    @staticmethod
    def _lance_bucket_resize_video(
        frames_thwc, resolution: int, stride: int, divisible_crop: int, mean, std
    ):
        """Apply upstream Lance's VideoTransform pipeline to a (T,H,W,C) uint8
        ndarray.  Returns ``(C, T, H', W')`` float tensor.

        Pipeline (mirrors lance-upstream's ``data/transforms.py::VideoTransform``):

            1. BucketResize per PIL frame: RandomResizedCrop(scale=(1,1),
               ratio=fixed-bucket-ratio, BICUBIC) → resized PIL → to_tensor.
               Per-frame PIL path matches upstream's
               ``BucketResize.__call__(list[PIL.Image])`` exactly — using a
               batched tensor RRC instead drifted pixel values by ~0.13
               (in [0,1] range) because torchvision's tensor-BICUBIC kernel
               differs subtly from PIL's BICUBIC kernel.
            2. DivisibleCrop(divisible_crop) — center-crop to dims divisible
               by patch_size * spatial_merge_size (28) for ViT, or by VAE
               downsample (16) for VAE.
            3. Normalize(mean, std) — VAE uses 0.5/0.5; ViT uses Qwen CLIP.
            4. Rearrange "t c h w -> c t h w"
        """
        import numpy as _np
        from PIL import Image as _Image
        from torchvision.transforms import InterpolationMode, RandomResizedCrop
        from torchvision.transforms.functional import center_crop as _ccrop
        from torchvision.transforms.functional import to_tensor as _to_tensor

        if not isinstance(frames_thwc, _np.ndarray):
            raise ValueError(
                f"Expected (T,H,W,C) uint8 ndarray; got {type(frames_thwc)}"
            )
        if frames_thwc.dtype != _np.uint8:
            frames_thwc = frames_thwc.astype(_np.uint8)
        if frames_thwc.ndim != 4 or frames_thwc.shape[-1] != 3:
            raise ValueError(f"Expected (T,H,W,3) uint8; got {frames_thwc.shape}")
        T_in, H_in, W_in, _ = frames_thwc.shape
        aspect = W_in / H_in
        buckets = LanceBagel._lance_compute_video_buckets(resolution, stride)
        diffs = _np.array([abs(aspect - br) for _, br in buckets])
        bh, bw = buckets[int(diffs.argmin())][0]
        bratio = bw / bh
        rrc = RandomResizedCrop(
            size=(bh, bw),
            scale=(1.0, 1.0),
            ratio=(bratio, bratio),
            interpolation=InterpolationMode.BICUBIC,
        )
        per_frame = []
        for t in range(T_in):
            img = _Image.fromarray(frames_thwc[t])
            img = rrc(img)
            per_frame.append(_to_tensor(img))
        frames = torch.stack(per_frame, dim=0)
        _, C, Hb, Wb = frames.shape
        Hc = Hb - Hb % divisible_crop
        Wc = Wb - Wb % divisible_crop
        if Hc != Hb or Wc != Wb:
            frames = _ccrop(frames, [Hc, Wc])
        if isinstance(mean, (int, float)):
            mean_t = torch.tensor([float(mean)] * C, dtype=frames.dtype).view(
                1, C, 1, 1
            )
        else:
            mean_t = torch.tensor(list(mean), dtype=frames.dtype).view(1, C, 1, 1)
        if isinstance(std, (int, float)):
            std_t = torch.tensor([float(std)] * C, dtype=frames.dtype).view(1, C, 1, 1)
        else:
            std_t = torch.tensor(list(std), dtype=frames.dtype).view(1, C, 1, 1)
        frames = (frames - mean_t) / std_t
        frames = frames.permute(1, 0, 2, 3).contiguous()
        return frames

    @staticmethod
    def _lance_patchify_vit_video(video_cthw: torch.Tensor):
        """Replicate upstream ``patchify_video_with_merge``: (C, T, H, W) →
        (num_patches, patch_dim).  ``patch_dim = C * tp * p² = 3 * 2 * 14² = 1176``.

        Returns ``(packed_pixels, grid_thw)`` where ``grid_thw`` is the pre-merge
        grid ``(T // tp, H // p, W // p)`` — same layout the Qwen2.5-VL ViT
        expects (matches ``Qwen2VLImageProcessor.video_processor`` output up to
        the actual pixel preprocessing).
        """
        p = LANCE_VIT_PATCH_SIZE
        tp = LANCE_VIT_TEMPORAL_PATCH_SIZE
        ms = LANCE_VIT_SPATIAL_MERGE
        video = video_cthw.permute(1, 0, 2, 3).contiguous()
        T, C, H, W = video.shape
        if T % tp != 0:
            raise ValueError(f"ViT T={T} must be divisible by temporal_patch={tp}")
        if H % p != 0 or W % p != 0:
            raise ValueError(f"ViT H,W=({H},{W}) must be divisible by patch={p}")
        gt, gh, gw = (T // tp, H // p, W // p)
        if gh % ms != 0 or gw % ms != 0:
            raise ValueError(f"ViT grid ({gh},{gw}) must be divisible by merge={ms}")
        video = video.reshape(gt, tp, C, gh // ms, ms, p, gw // ms, ms, p)
        video = video.permute(0, 3, 6, 4, 7, 2, 1, 5, 8)
        patches = video.reshape(gt * gh * gw, C * tp * p * p)
        grid_thw = torch.tensor([[gt, gh, gw]], dtype=torch.long)
        return (patches, grid_thw)

    @classmethod
    def _lance_video_preprocess(cls, frames_thwc, origin_fps: float):
        """Full upstream-compatible video preprocessing for video_edit.

        Pipeline (mirrors lance-upstream ``validation_dataset.py`` for
        ``--resolution video_480p``):

            1. Frame-sample at 12 fps with max_duration=6s (k*temporal+1 rule).
            2. Bucket-resize the sampled frames TWICE:
               - VAE branch (resolution=640, divisible=16, norm=0.5)
               - ViT branch (resolution=616, divisible=28, norm=Qwen CLIP)
            3. ViT branch is patchified to (num_patches, 1176) for direct
               consumption by Qwen2.5-VL.

        Returns:
            vae_video   — (C, T_lat_in, H_vae, W_vae) float tensor in
                          model-friendly [-1, 1] (mean=0.5, std=0.5).
            vit_pixels  — (num_patches, 1176) float tensor.
            vit_grid_thw — (1, 3) long tensor with pre-merge grid (gt, gh, gw).
            sampled_T   — number of RGB frames after the temporal sampler.
        """
        import numpy as _np

        if isinstance(frames_thwc, torch.Tensor):
            frames_thwc = frames_thwc.detach().cpu().numpy()
        if frames_thwc.dtype != _np.uint8:
            arr = frames_thwc
            if arr.max() <= 1.5:
                arr = (arr * 255.0).clip(0, 255).astype(_np.uint8)
            else:
                arr = arr.astype(_np.uint8)
            frames_thwc = arr
        T_in = frames_thwc.shape[0]
        indices = cls._lance_sample_frame_indices(T_in, origin_fps)
        sampled = frames_thwc[indices]
        vae_video = cls._lance_bucket_resize_video(
            sampled,
            resolution=LANCE_VIDEO_VAE_RESOLUTION,
            stride=LANCE_VIDEO_BUCKET_STRIDE,
            divisible_crop=LANCE_VIDEO_VAE_DIVISIBLE_CROP,
            mean=0.5,
            std=0.5,
        )
        vit_video = cls._lance_bucket_resize_video(
            sampled,
            resolution=LANCE_VIDEO_VIT_RESOLUTION,
            stride=LANCE_VIDEO_BUCKET_STRIDE,
            divisible_crop=LANCE_VIDEO_VIT_DIVISIBLE_CROP,
            mean=LANCE_VIT_NORM_MEAN,
            std=LANCE_VIT_NORM_STD,
        )
        if vit_video.shape[1] % 2 == 1:
            vit_video = torch.cat([vit_video, vit_video[:, -1:]], dim=1)
        vit_pixels, vit_grid_thw = cls._lance_patchify_vit_video(vit_video)
        return (vae_video, vit_pixels, vit_grid_thw, len(indices))

    @staticmethod
    def _qwen_vl_processor_call(processor, image):
        """Invoke the Qwen2-VL image processor and return ``(pixel_values, grid_thw)``.

        Applies upstream Lance's BucketResize+DivisibleCrop BEFORE calling the
        standard Qwen2VLImageProcessor.  After the pre-resize the input dims
        are already divisible by ``patch_size * spatial_merge_size`` and within
        the processor's pixel bounds, so the processor's own smart-resize is a
        no-op — the ViT sees the exact bucket-cropped pixels upstream uses.
        """
        prepped = LanceBagel._lance_bucket_resize_pil(image)
        proc_out = processor(images=prepped, return_tensors="pt")
        pixel_values = proc_out["pixel_values"]
        grid_thw = proc_out["image_grid_thw"]
        return (pixel_values, grid_thw)

    @staticmethod
    def _mrope_broadcast(position_ids: torch.Tensor) -> torch.Tensor:
        """Convert scalar ``(S,)`` position ids to mrope ``(3, S)`` by
        broadcasting the scalar value to all three (t, h, w) axes.

        Lance/Qwen2.5-VL's mRoPE expects 3-D positions per token; for text
        tokens (and image-edit context tokens) all three axes share the
        same scalar position id.  Vision-generation paths override this with
        per-token ``(t, h, w)`` indices.
        """
        if position_ids is None:
            return position_ids
        if position_ids.ndim == 1:
            return position_ids.unsqueeze(0).expand(3, -1).contiguous()
        return position_ids

    def prepare_prompts(self, *args, **kwargs):
        gen_input, newlens, new_rope = super().prepare_prompts(*args, **kwargs)
        if "packed_text_position_ids" in gen_input:
            gen_input["packed_text_position_ids"] = self._mrope_broadcast(
                gen_input["packed_text_position_ids"]
            )
        return (gen_input, newlens, new_rope)

    def _per_token_mrope_for_vae_latent(self, image_sizes, curr_rope) -> torch.Tensor:
        """Build per-token Qwen2.5-VL mRoPE positions for the gen latent block.

        Matches upstream Lance (``Lance.validation_gen_KVcache`` →
        ``get_rope_index``):

            start_of_image  ->  (P-1,   P-1,   P-1)
            latent (hi, wi) ->  (P,     P+hi,  P+wi)
            end_of_image    ->  (P+max(h,w), ..., ...)

        where ``P = curr_position_id`` is the position counter AFTER the text
        prefix (BAGEL parent already passes ``gen_context['ropes']``). The
        ``-1`` on start_of_image matches upstream's get_rope_index layout: the
        start marker sits one position before the latent block (which is
        anchored at P), and the end marker sits ``max(h,w)`` positions past.

        Without per-token (h, w) variation, attention can't see the spatial
        layout → image PSNR collapses ~6 dB after 30 steps.
        """
        pos_t: list[int] = []
        pos_h: list[int] = []
        pos_w: list[int] = []
        for (H, W), P in zip(image_sizes, curr_rope):
            h = H // self.latent_downsample
            w = W // self.latent_downsample
            max_hw = max(h, w)
            pos_t.append(P)
            pos_h.append(P)
            pos_w.append(P)
            for hi in range(h):
                for wi in range(w):
                    pos_t.append(P + 1)
                    pos_h.append(P + 1 + hi)
                    pos_w.append(P + 1 + wi)
            end_p = P + max_hw + 1
            pos_t.append(end_p)
            pos_h.append(end_p)
            pos_w.append(end_p)
        return torch.stack(
            [
                torch.tensor(pos_t, dtype=torch.long),
                torch.tensor(pos_h, dtype=torch.long),
                torch.tensor(pos_w, dtype=torch.long),
            ],
            dim=0,
        )

    def _per_token_mrope_for_video_latent(
        self, video_shapes, curr_rope
    ) -> torch.Tensor:
        """3-D analogue of :meth:`_per_token_mrope_for_vae_latent` for video.

        Matches upstream Lance's ``get_rope_index`` for ``modality==noise``
        (and ``modality==ref_source`` since they share rope per
        ``shift_position_ids``).  The temporal axis is amplified by
        ``LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID`` so neighbouring
        latent frames are well-separated, matching the upstream Qwen2.5-VL
        rope convention.  Verified against upstream's rope dump for
        video_edit at video_480p (call09 cond noise iter 0):

            start_of_image  -> (P,           P,         P)
            latent (t,h,w)  -> (P+1+t*2,     P+1+h,     P+1+w)
            end_of_image    -> (P+max+1,     P+max+1,   P+max+1)

        where ``max = max(t_lat*2-1, h_lat-1, w_lat-1) + 1`` matches the
        end marker placement upstream uses (call09 final token at 159 for
        T_lat=12, H_lat=35, W_lat=47 → max(22, 34, 46)+1=47, start=111,
        end=158... actual upstream end=159, suggesting +2 from the body's
        max).  We mirror :meth:`_lance_native_prepare_vae_images` exactly
        so the VAE_ref prefill and the gen noise share the same rope range.
        """
        downsample_t = int(getattr(self.config.vae_config, "downsample_temporal", 4))
        t_scale = LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID
        pos_t: list[int] = []
        pos_h: list[int] = []
        pos_w: list[int] = []
        for (T, H, W), P in zip(video_shapes, curr_rope):
            h = H // self.latent_downsample
            w = W // self.latent_downsample
            t = (T - 1) // downsample_t + 1
            max_thw = max(int((t - 1) * t_scale), h - 1, w - 1) + 1
            pos_t.append(P)
            pos_h.append(P)
            pos_w.append(P)
            for ti in range(t):
                for hi in range(h):
                    for wi in range(w):
                        pos_t.append(P + 1 + int(ti * t_scale))
                        pos_h.append(P + 1 + hi)
                        pos_w.append(P + 1 + wi)
            end_p = P + max_thw + 1
            pos_t.append(end_p)
            pos_h.append(end_p)
            pos_w.append(end_p)
        return torch.stack(
            [
                torch.tensor(pos_t, dtype=torch.long),
                torch.tensor(pos_h, dtype=torch.long),
                torch.tensor(pos_w, dtype=torch.long),
            ],
            dim=0,
        )

    def prepare_vae_latent(self, curr_kvlens, curr_rope, image_sizes, new_token_ids):
        gen_input = super().prepare_vae_latent(
            curr_kvlens, curr_rope, image_sizes, new_token_ids
        )
        gen_input["packed_position_ids"] = self._per_token_mrope_for_vae_latent(
            image_sizes, curr_rope
        )
        return gen_input

    def prepare_vae_latent_cfg(self, curr_kvlens, curr_rope, image_sizes):
        gen_input = super().prepare_vae_latent_cfg(curr_kvlens, curr_rope, image_sizes)
        gen_input["cfg_packed_position_ids"] = self._per_token_mrope_for_vae_latent(
            image_sizes, curr_rope
        )
        return gen_input

    def prepare_start_tokens(self, *args, **kwargs):
        gen_input = super().prepare_start_tokens(*args, **kwargs)
        if isinstance(gen_input, dict):
            for k in (
                "packed_query_position_ids",
                "packed_text_position_ids",
                "packed_position_ids",
            ):
                if k in gen_input and torch.is_tensor(gen_input[k]):
                    gen_input[k] = self._mrope_broadcast(gen_input[k])
        return gen_input

    def prepare_vit_videos(
        self, curr_kvlens, curr_rope, videos, new_token_ids, precomputed_vit=None
    ):
        """Multi-frame ViT prefill for the ``x2t_video`` / ``video_edit`` paths.

        ``videos`` is a list of per-request video tensors / numpy arrays of
        shape ``(T, H, W, 3)``.  By default the Qwen2-VL video processor is
        used to convert each video to ``(pixel_values_videos, video_grid_thw)``.
        For ``video_edit`` precision matching, the pipeline may pre-compute the
        upstream-style BucketResize output and pass it via ``precomputed_vit``
        — a list of ``(pixel_values, grid_thw)`` per video, in which case the
        processor call is skipped.
        """
        processor = getattr(self, "_lance_video_processor", None)
        if processor is None and precomputed_vit is None:
            raise RuntimeError(
                "LanceBagel.prepare_vit_videos requires either ``precomputed_vit`` or ``bagel._lance_video_processor`` (a Qwen2-VL-compatible video processor)."
            )
        if precomputed_vit is not None and len(precomputed_vit) != len(videos):
            raise ValueError(
                f"precomputed_vit length ({len(precomputed_vit)}) must match number of videos ({len(videos)})"
            )
        packed_vit_token_indexes: list[int] = []
        vit_token_seqlens: list[int] = []
        packed_vit_tokens: list[torch.Tensor] = []
        packed_vit_position_ids: list[torch.Tensor] = []
        packed_text_ids: list[int] = []
        packed_text_indexes: list[int] = []
        packed_seqlens: list[int] = []
        packed_indexes: list[int] = []
        packed_key_value_indexes: list[int] = []
        grid_thw_list: list[torch.Tensor] = []
        per_axis_pos: list[tuple[int, int, int]] = []
        merge_size = int(getattr(self.vit_model, "spatial_merge_size", 2))
        merge_factor = merge_size * merge_size
        _curr = curr = 0
        newlens: list[int] = []
        new_rope: list[int] = []
        for vi, (video, curr_kvlen, curr_position_id) in enumerate(
            zip(videos, curr_kvlens, curr_rope)
        ):
            packed_key_value_indexes.extend(range(curr, curr + curr_kvlen))
            curr += curr_kvlen
            packed_text_ids.append(new_token_ids["start_of_image"])
            packed_text_indexes.append(_curr)
            packed_indexes.append(curr)
            curr += 1
            _curr += 1
            per_axis_pos.append((curr_position_id, curr_position_id, curr_position_id))
            if precomputed_vit is not None:
                pixel_values, grid_thw = precomputed_vit[vi]
                if not torch.is_tensor(grid_thw):
                    grid_thw = torch.as_tensor(grid_thw, dtype=torch.long)
                if grid_thw.dim() == 1:
                    grid_thw = grid_thw.unsqueeze(0)
            else:
                proc_out = processor(videos=video, return_tensors="pt")
                pixel_values = proc_out["pixel_values_videos"]
                grid_thw = proc_out["video_grid_thw"]
            T_lat, H, W = (int(v) for v in grid_thw[0].tolist())
            num_patches_pre_merge = T_lat * H * W
            assert num_patches_pre_merge == pixel_values.shape[0], (
                f"pixel_values rows ({pixel_values.shape[0]}) != T_lat*H*W ({num_patches_pre_merge}); video_grid_thw={grid_thw.tolist()}"
            )
            num_vit_tokens = num_patches_pre_merge // merge_factor
            packed_vit_tokens.append(pixel_values)
            vit_token_seqlens.append(num_patches_pre_merge)
            packed_vit_position_ids.append(
                torch.arange(num_patches_pre_merge, dtype=torch.long)
            )
            grid_thw_list.append(grid_thw[0].to(torch.long))
            packed_vit_token_indexes.extend(range(_curr, _curr + num_vit_tokens))
            packed_indexes.extend(range(curr, curr + num_vit_tokens))
            curr += num_vit_tokens
            _curr += num_vit_tokens
            h_merged = H // merge_size
            w_merged = W // merge_size
            t_scale = LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID
            for ti in range(T_lat):
                for hi in range(h_merged):
                    for wi in range(w_merged):
                        per_axis_pos.append(
                            (
                                curr_position_id + 1 + int(ti * t_scale),
                                curr_position_id + 1 + hi,
                                curr_position_id + 1 + wi,
                            )
                        )
            packed_text_ids.append(new_token_ids["end_of_image"])
            packed_text_indexes.append(_curr)
            packed_indexes.append(curr)
            curr += 1
            _curr += 1
            max_offset = max(int((T_lat - 1) * t_scale), h_merged - 1, w_merged - 1)
            end_p = curr_position_id + max_offset + 2
            per_axis_pos.append((end_p, end_p, end_p))
            packed_seqlens.append(num_vit_tokens + 2)
            newlens.append(curr_kvlen + num_vit_tokens + 2)
            new_rope.append(end_p + 1)
        pos_t = torch.tensor([p[0] for p in per_axis_pos], dtype=torch.long)
        pos_h = torch.tensor([p[1] for p in per_axis_pos], dtype=torch.long)
        pos_w = torch.tensor([p[2] for p in per_axis_pos], dtype=torch.long)
        pos_t = pos_t - pos_t[0] + 1000
        packed_position_ids_3d = torch.stack([pos_t, pos_h, pos_w], dim=0)
        generation_input = {
            "packed_text_ids": torch.tensor(packed_text_ids, dtype=torch.long),
            "packed_text_indexes": torch.tensor(packed_text_indexes, dtype=torch.long),
            "vit_token_seqlens": torch.tensor(vit_token_seqlens, dtype=torch.int),
            "packed_vit_tokens": torch.cat(packed_vit_tokens, dim=0),
            "packed_vit_position_ids": torch.cat(packed_vit_position_ids, dim=0),
            "packed_vit_token_indexes": torch.tensor(
                packed_vit_token_indexes, dtype=torch.long
            ),
            "packed_position_ids": packed_position_ids_3d,
            "packed_seqlens": torch.tensor(packed_seqlens, dtype=torch.int),
            "packed_indexes": torch.tensor(packed_indexes, dtype=torch.long),
            "packed_key_value_indexes": torch.tensor(
                packed_key_value_indexes, dtype=torch.long
            ),
            "key_values_lens": torch.tensor(curr_kvlens, dtype=torch.int),
            "_lance_grid_thw": torch.stack(grid_thw_list, dim=0),
        }
        return (generation_input, newlens, new_rope)

    def prepare_vit_images(
        self, curr_kvlens, curr_rope, images, transforms, new_token_ids
    ):
        if not hasattr(self, "_lance_image_processor"):
            raise RuntimeError(
                "LanceBagel.prepare_vit_images requires the pipeline to set ``bagel._lance_image_processor`` (a Qwen2-VL-compatible processor)."
            )
        processor = self._lance_image_processor
        packed_vit_token_indexes: list[int] = []
        vit_token_seqlens: list[int] = []
        packed_vit_tokens: list[torch.Tensor] = []
        packed_vit_position_ids: list[torch.Tensor] = []
        packed_text_ids: list[int] = []
        packed_text_indexes: list[int] = []
        packed_seqlens: list[int] = []
        packed_indexes: list[int] = []
        packed_key_value_indexes: list[int] = []
        grid_thw_list: list[torch.Tensor] = []
        merge_size = int(getattr(self.vit_model, "spatial_merge_size", 2))
        merge_factor = merge_size * merge_size
        _curr = curr = 0
        newlens: list[int] = []
        new_rope: list[int] = []
        per_axis_pos: list[tuple[int, int, int]] = []
        for image, curr_kvlen, curr_position_id in zip(images, curr_kvlens, curr_rope):
            packed_key_value_indexes.extend(range(curr, curr + curr_kvlen))
            curr += curr_kvlen
            packed_text_ids.append(new_token_ids["start_of_image"])
            packed_text_indexes.append(_curr)
            packed_indexes.append(curr)
            curr += 1
            _curr += 1
            per_axis_pos.append((curr_position_id, curr_position_id, curr_position_id))
            pixel_values, grid_thw = self._qwen_vl_processor_call(processor, image)
            T, H, W = (int(v) for v in grid_thw[0].tolist())
            num_patches_pre_merge = T * H * W
            assert num_patches_pre_merge == pixel_values.shape[0], (
                f"pixel_values rows ({pixel_values.shape[0]}) != T*H*W ({num_patches_pre_merge}); image_grid_thw={grid_thw.tolist()}"
            )
            num_img_tokens = num_patches_pre_merge // merge_factor
            packed_vit_tokens.append(pixel_values)
            vit_token_seqlens.append(num_patches_pre_merge)
            packed_vit_position_ids.append(
                torch.arange(num_patches_pre_merge, dtype=torch.long)
            )
            grid_thw_list.append(grid_thw[0].to(torch.long))
            packed_vit_token_indexes.extend(range(_curr, _curr + num_img_tokens))
            packed_indexes.extend(range(curr, curr + num_img_tokens))
            curr += num_img_tokens
            _curr += num_img_tokens
            h_merged = H // merge_size
            w_merged = W // merge_size
            max_hw = max(h_merged, w_merged)
            for hi in range(h_merged):
                for wi in range(w_merged):
                    per_axis_pos.append(
                        (
                            curr_position_id + 1,
                            curr_position_id + 1 + hi,
                            curr_position_id + 1 + wi,
                        )
                    )
            packed_text_ids.append(new_token_ids["end_of_image"])
            packed_text_indexes.append(_curr)
            packed_indexes.append(curr)
            curr += 1
            _curr += 1
            end_p = curr_position_id + max_hw + 1
            per_axis_pos.append((end_p, end_p, end_p))
            packed_seqlens.append(num_img_tokens + 2)
            newlens.append(curr_kvlen + num_img_tokens + 2)
            new_rope.append(end_p + 1)
        pos_t = torch.tensor([p[0] for p in per_axis_pos], dtype=torch.long)
        pos_h = torch.tensor([p[1] for p in per_axis_pos], dtype=torch.long)
        pos_w = torch.tensor([p[2] for p in per_axis_pos], dtype=torch.long)
        pos_t = pos_t - pos_t[0] + 1000
        packed_position_ids_3d = torch.stack([pos_t, pos_h, pos_w], dim=0)
        generation_input = {
            "packed_text_ids": torch.tensor(packed_text_ids, dtype=torch.long),
            "packed_text_indexes": torch.tensor(packed_text_indexes, dtype=torch.long),
            "vit_token_seqlens": torch.tensor(vit_token_seqlens, dtype=torch.int),
            "packed_vit_tokens": torch.cat(packed_vit_tokens, dim=0),
            "packed_vit_position_ids": torch.cat(packed_vit_position_ids, dim=0),
            "packed_vit_token_indexes": torch.tensor(
                packed_vit_token_indexes, dtype=torch.long
            ),
            "packed_position_ids": packed_position_ids_3d,
            "packed_seqlens": torch.tensor(packed_seqlens, dtype=torch.int),
            "packed_indexes": torch.tensor(packed_indexes, dtype=torch.long),
            "packed_key_value_indexes": torch.tensor(
                packed_key_value_indexes, dtype=torch.long
            ),
            "key_values_lens": torch.tensor(curr_kvlens, dtype=torch.int),
            "_lance_grid_thw": torch.stack(grid_thw_list, dim=0),
        }
        return (generation_input, newlens, new_rope)

    def forward_cache_update_vit(self, *args, **kwargs):
        grid_thw = kwargs.pop("_lance_grid_thw", None)
        if grid_thw is not None and hasattr(self.vit_model, "set_pending_grid_thw"):
            self.vit_model.set_pending_grid_thw(grid_thw)
        return super().forward_cache_update_vit(*args, **kwargs)

    def prepare_video_latent(self, curr_kvlens, curr_rope, video_shapes, new_token_ids):
        """3-D analogue of :meth:`prepare_vae_latent`.

        ``video_shapes`` is a list of ``(T, H, W)`` per request (RGB pixel
        space).  We package one packed-init-noise tensor over ``T_lat × H_lat ×
        W_lat`` latent tokens per video, plus 1-D indices into the 3-D position
        embedding table maintained by :class:`LancePositionEmbedding3D`
        (`bagel.latent_pos_embed`).  Latent geometry:

        - spatial: ``H_lat = H // latent_downsample`` (``=16`` for Lance)
        - temporal: ``T_lat = (T - 1) // downsample_temporal + 1`` (``=4`` for Wan2.2)
        - channels: ``latent_channel = 48``

        Position ids are flattened ``t * max_per_side² + h * max_per_side + w``
        so they index directly into the ``(max_num_frames * max_per_side²,
        hidden_size)`` table.
        """
        downsample_t = int(getattr(self.config.vae_config, "downsample_temporal", 4))
        max_per_side = int(self.max_latent_size)
        packed_text_ids, packed_text_indexes = ([], [])
        packed_vae_position_ids, packed_vae_token_indexes, packed_init_noises = (
            [],
            [],
            [],
        )
        packed_seqlens, packed_indexes = ([], [])
        packed_key_value_indexes = []
        per_axis_pos: list[tuple[int, int, int]] = []
        query_curr = curr = 0
        for (T, H, W), curr_kvlen, curr_position_id in zip(
            video_shapes, curr_kvlens, curr_rope
        ):
            packed_key_value_indexes.extend(range(curr, curr + curr_kvlen))
            curr += curr_kvlen
            packed_text_ids.append(new_token_ids["start_of_image"])
            packed_text_indexes.append(query_curr)
            packed_indexes.append(curr)
            curr += 1
            query_curr += 1
            per_axis_pos.append((curr_position_id, curr_position_id, curr_position_id))
            h = H // self.latent_downsample
            w = W // self.latent_downsample
            t = (T - 1) // downsample_t + 1
            num_video_tokens = t * h * w
            tt, hh, ww = torch.meshgrid(
                torch.arange(t), torch.arange(h), torch.arange(w), indexing="ij"
            )
            tt_flat = tt.flatten().tolist()
            hh_flat = hh.flatten().tolist()
            ww_flat = ww.flatten().tolist()
            vae_position_ids = (
                tt * (max_per_side * max_per_side) + hh * max_per_side + ww
            ).flatten()
            packed_vae_position_ids.append(vae_position_ids)
            packed_init_noises.append(
                torch.randn(
                    num_video_tokens, self.latent_channel * self.latent_patch_size**2
                )
            )
            packed_vae_token_indexes.extend(
                range(query_curr, query_curr + num_video_tokens)
            )
            packed_indexes.extend(range(curr, curr + num_video_tokens))
            curr += num_video_tokens
            query_curr += num_video_tokens
            t_scale = LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID
            for ti, hi, wi in zip(tt_flat, hh_flat, ww_flat):
                per_axis_pos.append(
                    (
                        curr_position_id + 1 + int(ti * t_scale),
                        curr_position_id + 1 + hi,
                        curr_position_id + 1 + wi,
                    )
                )
            packed_text_ids.append(new_token_ids["end_of_image"])
            packed_text_indexes.append(query_curr)
            packed_indexes.append(curr)
            curr += 1
            query_curr += 1
            max_thw = max(int((t - 1) * t_scale), h - 1, w - 1) + 1
            end_p = curr_position_id + max_thw + 1
            per_axis_pos.append((end_p, end_p, end_p))
            packed_seqlens.append(num_video_tokens + 2)
        pos_t = torch.tensor([p[0] for p in per_axis_pos], dtype=torch.long)
        pos_h = torch.tensor([p[1] for p in per_axis_pos], dtype=torch.long)
        pos_w = torch.tensor([p[2] for p in per_axis_pos], dtype=torch.long)
        packed_position_ids_3d = torch.stack([pos_t, pos_h, pos_w], dim=0)
        generation_input = {
            "packed_text_ids": torch.tensor(packed_text_ids, dtype=torch.long),
            "packed_text_indexes": torch.tensor(packed_text_indexes, dtype=torch.long),
            "packed_init_noises": torch.cat(packed_init_noises, dim=0),
            "packed_vae_position_ids": torch.cat(packed_vae_position_ids, dim=0),
            "packed_vae_token_indexes": torch.tensor(
                packed_vae_token_indexes, dtype=torch.long
            ),
            "packed_seqlens": torch.tensor(packed_seqlens, dtype=torch.int),
            "packed_position_ids": packed_position_ids_3d,
            "key_values_lens": torch.tensor(curr_kvlens, dtype=torch.int),
            "packed_indexes": torch.tensor(packed_indexes, dtype=torch.long),
            "packed_key_value_indexes": torch.tensor(
                packed_key_value_indexes, dtype=torch.long
            ),
        }
        return generation_input

    def prepare_video_latent_cfg(self, curr_kvlens, curr_rope, video_shapes):
        """3-D analogue of :meth:`prepare_vae_latent_cfg` (CFG side).

        Mirrors :meth:`prepare_video_latent`'s mRoPE 3-D position layout
        EXACTLY, including the ``LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID``
        temporal scaling.  Without that scaling, the cfg_text branch attends
        with different rope coordinates than the cond branch (and than
        upstream's ``get_rope_index``), which makes ``cfg_text_v_t`` diverge
        from upstream and the CFG combination amplifies the error every
        denoise step.
        """
        downsample_t = int(getattr(self.config.vae_config, "downsample_temporal", 4))
        packed_indexes, packed_key_value_indexes = ([], [])
        per_axis_pos: list[tuple[int, int, int]] = []
        query_curr = curr = 0
        t_scale = LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID
        for (T, H, W), curr_kvlen, curr_position_id in zip(
            video_shapes, curr_kvlens, curr_rope
        ):
            packed_key_value_indexes.extend(range(curr, curr + curr_kvlen))
            curr += curr_kvlen
            packed_indexes.append(curr)
            curr += 1
            query_curr += 1
            per_axis_pos.append((curr_position_id, curr_position_id, curr_position_id))
            h = H // self.latent_downsample
            w = W // self.latent_downsample
            t = (T - 1) // downsample_t + 1
            num_video_tokens = t * h * w
            packed_indexes.extend(range(curr, curr + num_video_tokens))
            curr += num_video_tokens
            query_curr += num_video_tokens
            tt, hh, ww = torch.meshgrid(
                torch.arange(t), torch.arange(h), torch.arange(w), indexing="ij"
            )
            for ti, hi, wi in zip(
                tt.flatten().tolist(), hh.flatten().tolist(), ww.flatten().tolist()
            ):
                per_axis_pos.append(
                    (
                        curr_position_id + 1 + int(ti * t_scale),
                        curr_position_id + 1 + hi,
                        curr_position_id + 1 + wi,
                    )
                )
            packed_indexes.append(curr)
            curr += 1
            query_curr += 1
            max_thw = max(int((t - 1) * t_scale), h - 1, w - 1) + 1
            end_p = curr_position_id + max_thw + 1
            per_axis_pos.append((end_p, end_p, end_p))
        pos_t = torch.tensor([p[0] for p in per_axis_pos], dtype=torch.long)
        pos_h = torch.tensor([p[1] for p in per_axis_pos], dtype=torch.long)
        pos_w = torch.tensor([p[2] for p in per_axis_pos], dtype=torch.long)
        cfg_packed_position_ids_3d = torch.stack([pos_t, pos_h, pos_w], dim=0)
        return {
            "cfg_packed_position_ids": cfg_packed_position_ids_3d,
            "cfg_packed_query_indexes": torch.tensor(packed_indexes, dtype=torch.long),
            "cfg_key_values_lens": torch.tensor(curr_kvlens, dtype=torch.int),
            "cfg_packed_key_value_indexes": torch.tensor(
                packed_key_value_indexes, dtype=torch.long
            ),
        }

    def _lance_native_prepare_vae_images(
        self,
        curr_kvlens,
        curr_rope,
        images,
        transforms,
        new_token_ids,
        timestep=0,
        is_video: bool = False,
    ):
        """Lance-native ``prepare_vae_images`` with 3-D mRoPE positions.

        Mirrors :meth:`Bagel.prepare_vae_images` but emits per-token mRoPE
        ``(curr + t, curr + h, curr + w)`` positions for VAE latent tokens
        (BAGEL emits scalar ``curr_position_id`` for all of them, which
        triggers a CUDA index-out-of-bounds gather on Lance's Qwen2.5-VL
        backbone).  For still images ``t = 0``; for video clips ``t``
        ranges over ``T_lat = (T - 1) // downsample_temporal + 1``.
        """
        downsample_t = int(getattr(self.config.vae_config, "downsample_temporal", 4))
        max_per_side = int(self.max_latent_size)
        packed_text_ids: list[int] = []
        packed_text_indexes: list[int] = []
        packed_vae_position_ids: list[torch.Tensor] = []
        packed_vae_token_indexes: list[int] = []
        packed_indexes: list[int] = []
        packed_key_value_indexes: list[int] = []
        packed_seqlens: list[int] = []
        patchified_vae_latent_shapes: list[tuple] = []
        vae_image_tensors: list[torch.Tensor] = []
        per_axis_pos: list[tuple[int, int, int]] = []
        query_curr = curr = 0
        newlens: list[int] = []
        new_rope: list[int] = []
        for image, curr_kvlen, curr_position_id in zip(images, curr_kvlens, curr_rope):
            packed_key_value_indexes.extend(range(curr, curr + curr_kvlen))
            curr += curr_kvlen
            packed_text_ids.append(new_token_ids["start_of_image"])
            packed_text_indexes.append(query_curr)
            packed_indexes.append(curr)
            curr += 1
            query_curr += 1
            per_axis_pos.append((curr_position_id, curr_position_id, curr_position_id))
            image_tensor = transforms(image)
            vae_image_tensors.append(image_tensor)
            if image_tensor.dim() == 3:
                H, W = image_tensor.shape[1:]
                T = 1
            elif image_tensor.dim() == 4:
                _, T, H, W = image_tensor.shape
            else:
                raise ValueError(
                    f"vae transforms must return 3-D or 4-D tensor; got {image_tensor.shape}"
                )
            h_lat = H // self.latent_downsample
            w_lat = W // self.latent_downsample
            t_lat = (T - 1) // downsample_t + 1 if is_video else 1
            patchified_vae_latent_shapes.append(
                (t_lat, h_lat, w_lat) if is_video else (h_lat, w_lat)
            )
            tt, hh, ww = torch.meshgrid(
                torch.arange(t_lat),
                torch.arange(h_lat),
                torch.arange(w_lat),
                indexing="ij",
            )
            vae_pos_ids = (
                tt * (max_per_side * max_per_side) + hh * max_per_side + ww
            ).flatten()
            packed_vae_position_ids.append(vae_pos_ids)
            num_image_tokens = t_lat * h_lat * w_lat
            packed_vae_token_indexes.extend(
                range(query_curr, query_curr + num_image_tokens)
            )
            packed_indexes.extend(range(curr, curr + num_image_tokens))
            curr += num_image_tokens
            query_curr += num_image_tokens
            t_scale = (
                LANCE_TOKENS_PER_SECOND * LANCE_SECONDS_PER_GRID if is_video else 1
            )
            max_thw = max(int((t_lat - 1) * t_scale), h_lat - 1, w_lat - 1) + 1
            for ti, hi, wi in zip(
                tt.flatten().tolist(), hh.flatten().tolist(), ww.flatten().tolist()
            ):
                per_axis_pos.append(
                    (
                        curr_position_id + 1 + int(ti * t_scale),
                        curr_position_id + 1 + hi,
                        curr_position_id + 1 + wi,
                    )
                )
            packed_text_ids.append(new_token_ids["end_of_image"])
            packed_text_indexes.append(query_curr)
            packed_indexes.append(curr)
            curr += 1
            query_curr += 1
            end_p = curr_position_id + max_thw + 1
            per_axis_pos.append((end_p, end_p, end_p))
            packed_seqlens.append(num_image_tokens + 2)
            newlens.append(curr_kvlen + num_image_tokens + 2)
            new_rope.append(end_p + 1)
        image_sizes = [item.shape for item in vae_image_tensors]
        max_image_size = [max(item) for item in list(zip(*image_sizes))]
        padded_images = torch.zeros(size=(len(vae_image_tensors), *max_image_size))
        for i, image_tensor in enumerate(vae_image_tensors):
            if image_tensor.dim() == 3:
                padded_images[
                    i, :, : image_tensor.shape[1], : image_tensor.shape[2]
                ] = image_tensor
            else:
                padded_images[
                    i,
                    :,
                    : image_tensor.shape[1],
                    : image_tensor.shape[2],
                    : image_tensor.shape[3],
                ] = image_tensor
        pos_t = torch.tensor([p[0] for p in per_axis_pos], dtype=torch.long)
        pos_h = torch.tensor([p[1] for p in per_axis_pos], dtype=torch.long)
        pos_w = torch.tensor([p[2] for p in per_axis_pos], dtype=torch.long)
        packed_position_ids_3d = torch.stack([pos_t, pos_h, pos_w], dim=0)
        generation_input = {
            "padded_images": padded_images,
            "patchified_vae_latent_shapes": patchified_vae_latent_shapes,
            "packed_vae_position_ids": torch.cat(packed_vae_position_ids, dim=0),
            "packed_timesteps": torch.tensor([timestep]),
            "packed_vae_token_indexes": torch.tensor(
                packed_vae_token_indexes, dtype=torch.long
            ),
            "packed_text_ids": torch.tensor(packed_text_ids, dtype=torch.long),
            "packed_text_indexes": torch.tensor(packed_text_indexes, dtype=torch.long),
            "packed_position_ids": packed_position_ids_3d,
            "packed_seqlens": torch.tensor(packed_seqlens, dtype=torch.int),
            "packed_indexes": torch.tensor(packed_indexes, dtype=torch.long),
            "packed_key_value_indexes": torch.tensor(
                packed_key_value_indexes, dtype=torch.long
            ),
            "key_values_lens": torch.tensor(curr_kvlens, dtype=torch.int),
        }
        return (generation_input, newlens, new_rope)

    def prepare_vae_images(
        self, curr_kvlens, curr_rope, images, transforms, new_token_ids, timestep=0
    ):
        """VAE prefill router.

        - When ``images`` is non-empty (image_edit / video_edit path on the
          image side): delegate to :meth:`_lance_native_prepare_vae_images`
          which emits Lance's 3-D mRoPE positions and a real VAE prefill,
          letting BAGEL's parent ``image_edit`` flow handle the rest.
        - When ``images`` is empty (t2i / x2t paths): short-circuit with the
          no-op output, mirroring BAGEL's "no image to prefill" sentinel.
        """
        if images:
            return self._lance_native_prepare_vae_images(
                curr_kvlens=curr_kvlens,
                curr_rope=curr_rope,
                images=images,
                transforms=transforms,
                new_token_ids=new_token_ids,
                timestep=timestep,
                is_video=False,
            )
        generation_input = {
            "padded_images": torch.empty(0, 3, 0, 0),
            "patchified_vae_latent_shapes": [],
            "packed_vae_position_ids": torch.empty(0, dtype=torch.long),
            "packed_timesteps": torch.tensor([timestep]),
            "packed_vae_token_indexes": torch.empty(0, dtype=torch.long),
            "packed_text_ids": torch.empty(0, dtype=torch.long),
            "packed_text_indexes": torch.empty(0, dtype=torch.long),
            "packed_position_ids": torch.empty(0, dtype=torch.long),
            "packed_seqlens": torch.empty(0, dtype=torch.int),
            "packed_indexes": torch.empty(0, dtype=torch.long),
            "packed_key_value_indexes": torch.empty(0, dtype=torch.long),
            "key_values_lens": torch.tensor(curr_kvlens, dtype=torch.int),
        }
        return (generation_input, list(curr_kvlens), list(curr_rope))

    def forward_cache_update_vae(
        self,
        vae_model,
        past_key_values,
        padded_images=None,
        patchified_vae_latent_shapes=None,
        packed_vae_position_ids=None,
        packed_timesteps=None,
        packed_vae_token_indexes=None,
        packed_text_ids=None,
        packed_text_indexes=None,
        packed_position_ids=None,
        packed_seqlens=None,
        packed_indexes=None,
        key_values_lens=None,
        packed_key_value_indexes=None,
        precomputed_latent=None,
    ):
        """Lance-native VAE prefill that *actually* scatters the encoded
        latents into the LLM query sequence.

        :meth:`Bagel.forward_cache_update_vae` in vllm-omni computes
        ``packed_latent = vae2llm(...) + time_embed + pos_embed`` and then
        passes only ``packed_text_ids`` to the LLM — the VAE embeddings
        never enter the query sequence (the LLM builds it from
        ``embed_tokens(packed_text_ids)`` which is just the 2 framing
        tokens).  The mismatch between ``query_lens = [num_vae + 2]`` and
        the resulting 2-token sequence is what crashes the gather inside
        attention.

        We scatter both pieces explicitly: text framing tokens at
        ``packed_text_indexes`` and the VAE latent embeddings at
        ``packed_vae_token_indexes``, producing a full-length
        ``(sum(packed_seqlens), hidden)`` sequence the LLM can attend
        over.  Empty prep data (legacy x2t / x2t_video no-op path) is
        short-circuited.
        """
        if (
            packed_text_ids is None
            or packed_text_ids.numel() == 0
            or (
                precomputed_latent is None
                and (padded_images is None or padded_images.numel() == 0)
            )
        ):
            return past_key_values
        if precomputed_latent is not None:
            padded_latent = precomputed_latent
        else:
            padded_latent = vae_model.encode(padded_images)
        p = self.latent_patch_size
        packed_latent_list = []
        for latent, shape in zip(padded_latent, patchified_vae_latent_shapes):
            if isinstance(shape, tuple) and len(shape) == 3:
                t_lat, h_lat, w_lat = shape
                latent = latent[:, :t_lat, : h_lat * p, : w_lat * p].reshape(
                    self.latent_channel, t_lat, h_lat, p, w_lat, p
                )
                latent = torch.einsum("cthpwq->thwpqc", latent).reshape(
                    -1, p * p * self.latent_channel
                )
            else:
                h_lat, w_lat = shape
                latent = latent[:, : h_lat * p, : w_lat * p].reshape(
                    self.latent_channel, h_lat, p, w_lat, p
                )
                latent = torch.einsum("chpwq->hwpqc", latent).reshape(
                    -1, p * p * self.latent_channel
                )
            packed_latent_list.append(latent)
        packed_latent = torch.cat(packed_latent_list, dim=0)
        packed_pos_embed = self.latent_pos_embed(packed_vae_position_ids)
        packed_timestep_embeds = self.time_embedder(packed_timesteps)
        packed_latent = (
            self.vae2llm(packed_latent) + packed_timestep_embeds + packed_pos_embed
        )
        total_len = int(packed_seqlens.sum().item())
        packed_text_embed = self.language_model.model.embed_tokens(packed_text_ids)
        packed_query_sequence = packed_latent.new_zeros(
            (total_len, packed_latent.shape[-1])
        )
        packed_query_sequence[packed_text_indexes] = packed_text_embed.to(
            packed_query_sequence.dtype
        )
        packed_query_sequence[packed_vae_token_indexes] = packed_latent.to(
            packed_query_sequence.dtype
        )
        extra_inputs = {}
        if self.use_moe:
            extra_inputs = {
                "mode": "gen",
                "packed_vae_token_indexes": packed_vae_token_indexes,
                "packed_text_indexes": packed_text_indexes,
            }
        output = self.language_model.forward(
            packed_query_sequence=packed_query_sequence,
            query_lens=packed_seqlens,
            packed_query_position_ids=packed_position_ids,
            past_key_values=past_key_values,
            update_past_key_values=True,
            is_causal=False,
            **extra_inputs,
        )
        return output.past_key_values
