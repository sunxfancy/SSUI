import PIL
from pydantic import BaseModel, ConfigDict, Field
from backend.model_manager.load.load_base import ModelLoaderConfig
from backend.model_manager.probe import ModelProbe
from backend.util.devices import TorchDevice

from typing import Callable, List, Optional, Tuple
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
from backend.util.freeu import FreeUConfig


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


class LoRAModel(BaseModel):
    lora: "LoadedModel" = Field(description="The lora model", validate=False)
    weight: float = Field(default=1, description="Weight to apply to lora model")
    model_config = ConfigDict(arbitrary_types_allowed=True)

class ControlLoRAModel(LoRAModel):
    img: PIL.Image.Image = Field(description="Image to use in structural conditioning", validate=False)
    model_config = ConfigDict(arbitrary_types_allowed=True)


class UNetModel(BaseModel):
    unet: "LoadedModel" = Field(description="The basic unet model", validate=False)
    scheduler: "LoadedModel" = Field(
        description="A scheduler object defined in the model", validate=False
    )
    loras: List[LoRAModel] = Field(
        default_factory=list, description="LoRAs to apply on model loading"
    )
    seamless_axes: List[str] = Field(
        default_factory=list, description='Axes("x" and "y") to which apply seamless'
    )
    freeu_config: Optional[FreeUConfig] = Field(default=None, description="Info to load freeu config")
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ClipModel(BaseModel):
    text_encoder: "LoadedModel" = Field(
        description="The text encoder model", validate=False
    )
    tokenizer: "LoadedModel" = Field(description="The tokenizer model", validate=False)
    skipped_layers: int = Field(
        default=0, description="Number of skipped layers in text_encoder"
    )
    loras: List[LoRAModel] = Field(
        default_factory=list, description="LoRAs to apply on model loading"
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)


class VAEModel(BaseModel):
    vae: "LoadedModel" = Field(description="The vae model", validate=False)
    seamless_axes: List[str] = Field(
        default_factory=list, description='Axes("x" and "y") to which apply seamless'
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)


def _load_model_service(
    service: ModelLoaderService, config: AnyModelConfig, submodel_type: SubModelType
) -> LoadedModel:
    return service.load_model(
        config.model_copy(update={"submodel_type": submodel_type}),
        submodel_type,
    )


def load_model(
    model_loader_service: ModelLoaderService, model_path: Path
) -> Tuple[UNetModel, ClipModel, VAEModel]:
    model_config = ModelProbe.probe(Path(model_path))
    unet = _load_model_service(model_loader_service, model_config, SubModelType.UNet)
    scheduler = _load_model_service(
        model_loader_service, model_config, SubModelType.Scheduler
    )
    vae = _load_model_service(model_loader_service, model_config, SubModelType.VAE)
    text_encoder = _load_model_service(
        model_loader_service, model_config, SubModelType.TextEncoder
    )
    tokenizer = _load_model_service(
        model_loader_service, model_config, SubModelType.Tokenizer
    )
    return (
        UNetModel(unet=unet, scheduler=scheduler),
        ClipModel(text_encoder=text_encoder, tokenizer=tokenizer),
        VAEModel(vae=vae),
    )


def load_sdxl_model(
    model_loader_service: ModelLoaderService, model_path: Path
) -> Tuple[UNetModel, ClipModel, VAEModel]:
    model_config = ModelProbe.probe(Path(model_path))
    unet = _load_model_service(model_loader_service, model_config, SubModelType.UNet)
    scheduler = _load_model_service(
        model_loader_service, model_config, SubModelType.Scheduler
    )
    vae = _load_model_service(model_loader_service, model_config, SubModelType.VAE)
    text_encoder = _load_model_service(
        model_loader_service, model_config, SubModelType.TextEncoder
    )
    tokenizer = _load_model_service(
        model_loader_service, model_config, SubModelType.Tokenizer
    )
    text_encoder2 = _load_model_service(
        model_loader_service, model_config, SubModelType.TextEncoder2
    )
    tokenizer2 = _load_model_service(
        model_loader_service, model_config, SubModelType.Tokenizer2
    )
    return (
        UNetModel(unet=unet, scheduler=scheduler),
        ClipModel(text_encoder=text_encoder, tokenizer=tokenizer),
        ClipModel(text_encoder=text_encoder2, tokenizer=tokenizer2),
        VAEModel(vae=vae),
    )


