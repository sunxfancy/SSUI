from dataclasses import dataclass
from backend.model_manager.load.load_base import ModelLoaderConfig
from backend.model_manager.probe import ModelProbe
from backend.util.devices import TorchDevice

from typing import Any, Callable, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from safetensors.torch import load_file as safetensors_load_file
from torch import load as torch_load


from backend.model_manager import AnyModel, AnyModelConfig, SubModelType
from backend.model_manager.load import (
    LoadedModel,
    LoadedModelWithoutConfig,
    ModelLoaderRegistry,
)
from backend.model_manager.load.model_cache.model_cache import ModelCache
from backend.model_manager.load.model_loaders.generic_diffusers import (
    GenericDiffusersLoader,
)
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
        return LoadedModelWithoutConfig(
            cache_record=ram_cache.get(key=cache_key), cache=ram_cache
        )
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
        return load_class.from_pretrained(
            model_path, torch_dtype=TorchDevice.choose_torch_dtype()
        )

    loader = loader or (
        diffusers_load_directory
        if model_path.is_dir()
        else (
            torch_load_file
            if model_path.suffix.endswith((".ckpt", ".pt", ".pth", ".bin"))
            else lambda path: safetensors_load_file(path, device="cpu")
        )
    )
    assert loader is not None
    raw_model = loader(model_path)
    ram_cache.put(key=cache_key, model=raw_model)
    return LoadedModelWithoutConfig(
        cache_record=ram_cache.get(key=cache_key), cache=ram_cache
    )


class ModelLoaderService:
    def __init__(self):
        self._app_config = ModelLoaderConfig()
        self._ram_cache = ModelCache(
            execution_device_working_mem_gb=3,
            enable_partial_loading=False,
            keep_ram_copy_of_weights=True,
            max_ram_cache_size_gb=None,
            max_vram_cache_size_gb=None,
            execution_device=TorchDevice.choose_torch_device(),
            logger=None,
        )

    def load_model(
        self, model_config: AnyModelConfig, submodel_type: Optional[SubModelType] = None
    ) -> LoadedModel:
        implementation, model_config, submodel_type = (
            ModelLoaderRegistry.get_implementation(model_config, submodel_type)
        )
        loaded_model: LoadedModel = implementation(
            app_config=self._app_config,
            logger=None,
            ram_cache=self._ram_cache,
        ).load_model(model_config, submodel_type)
        return loaded_model

@dataclass
class UNetModel:
    unet: LoadedModel
    scheduler: LoadedModel

@dataclass
class ClipModel:
    text_encoder: LoadedModel
    tokenizer: LoadedModel

@dataclass
class VAEModel:
    vae: LoadedModel


def load_model(model_loader_service: ModelLoaderService, model_path: Path) -> Tuple[UNetModel, ClipModel, VAEModel]:
    model_config = ModelProbe.probe(Path(model_path))

    unet = model_loader_service.load_model(
        model_config.model_copy(update={"submodel_type": SubModelType.UNet}),
        SubModelType.UNet,
    )
    scheduler = model_loader_service.load_model(
        model_config.model_copy(update={"submodel_type": SubModelType.Scheduler}),
        SubModelType.Scheduler,
    )
    vae = model_loader_service.load_model(
        model_config.model_copy(update={"submodel_type": SubModelType.VAE}),
        SubModelType.VAE,
    )
    text_encoder = model_loader_service.load_model(
        model_config.model_copy(update={"submodel_type": SubModelType.TextEncoder}),
        SubModelType.TextEncoder,
    )
    tokenizer = model_loader_service.load_model(
        model_config.model_copy(update={"submodel_type": SubModelType.Tokenizer}),
        SubModelType.Tokenizer,
    )

    return UNetModel(unet, scheduler), ClipModel(text_encoder, tokenizer), VAEModel(vae)
