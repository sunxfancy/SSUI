import unittest
from backend.model_manager.config import MainCheckpointConfig, ModelSourceType
from backend.model_manager.load.load_base import ModelLoaderConfig
from backend.model_manager.probe import ModelProbe
from backend.model_patcher import ModelPatcher
from backend.stable_diffusion.denoise_context import DenoiseContext, DenoiseInputs
from backend.stable_diffusion.diffusion.conditioning_data import (
    BasicConditioningInfo,
    Range,
    SDXLConditioningInfo,
    TextConditioningData,
    TextConditioningRegions,
)
from backend.stable_diffusion.diffusion_backend import StableDiffusionBackend
from backend.stable_diffusion.extension_callback_type import ExtensionCallbackType
from backend.stable_diffusion.extensions.preview import PipelineIntermediateState
from backend.stable_diffusion.extensions_manager import ExtensionsManager
from backend.util.devices import TorchDevice
from transformers import CLIPTextModel, CLIPTextModelWithProjection, CLIPTokenizer
import torchvision
import inspect
from contextlib import ExitStack

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    TypeAdapter,
    model_validator,
)
from typing import Any, Callable, Dict, Optional, Tuple, Union
import torch
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Type

from safetensors.torch import load_file as safetensors_load_file
from torch import load as torch_load
from compel import Compel, ReturnedEmbeddingsType
from compel.prompt_parser import (
    Blend,
    Conjunction,
    CrossAttentionControlSubstitute,
    FlattenedPrompt,
    Fragment,
)

from backend.model_manager import AnyModel, AnyModelConfig, SubModelType
from backend.model_manager.load import (
    LoadedModel,
    LoadedModelWithoutConfig,
    ModelLoaderRegistry,
    ModelLoaderRegistryBase,
)
from backend.model_manager.load.model_cache.model_cache import ModelCache
from backend.model_manager.load.model_loaders.generic_diffusers import (
    GenericDiffusersLoader,
)
from backend.util.devices import TorchDevice
from backend.util.mask import to_standard_float_mask

from diffusers.configuration_utils import ConfigMixin
from diffusers.schedulers.scheduling_dpmsolver_multistep import (
    DPMSolverMultistepScheduler,
)
from diffusers.schedulers.scheduling_dpmsolver_sde import DPMSolverSDEScheduler
from diffusers.schedulers.scheduling_dpmsolver_singlestep import (
    DPMSolverSinglestepScheduler,
)
from diffusers.schedulers.scheduling_tcd import TCDScheduler
from diffusers.schedulers.scheduling_utils import SchedulerMixin as Scheduler

from backend.stable_diffusion.schedulers import SCHEDULER_MAP
from backend.stable_diffusion.schedulers.schedulers import SCHEDULER_NAME_VALUES
from backend.stable_diffusion.diffusion.custom_atttention import CustomAttnProcessor2_0

from diffusers.models.autoencoders.autoencoder_kl import AutoencoderKL
from diffusers.models.autoencoders.autoencoder_tiny import AutoencoderTiny

from diffusers.image_processor import VaeImageProcessor

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
    seed: Optional[int] = Field(
        default=None, description="Seed used to generate this latents"
    )


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


def create_conditioning(prompt: str, tokenizer: LoadedModel, text_encoder: LoadedModel):
    with (text_encoder.model_on_device() as (cached_weights, text_encoder),):
        tokenizer = tokenizer.model
        print("text_encoder: ", text_encoder)
        print("tokenizer: ", tokenizer)
        assert isinstance(text_encoder, CLIPTextModel)
        assert isinstance(tokenizer, CLIPTokenizer)

        compel = Compel(
            tokenizer=tokenizer,
            text_encoder=text_encoder,
            dtype_for_device_getter=TorchDevice.choose_torch_dtype,
            truncate_long_prompts=False,
            device=TorchDevice.choose_torch_device(),
        )

        conjunction = Compel.parse_prompt_string(prompt)
        c, _options = compel.build_conditioning_tensor_for_conjunction(conjunction)
        c = c.detach().to("cpu")
        return BasicConditioningInfo(embeds=c)


