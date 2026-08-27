from pathlib import Path
from typing import List

import torch

from ssui.annotation import param
from ssui.base import Image, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider


_PIPELINE_CACHE = {}


def _resolve_device() -> str:
    if torch.cuda.is_available():
        # PyTorch uses the cuda device name for both CUDA and ROCm builds.
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _resolve_dtype(dtype: str, device: str) -> torch.dtype:
    dtypes = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }
    if dtype not in dtypes:
        raise ValueError(f"Unsupported FLUX.2 dtype: {dtype}")
    if device == "cpu" and dtype != "float32":
        return torch.float32
    return dtypes[dtype]


class Flux2KleinModel:
    """Loaded FLUX.2 Klein pipeline shared by generation and editing workflows."""

    def __init__(self, model_path: str = "", pipeline=None):
        self.model_path = model_path
        self.pipeline = pipeline

    @staticmethod
    def load(
        model_path: str,
        cpu_offload: bool = True,
        dtype: str = "bfloat16",
    ) -> "Flux2KleinModel":
        """Load a local Diffusers FLUX.2 Klein repository.

        The cache avoids reloading the 4B pipeline for every executor task. A
        Hugging Face repo id is also accepted, although preset installs pass a
        local directory.
        """
        try:
            from diffusers import Flux2KleinPipeline
        except ImportError as exc:
            raise RuntimeError(
                "FLUX.2 Klein requires diffusers>=0.36.0 and transformers>=4.51.3."
            ) from exc

        device = _resolve_device()
        torch_dtype = _resolve_dtype(dtype, device)
        path = Path(model_path).expanduser()
        cache_path = str(path.resolve()) if path.exists() else model_path
        cache_key = (cache_path, cpu_offload, str(torch_dtype), device)
        pipeline = _PIPELINE_CACHE.get(cache_key)

        if pipeline is None:
            pipeline = Flux2KleinPipeline.from_pretrained(
                model_path,
                torch_dtype=torch_dtype,
            )
            if cpu_offload and device == "cuda":
                pipeline.enable_model_cpu_offload()
            else:
                pipeline.to(device)
            _PIPELINE_CACHE[cache_key] = pipeline

        return Flux2KleinModel(model_path=cache_path, pipeline=pipeline)

    @staticmethod
    def clear_cache() -> None:
        _PIPELINE_CACHE.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


@param("width", Slider(256, 2048, 64, labels=[512, 768, 1024, 1536, 2048]), default=1024)
@param("height", Slider(256, 2048, 64, labels=[512, 768, 1024, 1536, 2048]), default=1024)
@param("steps", Slider(1, 50, 1, labels=[1, 4, 8, 20, 28, 50]), default=4)
@param("guidance", Slider(1, 10, 0.1), default=1.0)
@param("seed", Random(), default=123454321)
def Flux2KleinGenerate(
    config: SSUIConfig,
    model: Flux2KleinModel,
    prompt: Prompt,
    reference_images: List[Image],
) -> Image:
    """Generate or edit with zero to four reference images."""
    if config.is_prepare():
        return Image()

    if model.pipeline is None:
        raise ValueError("FLUX.2 Klein is not loaded")

    references = [item._image for item in reference_images]
    if any(item is None for item in references):
        raise ValueError("Every FLUX.2 reference must contain an image")
    if len(references) > 4:
        raise ValueError("FLUX.2 Klein supports at most four reference images")

    generator = torch.Generator(device="cpu").manual_seed(int(config["seed"]))
    result = model.pipeline(
        image=references or None,
        prompt=prompt.text,
        height=int(config["height"]),
        width=int(config["width"]),
        num_inference_steps=int(config["steps"]),
        guidance_scale=float(config["guidance"]),
        generator=generator,
    )
    return Image(result.images[0])