def load_sdxl_refiner_model(
    model_loader_service: ModelLoaderService, model_path: Path
) -> Tuple[UNetModel, ClipModel, VAEModel]:
    model_config = ModelProbe.probe(Path(model_path))
    unet = _load_model_service(model_loader_service, model_config, SubModelType.UNet)
    scheduler = _load_model_service(
        model_loader_service, model_config, SubModelType.Scheduler
    )
    vae = _load_model_service(model_loader_service, model_config, SubModelType.VAE)
    text_encoder2 = _load_model_service(
        model_loader_service, model_config, SubModelType.TextEncoder2
    )
    tokenizer2 = _load_model_service(
        model_loader_service, model_config, SubModelType.Tokenizer2
    )
    return (
        UNetModel(unet=unet, scheduler=scheduler),
        ClipModel(text_encoder=text_encoder2, tokenizer=tokenizer2),
        VAEModel(vae=vae),
    )


class FluxModel(BaseModel):
    transformer: "LoadedModel" = Field(
        description="The transformer model", validate=False
    )
    loras: List[LoRAModel] = Field(default_factory=list, description="LoRAs to apply on model loading")
    model_config = ConfigDict(arbitrary_types_allowed=True)


class T5EncoderModel(BaseModel):
    text_encoder: "LoadedModel" = Field(
        description="The text encoder model", validate=False
    )
    tokenizer: "LoadedModel" = Field(description="The tokenizer model", validate=False)
    max_seq_length: int = Field(default=512, description="The maximum sequence length")
    model_config = ConfigDict(arbitrary_types_allowed=True)


def load_flux_model(
    model_loader_service: ModelLoaderService,
    model_path: Path,
    t5_encoder_path: Path,
    clip_path: Path,
    vae_path: Path,
) -> Tuple[LoadedModel, LoadedModel, LoadedModel, LoadedModel]:
    model_config = ModelProbe.probe(Path(model_path))
    t5_config = ModelProbe.probe(Path(t5_encoder_path))
    clip_config = ModelProbe.probe(Path(clip_path))
    vae_config = ModelProbe.probe(Path(vae_path))

    transformer = _load_model_service(
        model_loader_service, model_config, SubModelType.Transformer
    )
    vae = _load_model_service(model_loader_service, vae_config, SubModelType.VAE)

    clip_tokenizer = _load_model_service(
        model_loader_service, clip_config, SubModelType.Tokenizer
    )
    clip_encoder = _load_model_service(
        model_loader_service, clip_config, SubModelType.TextEncoder
    )

    def preprocess_t5_encoder_model_identifier(model_identifier):
        """A helper function to normalize a T5 encoder model identifier so that T5 models associated with FLUX
        or SD3 models can be used interchangeably.
        """
        if model_identifier.base == BaseModelType.Any:
            return SubModelType.TextEncoder2
        elif model_identifier.base == BaseModelType.StableDiffusion3:
            return SubModelType.TextEncoder3
        else:
            raise ValueError(f"Unsupported model base: {model_identifier.base}")

    def preprocess_t5_tokenizer_model_identifier(model_identifier):
        """A helper function to normalize a T5 tokenizer model identifier so that T5 models associated with FLUX
        or SD3 models can be used interchangeably.
        """
        if model_identifier.base == BaseModelType.Any:
            return SubModelType.Tokenizer2
        elif model_identifier.base == BaseModelType.StableDiffusion3:
            return SubModelType.Tokenizer3
        else:
            raise ValueError(f"Unsupported model base: {model_identifier.base}")

    t5_tokenizer = _load_model_service(
        model_loader_service,
        t5_config,
        preprocess_t5_tokenizer_model_identifier(t5_config),
    )
    t5_encoder = _load_model_service(
        model_loader_service,
        t5_config,
        preprocess_t5_encoder_model_identifier(t5_config),
    )

    max_seq_lengths = {
        "flux-dev": 512,
        "flux-schnell": 256,
    }
    return (
        FluxModel(transformer=transformer),
        T5EncoderModel(
            text_encoder=t5_encoder,
            tokenizer=t5_tokenizer,
            max_seq_length=max_seq_lengths[model_config.config_path],
        ),
        ClipModel(text_encoder=clip_encoder, tokenizer=clip_tokenizer),
        VAEModel(vae=vae),
    )

def load_lora(
    model_loader_service: ModelLoaderService, 
    lora_path: Path,
    lora_weight: Optional[float] = None
) -> LoRAModel:
    """
    Load multiple Stable Diffusion 1 LoRA models 
    
    Args:
        model_loader_service: The model loader service
        lora_path: LoRA model paths
        lora_weight: LoRA weights, if not provided all models use default weight of 1.0
        
    Returns:
        LoRAModel: loaded LoRA model objects
    """
    # Handle weights parameter
    if lora_weight is None:
        lora_weight = 1.0   

    # Probe LoRA model configuration
    lora_config = ModelProbe.probe(Path(lora_path))
    # Load LoRA model
    lora = _load_model_service(model_loader_service, lora_config, None)
    
    # Create LoRAModel object
    lora_model = LoRAModel(lora=lora,weight=lora_weight)
  
    return lora_model
