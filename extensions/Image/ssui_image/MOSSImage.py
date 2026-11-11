"""MOSS-Image nodes using SSUI's shared runtime and local backend implementation."""
from pathlib import Path
from threading import RLock

import torch

from ssui.annotation import param
from ssui.base import Image, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch


_PIPELINE_CACHE = {}
_CACHE_LOCK = RLock()


class MOSSImageModel:
    def __init__(self, model_path: str = "", pipeline=None):
        self.model_path = model_path
        self.pipeline = pipeline

    @staticmethod
    def load(model_path: str, cpu_offload: bool = True, revision: str = "") -> "MOSSImageModel":
        """Load an official Base/SFT HF bundle, local directory or Hub repo ID.

        No remote Python is executed. CUDA/ROCm uses BF16 and CPU uses FP32;
        VAE always uses FP32. Component offload requires sufficient system RAM.
        """
        from backend.moss_image.pipeline import MOSSPipeline

        # MPS requires separate real-weight validation before being enabled.
        device = "cuda" if torch.cuda.is_available() else "cpu"
        path = Path(model_path).expanduser()
        source = str(path.resolve()) if path.is_dir() else model_path
        key = (source, cpu_offload, revision, device)
        with _CACHE_LOCK:
            if key not in _PIPELINE_CACHE:
                _PIPELINE_CACHE[key] = MOSSPipeline.from_pretrained(
                    source, device=device, cpu_offload=cpu_offload, revision=revision or None,
                )
            return MOSSImageModel(source, _PIPELINE_CACHE[key])

    @staticmethod
    def clear_cache() -> None:
        with _CACHE_LOCK:
            for pipeline in _PIPELINE_CACHE.values():
                pipeline.close()
            _PIPELINE_CACHE.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


@param("width", Slider(256, 2048, 16), default=1024)
@param("height", Slider(256, 2048, 16), default=1024)
@param("steps", Slider(1, 100, 1), default=50)
@param("guidance", Slider(0, 10, 0.1), default=3.0)
@param("shift", Slider(0.1, 10, 0.1), default=5.0)
@param("skip_negative_layer_22", Switch(), default=True)
@param("seed", Random(), default=42)
def MOSSImageGenerate(config: SSUIConfig, model: MOSSImageModel, prompt: Prompt,
                      negative_prompt: Prompt) -> Image:
    """Generate from a caption or a MOSS layout JSON string in the prompt."""
    if config.is_prepare():
        return Image()
    if model.pipeline is None:
        raise ValueError("MOSS-Image model is not loaded")
    image = model.pipeline(
        prompt=prompt.text, negative_prompt=negative_prompt.text,
        width=int(config["width"]), height=int(config["height"]),
        steps=int(config["steps"]), guidance=float(config["guidance"]),
        shift=float(config["shift"]), seed=int(config["seed"]),
        uncond_skip_layers=(22,) if config["skip_negative_layer_22"] else (),
    )
    return Image(image)
