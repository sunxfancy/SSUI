"""Qwen-Image workflow nodes backed by the vendored DiffSynth pipeline.

The Video extension already owns the DiffSynth runtime, so the image nodes live
here to avoid shipping a second copy of the same model implementation.
"""

import os
from typing import Optional

import torch

from diffsynth.pipelines.qwen_image import QwenImagePipeline
from diffsynth.utils import ModelConfig
from ssui.annotation import param
from ssui.base import Image as SSUIImage, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Select, Slider, Switch
from ssui_image.PixelArt import finalize_pixel_art_image


QWEN_IMAGE_MODEL_ID = "Qwen/Qwen-Image"
QWEN_IMAGE_EDIT_MODEL_ID = "Qwen/Qwen-Image-Edit-2509"
QWEN_IMAGE_PROCESSOR_ID = "Qwen/Qwen-Image-Edit"


def _model_config(model_id: str, pattern: str, low_vram: bool) -> ModelConfig:
    return ModelConfig(
        model_id=model_id,
        origin_file_pattern=pattern,
        download_resource=os.environ.get(
            "SSUI_QWEN_IMAGE_DOWNLOAD_SOURCE", "ModelScope"
        ),
        local_model_path=os.environ.get("SSUI_QWEN_IMAGE_MODEL_ROOT", "models"),
        offload_device="cpu" if low_vram else None,
    )


def _load_pipeline(
    model_id: str,
    *,
    edit: bool,
    low_vram: bool,
    vram_limit_gib: Optional[float] = None,
) -> QwenImagePipeline:
    if not torch.cuda.is_available():
        raise RuntimeError("Qwen-Image in SSUI currently requires a CUDA GPU")

    pipe = QwenImagePipeline.from_pretrained(
        torch_dtype=torch.bfloat16,
        device="cuda",
        model_configs=[
            _model_config(
                model_id,
                "transformer/diffusion_pytorch_model*.safetensors",
                low_vram,
            ),
            _model_config(
                QWEN_IMAGE_MODEL_ID,
                "text_encoder/model*.safetensors",
                low_vram,
            ),
            _model_config(
                QWEN_IMAGE_MODEL_ID,
                "vae/diffusion_pytorch_model.safetensors",
                low_vram,
            ),
        ],
        tokenizer_config=(
            None
            if edit
            else _model_config(QWEN_IMAGE_MODEL_ID, "tokenizer/", low_vram)
        ),
        processor_config=(
            _model_config(QWEN_IMAGE_PROCESSOR_ID, "processor/", low_vram)
            if edit
            else None
        ),
    )
    if low_vram:
        env_limit = os.environ.get("SSUI_QWEN_IMAGE_VRAM_LIMIT_GIB")
        vram_limit = vram_limit_gib
        if vram_limit is None and env_limit:
            vram_limit = float(env_limit)
        pipe.enable_vram_management(
            vram_limit=vram_limit if vram_limit and vram_limit > 0 else None
        )
    return pipe


class QwenImageModel:
    """Text-to-image Qwen model handle.

    ``model_id`` may point at a DiffSynth-compatible Qwen-Image transformer.
    Shared text encoder, VAE and tokenizer files continue to come from the
    official ``Qwen/Qwen-Image`` repository.
    """

    def __init__(
        self,
        pipe: Optional[QwenImagePipeline] = None,
        model_id: str = QWEN_IMAGE_MODEL_ID,
    ):
        self.pipe = pipe
        self.model_id = model_id

    @staticmethod
    def load(
        model_id: str = QWEN_IMAGE_MODEL_ID,
        low_vram: bool = True,
        vram_limit_gib: float = 0.0,
    ) -> "QwenImageModel":
        return QwenImageModel(
            pipe=_load_pipeline(
                model_id,
                edit=False,
                low_vram=low_vram,
                vram_limit_gib=vram_limit_gib or None,
            ),
            model_id=model_id,
        )


class QwenImageEditModel:
    """Reference-image editing model handle.

    The default is the multi-reference 2509 checkpoint, which is supported by
    the DiffSynth version bundled in this repository.
    """

    def __init__(
        self,
        pipe: Optional[QwenImagePipeline] = None,
        model_id: str = QWEN_IMAGE_EDIT_MODEL_ID,
    ):
        self.pipe = pipe
        self.model_id = model_id

    @staticmethod
    def load(
        model_id: str = QWEN_IMAGE_EDIT_MODEL_ID,
        low_vram: bool = True,
        vram_limit_gib: float = 0.0,
    ) -> "QwenImageEditModel":
        return QwenImageEditModel(
            pipe=_load_pipeline(
                model_id,
                edit=True,
                low_vram=low_vram,
                vram_limit_gib=vram_limit_gib or None,
            ),
            model_id=model_id,
        )


def _require_pipe(model) -> QwenImagePipeline:
    if model is None or model.pipe is None:
        raise ValueError("Qwen-Image model is not loaded; call its load() method first")
    return model.pipe


