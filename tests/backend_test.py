import unittest
from backend.model_manager.load.load_base import ModelLoaderConfig
from backend.stable_diffusion.diffusion_backend import StableDiffusionBackend
from backend.stable_diffusion.extensions_manager import ExtensionsManager
from backend.util.devices import TorchDevice

from pydantic import BaseModel, ConfigDict, Field, RootModel, TypeAdapter, model_validator
from typing import Any, Callable, Optional, Tuple
import torch
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Type

from safetensors.torch import load_file as safetensors_load_file
from torch import load as torch_load


from backend.model_manager import AnyModel, AnyModelConfig, SubModelType
from backend.model_manager.load import (
    LoadedModel,
    LoadedModelWithoutConfig,
    ModelLoaderRegistry,
    ModelLoaderRegistryBase,
)
from backend.model_manager.load.model_cache.model_cache import ModelCache
from backend.model_manager.load.model_loaders.generic_diffusers import GenericDiffusersLoader
from backend.util.devices import TorchDevice

class BaseModelType(str, Enum):
    """Base model type."""

    Any = "any"
    StableDiffusion1 = "sd-1"
    StableDiffusion2 = "sd-2"
    StableDiffusion3 = "sd-3"
    StableDiffusionXL = "sdxl"
    StableDiffusionXLRefiner = "sdxl-refiner"
    Flux = "flux"
    # Kandinsky2_1 = "kandinsky-2.1"

class ModelType(str, Enum):
    """Model type."""

    ONNX = "onnx"
    Main = "main"
    VAE = "vae"
    LoRA = "lora"
    ControlLoRa = "control_lora"
    ControlNet = "controlnet"  # used by model_probe
    TextualInversion = "embedding"
    IPAdapter = "ip_adapter"
    CLIPVision = "clip_vision"
    CLIPEmbed = "clip_embed"
    T2IAdapter = "t2i_adapter"
    T5Encoder = "t5_encoder"
    SpandrelImageToImage = "spandrel_image_to_image"


class SubModelType(str, Enum):
    """Submodel type."""

    UNet = "unet"
    Transformer = "transformer"
    TextEncoder = "text_encoder"
    TextEncoder2 = "text_encoder_2"
    TextEncoder3 = "text_encoder_3"
    Tokenizer = "tokenizer"
    Tokenizer2 = "tokenizer_2"
    Tokenizer3 = "tokenizer_3"
    VAE = "vae"
    VAEDecoder = "vae_decoder"
    VAEEncoder = "vae_encoder"
    Scheduler = "scheduler"
    SafetyChecker = "safety_checker"

class ModelIdentifierField(BaseModel):
    key: str = Field(description="The model's unique key")
    hash: str = Field(description="The model's BLAKE3 hash")
    name: str = Field(description="The model's name")
    base: BaseModelType = Field(description="The model's base model type")
    type: ModelType = Field(description="The model's type")
    submodel_type: Optional[SubModelType] = Field(
        description="The submodel to load, if this is a main model", default=None
    )

    @classmethod
    def from_config(
        cls, config: "AnyModelConfig", submodel_type: Optional[SubModelType] = None
    ) -> "ModelIdentifierField":
        return cls(
            key=config.key,
            hash=config.hash,
            name=config.name,
            base=config.base,
            type=config.type,
            submodel_type=submodel_type,
        )



class LatentsField(BaseModel):
    """A latents tensor primitive field"""

    latents_name: str = Field(description="The name of the latents")
    seed: Optional[int] = Field(default=None, description="Seed used to generate this latents")


def load_model_from_path(
        model_path: Path, loader: Optional[Callable[[Path], AnyModel]] = None
    ) -> LoadedModelWithoutConfig:
        ram_cache = ModelCache(
            execution_device_working_mem_gb=3,
            enable_partial_loading=False,
            keep_ram_copy_of_weights=True,
            max_ram_cache_size_gb=None,
            max_vram_cache_size_gb=None,
            execution_device=TorchDevice.choose_torch_device(),
            logger=None,
        )

        cache_key = str(model_path)
        try:
            return LoadedModelWithoutConfig(cache_record=ram_cache.get(key=cache_key), cache=ram_cache)
        except IndexError:
            pass

        def torch_load_file(checkpoint: Path) -> AnyModel:
            result = torch_load(checkpoint, map_location="cpu")
            return result

        def diffusers_load_directory(directory: Path) -> AnyModel:
            load_class = GenericDiffusersLoader(
                app_config=ModelLoaderConfig(),
                logger=None,
                ram_cache=ram_cache,
            ).get_hf_load_class(directory)
            return load_class.from_pretrained(model_path, torch_dtype=TorchDevice.choose_torch_dtype())

        loader = loader or (
            diffusers_load_directory
            if model_path.is_dir()
            else torch_load_file
            if model_path.suffix.endswith((".ckpt", ".pt", ".pth", ".bin"))
            else lambda path: safetensors_load_file(path, device="cpu")
        )
        assert loader is not None
        raw_model = loader(model_path)
        ram_cache.put(key=cache_key, model=raw_model)
        return LoadedModelWithoutConfig(cache_record=ram_cache.get(key=cache_key), cache=ram_cache)


def generate_image(prompt: str, negative: str):
    model =load_model_from_path(Path("D:\\StableDiffusion\\stable-diffusion-webui\\models\\Stable-diffusion\\animefull-latest.ckpt"))
    print("model loaded: ", model)

class TestBackend(unittest.TestCase):
    def test_backend(self):
        generate_image("a beautiful girl", "a bad image")