def get_noise(
    width: int,
    height: int,
    device: torch.device,
    seed: int = 0,
    latent_channels: int = 4,
    downsampling_factor: int = 8,
    use_cpu: bool = True,
    perlin: float = 0.0,
):
    """Generate noise for a given image size."""
    noise_device_type = "cpu" if use_cpu else device.type

    # limit noise to only the diffusion image channels, not the mask channels
    input_channels = min(latent_channels, 4)
    generator = torch.Generator(device=noise_device_type).manual_seed(seed)

    noise_tensor = torch.randn(
        [
            1,
            input_channels,
            height // downsampling_factor,
            width // downsampling_factor,
        ],
        dtype=TorchDevice.choose_torch_dtype(device=device),
        device=noise_device_type,
        generator=generator,
    ).to("cpu")

    return noise_tensor


def get_conditioning_data(
    positive_conditioning_field: Union[
        BasicConditioningInfo, list[BasicConditioningInfo]
    ],
    negative_conditioning_field: Union[
        BasicConditioningInfo, list[BasicConditioningInfo]
    ],
    latent_height: int,
    latent_width: int,
    device: torch.device,
    dtype: torch.dtype,
    cfg_scale: float | list[float],
    steps: int,
    cfg_rescale_multiplier: float,
) -> TextConditioningData:

    def _get_text_embeddings_and_masks(
        cond_list: list[BasicConditioningInfo],
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[
        Union[list[BasicConditioningInfo], list[SDXLConditioningInfo]],
        list[Optional[torch.Tensor]],
    ]:
        """Get the text embeddings and masks from the input conditioning fields."""
        text_embeddings: Union[
            list[BasicConditioningInfo], list[SDXLConditioningInfo]
        ] = []
        text_embeddings_masks: list[Optional[torch.Tensor]] = []
        for cond in cond_list:
            text_embeddings.append(cond.to(device=device, dtype=dtype))
            text_embeddings_masks.append(None)

        return text_embeddings, text_embeddings_masks

    def _preprocess_regional_prompt_mask(
        mask: Optional[torch.Tensor],
        target_height: int,
        target_width: int,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        """Preprocess a regional prompt mask to match the target height and width.
        If mask is None, returns a mask of all ones with the target height and width.
        If mask is not None, resizes the mask to the target height and width using 'nearest' interpolation.

        Returns:
            torch.Tensor: The processed mask. shape: (1, 1, target_height, target_width).
        """

        if mask is None:
            return torch.ones((1, 1, target_height, target_width), dtype=dtype)

        mask = to_standard_float_mask(mask, out_dtype=dtype)

        tf = torchvision.transforms.Resize(
            (target_height, target_width),
            interpolation=torchvision.transforms.InterpolationMode.NEAREST,
        )

        # Add a batch dimension to the mask, because torchvision expects shape (batch, channels, h, w).
        mask = mask.unsqueeze(0)  # Shape: (1, h, w) -> (1, 1, h, w)
        resized_mask = tf(mask)
        return resized_mask

    def _concat_regional_text_embeddings(
        text_conditionings: Union[
            list[BasicConditioningInfo], list[SDXLConditioningInfo]
        ],
        masks: Optional[list[Optional[torch.Tensor]]],
        latent_height: int,
        latent_width: int,
        dtype: torch.dtype,
    ) -> tuple[
        Union[BasicConditioningInfo, SDXLConditioningInfo],
        Optional[TextConditioningRegions],
    ]:
        """Concatenate regional text embeddings into a single embedding and track the region masks accordingly."""
        if masks is None:
            masks = [None] * len(text_conditionings)
        assert len(text_conditionings) == len(masks)

        is_sdxl = type(text_conditionings[0]) is SDXLConditioningInfo

        all_masks_are_none = all(mask is None for mask in masks)

        text_embedding = []
        pooled_embedding = None
        add_time_ids = None
        cur_text_embedding_len = 0
        processed_masks = []
        embedding_ranges = []

        for prompt_idx, text_embedding_info in enumerate(text_conditionings):
            mask = masks[prompt_idx]

            if is_sdxl:
                # We choose a random SDXLConditioningInfo's pooled_embeds and add_time_ids here, with a preference for
                # prompts without a mask. We prefer prompts without a mask, because they are more likely to contain
                # global prompt information.  In an ideal case, there should be exactly one global prompt without a
                # mask, but we don't enforce this.

                # HACK(ryand): The fact that we have to choose a single pooled_embedding and add_time_ids here is a
                # fundamental interface issue. The SDXL Compel nodes are not designed to be used in the way that we use
                # them for regional prompting. Ideally, the DenoiseLatents invocation should accept a single
                # pooled_embeds tensor and a list of standard text embeds with region masks. This change would be a
                # pretty major breaking change to a popular node, so for now we use this hack.
                if pooled_embedding is None or mask is None:
                    pooled_embedding = text_embedding_info.pooled_embeds
                if add_time_ids is None or mask is None:
                    add_time_ids = text_embedding_info.add_time_ids

            text_embedding.append(text_embedding_info.embeds)
            if not all_masks_are_none:
                embedding_ranges.append(
                    Range(
                        start=cur_text_embedding_len,
                        end=cur_text_embedding_len
                        + text_embedding_info.embeds.shape[1],
                    )
                )
                processed_masks.append(
                    _preprocess_regional_prompt_mask(
                        mask, latent_height, latent_width, dtype=dtype
                    )
                )

            cur_text_embedding_len += text_embedding_info.embeds.shape[1]

        text_embedding = torch.cat(text_embedding, dim=1)
        assert len(text_embedding.shape) == 3  # batch_size, seq_len, token_len

        regions = None
        if not all_masks_are_none:
            regions = TextConditioningRegions(
                masks=torch.cat(processed_masks, dim=1),
                ranges=embedding_ranges,
            )

        if is_sdxl:
            return (
                SDXLConditioningInfo(
                    embeds=text_embedding,
                    pooled_embeds=pooled_embedding,
                    add_time_ids=add_time_ids,
                ),
                regions,
            )
        return BasicConditioningInfo(embeds=text_embedding), regions

    # Main workflow starts here
    # Normalize positive_conditioning_field and negative_conditioning_field to lists.
    cond_list = positive_conditioning_field
    if not isinstance(cond_list, list):
        cond_list = [cond_list]
    uncond_list = negative_conditioning_field
    if not isinstance(uncond_list, list):
        uncond_list = [uncond_list]

    cond_text_embeddings, cond_text_embedding_masks = _get_text_embeddings_and_masks(
        cond_list, device, dtype
    )
    uncond_text_embeddings, uncond_text_embedding_masks = (
        _get_text_embeddings_and_masks(uncond_list, device, dtype)
    )

    cond_text_embedding, cond_regions = _concat_regional_text_embeddings(
        text_conditionings=cond_text_embeddings,
        masks=cond_text_embedding_masks,
        latent_height=latent_height,
        latent_width=latent_width,
        dtype=dtype,
    )
    uncond_text_embedding, uncond_regions = _concat_regional_text_embeddings(
        text_conditionings=uncond_text_embeddings,
        masks=uncond_text_embedding_masks,
        latent_height=latent_height,
        latent_width=latent_width,
        dtype=dtype,
    )

    if isinstance(cfg_scale, list):
        assert (
            len(cfg_scale) == steps
        ), "cfg_scale (list) must have the same length as the number of steps"

    conditioning_data = TextConditioningData(
        uncond_text=uncond_text_embedding,
        cond_text=cond_text_embedding,
        uncond_regions=uncond_regions,
        cond_regions=cond_regions,
        guidance_scale=cfg_scale,
        guidance_rescale_multiplier=cfg_rescale_multiplier,
    )
    return conditioning_data


def get_scheduler(
    scheduler_info: LoadedModel,
    scheduler_name: str,
    seed: int,
    unet_config: AnyModelConfig,
) -> Scheduler:
    """Load a scheduler and apply some scheduler-specific overrides."""
    # TODO(ryand): Silently falling back to ddim seems like a bad idea. Look into why this was added and remove if
    # possible.
    scheduler_class, scheduler_extra_config = SCHEDULER_MAP.get(
        scheduler_name, SCHEDULER_MAP["ddim"]
    )
    orig_scheduler_info = scheduler_info

    with orig_scheduler_info as orig_scheduler:
        scheduler_config = orig_scheduler.config

    if "_backup" in scheduler_config:
        scheduler_config = scheduler_config["_backup"]
    scheduler_config = {
        **scheduler_config,
        **scheduler_extra_config,  # FIXME
        "_backup": scheduler_config,
    }

    if hasattr(unet_config, "prediction_type"):
        scheduler_config["prediction_type"] = unet_config.prediction_type

    # make dpmpp_sde reproducable(seed can be passed only in initializer)
    if scheduler_class is DPMSolverSDEScheduler:
        scheduler_config["noise_sampler_seed"] = seed

    if (
        scheduler_class is DPMSolverMultistepScheduler
        or scheduler_class is DPMSolverSinglestepScheduler
    ):
        if (
            scheduler_config["_class_name"] == "DEISMultistepScheduler"
            and scheduler_config["algorithm_type"] == "deis"
        ):
            scheduler_config["algorithm_type"] = "dpmsolver++"

    scheduler = scheduler_class.from_config(scheduler_config)

    # hack copied over from generate.py
    if not hasattr(scheduler, "uses_inpainting_model"):
        scheduler.uses_inpainting_model = lambda: False
    assert isinstance(scheduler, Scheduler)
    return scheduler


def init_scheduler(
    scheduler: Union[Scheduler, ConfigMixin],
    device: torch.device,
    steps: int,
    denoising_start: float,
    denoising_end: float,
    seed: int,
) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
    assert isinstance(scheduler, ConfigMixin)
    if scheduler.config.get("cpu_only", False):
        scheduler.set_timesteps(steps, device="cpu")
        timesteps = scheduler.timesteps.to(device=device)
    else:
        scheduler.set_timesteps(steps, device=device)
        timesteps = scheduler.timesteps

    # skip greater order timesteps
    _timesteps = timesteps[:: scheduler.order]

    # get start timestep index
    t_start_val = int(
        round(scheduler.config["num_train_timesteps"] * (1 - denoising_start))
    )
    t_start_idx = len(list(filter(lambda ts: ts >= t_start_val, _timesteps)))

    # get end timestep index
    t_end_val = int(
        round(scheduler.config["num_train_timesteps"] * (1 - denoising_end))
    )
    t_end_idx = len(list(filter(lambda ts: ts >= t_end_val, _timesteps[t_start_idx:])))

    # apply order to indexes
    t_start_idx *= scheduler.order
    t_end_idx *= scheduler.order

    init_timestep = timesteps[t_start_idx : t_start_idx + 1]
    timesteps = timesteps[t_start_idx : t_start_idx + t_end_idx]

    scheduler_step_kwargs: Dict[str, Any] = {}
    scheduler_step_signature = inspect.signature(scheduler.step)
    if "generator" in scheduler_step_signature.parameters:
        # At some point, someone decided that schedulers that accept a generator should use the original seed with
        # all bits flipped. I don't know the original rationale for this, but now we must keep it like this for
        # reproducibility.
        #
        # These Invoke-supported schedulers accept a generator as of 2024-06-04:
        #   - DDIMScheduler
        #   - DDPMScheduler
        #   - DPMSolverMultistepScheduler
        #   - EulerAncestralDiscreteScheduler
        #   - EulerDiscreteScheduler
        #   - KDPM2AncestralDiscreteScheduler
        #   - LCMScheduler
        #   - TCDScheduler
        scheduler_step_kwargs.update(
            {"generator": torch.Generator(device=device).manual_seed(seed ^ 0xFFFFFFFF)}
        )
    if isinstance(scheduler, TCDScheduler):
        scheduler_step_kwargs.update({"eta": 1.0})

    return timesteps, init_timestep, scheduler_step_kwargs

torch.no_grad()
def generate_image(positive: str, negative: str):
    model_path = Path(
        "D:\\StableDiffusion\\stable-diffusion-webui\\models\\Stable-diffusion\\anything-v3-2700c435.ckpt"
    )
    # model =load_model_from_path(model_path)
    model_config = ModelProbe.probe(Path(model_path))

    model_loader_service = ModelLoaderService()
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

    print("model loaded: ", unet, scheduler, text_encoder, tokenizer, vae)

    positive = create_conditioning(
        prompt=positive, tokenizer=tokenizer, text_encoder=text_encoder
    )
    negative = create_conditioning(
        prompt=negative, tokenizer=tokenizer, text_encoder=text_encoder
    )

    device = TorchDevice.choose_torch_device()
    dtype = TorchDevice.choose_torch_dtype()

    print("conditioning created: ", positive, negative)
    seed = 123454321
    noise = get_noise(
        width=512, height=512, device=device, seed=seed
    )
    latents = torch.zeros_like(noise)
    print("noise created: ", noise)
    _, _, latent_height, latent_width = latents.shape

    conditioning_data = get_conditioning_data(
        positive,
        negative,
        latent_height,
        latent_width,
        device=device,
        dtype=dtype,
        cfg_scale=7.5,
        steps=30,
        cfg_rescale_multiplier=0,
    )
    print("conditioning data created: ", conditioning_data)

    scheduler = get_scheduler(
        scheduler_info=scheduler,
        scheduler_name="ddim",
        seed=seed,
        unet_config=model_config,
    )

    timesteps, init_timestep, scheduler_step_kwargs = init_scheduler(
        scheduler,
        seed=seed,
        device=device,
        steps=30,
        denoising_start=0,
        denoising_end=1,
    )

    ext_manager = ExtensionsManager()

    # Initialize context for modular denoise
    latents = latents.to(device=device, dtype=dtype)
    noise = noise.to(device=device, dtype=dtype)

    denoise_ctx = DenoiseContext(
        inputs=DenoiseInputs(
            orig_latents=latents,
            timesteps=timesteps,
            init_timestep=init_timestep,
            noise=noise,
            seed=seed,
            scheduler_step_kwargs=scheduler_step_kwargs,
            conditioning_data=conditioning_data,
            attention_processor_cls=CustomAttnProcessor2_0,
        ),
        unet=None,
        scheduler=scheduler,
    )

    with ExitStack() as exit_stack:
        ext_manager.run_callback(ExtensionCallbackType.SETUP, denoise_ctx)
        
        with (
            unet.model_on_device() as (cached_weights, unet),
            ModelPatcher.patch_unet_attention_processor(unet, denoise_ctx.inputs.attention_processor_cls),
            ext_manager.patch_extensions(denoise_ctx),
            ext_manager.patch_unet(unet, cached_weights),
        ):
            sd_backend = StableDiffusionBackend(unet, scheduler)
            denoise_ctx.unet = unet
            result_latents = sd_backend.latents_from_embeddings(denoise_ctx, ext_manager)

        # https://discuss.huggingface.co/t/memory-usage-by-later-pipeline-stages/23699
        result_latents = result_latents.detach().to("cpu")
        TorchDevice.empty_cache()

    print("result_latents: ", result_latents)

    assert isinstance(vae.model, (AutoencoderKL, AutoencoderTiny))

    with (
        vae.model_on_device() as (_, vae),
    ):
        result_latents = result_latents.to(device=device)
        vae.to(dtype=torch.float16)
        result_latents = result_latents.half()
        vae.disable_tiling()
        TorchDevice.empty_cache()

        with torch.inference_mode():
            # copied from diffusers pipeline
            result_latents = result_latents / vae.config.scaling_factor
            image = vae.decode(result_latents, return_dict=False)[0]
            image = (image / 2 + 0.5).clamp(0, 1)  # denormalize
            # we always cast to float32 as this does not cause significant overhead and is compatible with bfloat16
            np_image = image.cpu().permute(0, 2, 3, 1).float().numpy()

            image = VaeImageProcessor.numpy_to_pil(np_image)[0]
            image.save("result.png")


class TestBackend(unittest.TestCase):
    def test_backend(self):
        generate_image("a beautiful girl, masterpiece, best quality", "a bad image")