@param("seed", Random(), default=42)
@param("width", Slider(256, 1536, 16), default=1024)
@param("height", Slider(256, 1536, 16), default=1024)
@param("steps", Slider(1, 80, 1), default=40)
@param("CFG", Slider(1, 10, 0.1), default=4.0)
@param("tiled", Switch(), default=False)
def QwenImageGenerate(
    config: SSUIConfig,
    model: QwenImageModel,
    positive: Prompt,
    negative: Prompt,
) -> SSUIImage:
    if config.is_prepare():
        return SSUIImage()
    image = _require_pipe(model)(
        prompt=positive.text,
        negative_prompt=negative.text,
        seed=config["seed"],
        width=config["width"],
        height=config["height"],
        num_inference_steps=config["steps"],
        cfg_scale=config["CFG"],
        tiled=config["tiled"],
    )
    return SSUIImage(image)


@param("seed", Random(), default=42)
@param("width", Slider(256, 1536, 16), default=1024)
@param("height", Slider(256, 1536, 16), default=1024)
@param("steps", Slider(1, 80, 1), default=40)
@param("CFG", Slider(1, 10, 0.1), default=4.0)
@param("auto_resize_reference", Switch(), default=True)
@param("tiled", Switch(), default=False)
def QwenImageEdit(
    config: SSUIConfig,
    model: QwenImageEditModel,
    reference: SSUIImage,
    positive: Prompt,
    negative: Prompt,
) -> SSUIImage:
    if config.is_prepare():
        return SSUIImage()
    if reference is None or reference._image is None:
        raise ValueError("QwenImageEdit requires a reference image")

    # Qwen-Image-Edit-2509 expects a list even for one reference image.
    image = _require_pipe(model)(
        prompt=positive.text,
        negative_prompt=negative.text,
        edit_image=[reference._image.convert("RGB")],
        edit_image_auto_resize=config["auto_resize_reference"],
        seed=config["seed"],
        width=config["width"],
        height=config["height"],
        num_inference_steps=config["steps"],
        cfg_scale=config["CFG"],
        tiled=config["tiled"],
    )
    return SSUIImage(image)


def _finish_pixel_asset(config: SSUIConfig, image) -> SSUIImage:
    return finalize_pixel_art_image(
        SSUIImage(image),
        width=config["pixel_width"],
        height=config["pixel_height"],
        colors=config["colors"],
        alpha_threshold=config["alpha_threshold"],
        downsample=config["downsample"],
        preview_scale=config["preview_scale"],
    )


@param("seed", Random(), default=42)
@param("width", Slider(256, 1024, 64), default=512)
@param("height", Slider(256, 1024, 64), default=512)
@param("steps", Slider(1, 50, 1), default=20)
@param("CFG", Slider(1, 10, 0.1), default=1.0)
@param("tiled", Switch(), default=False)
@param("pixel_width", Slider(8, 256, 1), default=64)
@param("pixel_height", Slider(8, 256, 1), default=64)
@param("colors", Slider(2, 256, 1), default=24)
@param("alpha_threshold", Slider(0, 255, 1), default=128)
@param("downsample", Select("box", "nearest"), default="box")
@param("preview_scale", Slider(1, 16, 1), default=4)
def QwenPixelArtGenerate(
    config: SSUIConfig,
    model: QwenImageModel,
    positive: Prompt,
    negative: Prompt,
) -> SSUIImage:
    """Generate and finish a game-ready pixel asset in one node."""

    if config.is_prepare():
        return SSUIImage()
    image = _require_pipe(model)(
        prompt=positive.text,
        negative_prompt=negative.text,
        seed=config["seed"],
        width=config["width"],
        height=config["height"],
        num_inference_steps=config["steps"],
        cfg_scale=config["CFG"],
        tiled=config["tiled"],
    )
    return _finish_pixel_asset(config, image)


@param("seed", Random(), default=42)
@param("width", Slider(256, 1024, 64), default=512)
@param("height", Slider(256, 1024, 64), default=512)
@param("steps", Slider(1, 50, 1), default=20)
@param("CFG", Slider(1, 10, 0.1), default=1.0)
@param("auto_resize_reference", Switch(), default=True)
@param("tiled", Switch(), default=False)
@param("pixel_width", Slider(8, 256, 1), default=64)
@param("pixel_height", Slider(8, 256, 1), default=64)
@param("colors", Slider(2, 256, 1), default=24)
@param("alpha_threshold", Slider(0, 255, 1), default=128)
@param("downsample", Select("box", "nearest"), default="box")
@param("preview_scale", Slider(1, 16, 1), default=4)
def QwenPixelArtEdit(
    config: SSUIConfig,
    model: QwenImageEditModel,
    reference: SSUIImage,
    positive: Prompt,
    negative: Prompt,
) -> SSUIImage:
    """Edit a reference and finish it as a game-ready pixel asset."""

    if config.is_prepare():
        return SSUIImage()
    if reference is None or reference._image is None:
        raise ValueError("QwenPixelArtEdit requires a reference image")
    image = _require_pipe(model)(
        prompt=positive.text,
        negative_prompt=negative.text,
        edit_image=[reference._image.convert("RGB")],
        edit_image_auto_resize=config["auto_resize_reference"],
        seed=config["seed"],
        width=config["width"],
        height=config["height"],
        num_inference_steps=config["steps"],
        cfg_scale=config["CFG"],
        tiled=config["tiled"],
    )
    return _finish_pixel_asset(config, image)
