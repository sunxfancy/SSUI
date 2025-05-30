import PIL
from einops import rearrange
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.flux.controlnet.instantx_controlnet_flux import InstantXControlNetFlux
from backend.flux.controlnet.xlabs_controlnet_flux import XLabsControlNetFlux
from backend.flux.denoise import denoise as flux_denoise
from backend.flux.extensions.inpaint_extension import InpaintExtension
from backend.flux.extensions.instantx_controlnet_extension import InstantXControlNetExtension
from backend.flux.extensions.regional_prompting_extension import (
    RegionalPromptingExtension,
)
from backend.flux.extensions.xlabs_controlnet_extension import XLabsControlNetExtension
from backend.flux.extensions.xlabs_ip_adapter_extension import XLabsIPAdapterExtension
from backend.flux.ip_adapter.xlabs_ip_adapter_flux import XlabsIpAdapterFlux
from backend.flux.model import Flux
from backend.flux.modules.autoencoder import AutoEncoder
from backend.flux.text_conditioning import FluxTextConditioning
from backend.model_manager.config import BaseModelType, ModelFormat, ModelVariantType
from backend.model_patcher import ModelPatcher
from backend.patches.layer_patcher import LayerPatcher
from backend.patches.lora_conversions.flux_lora_constants import FLUX_LORA_TRANSFORMER_PREFIX
from backend.patches.model_patch_raw import ModelPatchRaw
from backend.stable_diffusion.denoise_context import DenoiseContext, DenoiseInputs
from backend.stable_diffusion.diffusion.conditioning_data import (
    BasicConditioningInfo,
    FLUXConditioningInfo,
)
from backend.stable_diffusion.diffusion_backend import StableDiffusionBackend
from backend.stable_diffusion.extension_callback_type import ExtensionCallbackType
from backend.stable_diffusion.extensions.controlnet import ControlNetExt
from backend.stable_diffusion.extensions.freeu import FreeUExt
from backend.stable_diffusion.extensions.inpaint import InpaintExt
from backend.stable_diffusion.extensions.inpaint_model import InpaintModelExt
from backend.stable_diffusion.extensions.lora import LoRAExt
from backend.stable_diffusion.extensions.rescale_cfg import RescaleCFGExt
from backend.stable_diffusion.extensions.seamless import SeamlessExt
from backend.stable_diffusion.extensions.t2i_adapter import T2IAdapterExt
from backend.stable_diffusion.extensions_manager import ExtensionsManager
from backend.stable_diffusion.util.controlnet_utils import CONTROLNET_RESIZE_VALUES, CONTROLNET_MODE_VALUES
from backend.util.devices import TorchDevice
import inspect
from contextlib import ExitStack
from torchvision.transforms.functional import resize as tv_resize
import torchvision.transforms as tv_transforms
from transformers import CLIPImageProcessor, CLIPVisionModelWithProjection

from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
import torch


from backend.model_manager import AnyModelConfig
from backend.model_manager.load import (
    LoadedModel,
)

from backend.util.devices import TorchDevice

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
from backend.stable_diffusion.diffusion.custom_atttention import CustomAttnProcessor2_0

from diffusers.models.autoencoders.autoencoder_kl import AutoencoderKL
from diffusers.models.autoencoders.autoencoder_tiny import AutoencoderTiny

from diffusers.image_processor import VaeImageProcessor

from .conditioning import _load_text_conditioning, get_conditioning_data
from .model import ControlLoRAModel, FluxModel, LoRAModel, UNetModel, VAEModel
from backend.flux.sampling_utils import (
    clip_timestep_schedule_fractional,
    generate_img_ids,
    get_noise as get_noise_flux,
    get_schedule,
    pack,
    unpack,
)


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



class Latents(BaseModel):
    tensor: torch.Tensor = Field(description="The latents to be denoised", validate=False)
    model_config = ConfigDict(arbitrary_types_allowed=True)

class DenoiseMask(BaseModel):
    mask_image: torch.Tensor = Field(description="The mask image to be used for inpainting", validate=False)
    masked_latents: Optional[Latents] = Field(default=None, description="The latents to be used for inpainting")
    gradient: bool = Field(default=False, description="Whether the mask is a gradient mask")
    model_config = ConfigDict(arbitrary_types_allowed=True)

class ApplyRange(BaseModel):
    begin_step_percent: float = Field(
        default=0, ge=0, le=1, description="When the ControlNet is first applied (% of total steps)"
    )
    end_step_percent: float = Field(
        default=1, ge=0, le=1, description="When the ControlNet is last applied (% of total steps)"
    )

    @model_validator(mode="after")
    def validate_begin_end_step_percent(self):
        if self.begin_step_percent >= self.end_step_percent:
            raise ValueError("Begin step percent must be less than or equal to end step percent")
        return self

class ControlNet(BaseModel):
    image: PIL.Image.Image = Field(description="The control image", validate=False)
    control_model: LoadedModel = Field(description="The ControlNet model to use", validate=False)
    control_weight: Union[float, List[float]] = Field(default=1, description="The weight given to the ControlNet")
    apply_range: ApplyRange = Field(default=ApplyRange(), description="The range of steps to apply the ControlNet")
    control_mode: CONTROLNET_MODE_VALUES = Field(default="balanced", description="The control mode to use")
    resize_mode: CONTROLNET_RESIZE_VALUES = Field(default="just_resize", description="The resize mode to use")
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("control_weight")
    @classmethod
    def validate_control_weight(cls, weights):
        to_validate = weights if isinstance(weights, list) else [weights]
        if any(i < -1 or i > 2 for i in to_validate):
            raise ValueError("Control weights must be within -1 to 2 range")
        return weights

class FluxControlNet(BaseModel):
    image: PIL.Image.Image = Field(description="The control image", validate=False)
    control_model: LoadedModel = Field(description="The ControlNet model to use", validate=False)
    control_weight: float | list[float] = Field(default=1, description="The weight given to the ControlNet")
    apply_range: ApplyRange = Field(default=ApplyRange(), description="The range of steps to apply the ControlNet")
    resize_mode: CONTROLNET_RESIZE_VALUES = Field(default="just_resize", description="The resize mode to use")
    instantx_control_mode: int | None = Field(default=-1, description="The control mode for InstantX ControlNet union models. Ignored for other ControlNet models. The standard mapping is: canny (0), tile (1), depth (2), blur (3), pose (4), gray (5), low quality (6). Negative values will be treated as 'None'.")
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("control_weight")
    @classmethod
    def validate_control_weight(cls, weights):
        to_validate = weights if isinstance(weights, list) else [weights]
        if any(i < -1 or i > 2 for i in to_validate):
            raise ValueError("Control weights must be within -1 to 2 range")
        return weights


class IPAdapter(BaseModel):
    image: Union['PIL.Image.Image', List['PIL.Image.Image']] = Field(description="The IP-Adapter image prompt(s).", validate=False)
    ip_adapter_model: 'LoadedModel' = Field(description="The IP-Adapter model to use", validate=False)
    image_encoder_model: 'LoadedModel' = Field(description="The name of the CLIP image encoder model", validate=False)
    weight: Union[float, List[float]] = Field(default=1, description="The weight given to the IP-Adapter.")
    target_blocks: List[str] = Field(default=[], description="The IP Adapter blocks to apply")
    apply_range: ApplyRange = Field(description="The range of steps to apply the IP-Adapter")
    mask: Optional[torch.Tensor] = Field(
        default=None,
        description="The bool mask associated with this IP-Adapter. Excluded regions should be set to False, included "
        "regions should be set to True.",
    )

    @field_validator("weight")
    @classmethod
    def validate_ip_adapter_weight(cls, weights: float) -> float:
        to_validate = weights if isinstance(weights, list) else [weights]
        if any(i < -1 or i > 2 for i in to_validate):
            raise ValueError("Control weights must be within -1 to 2 range")
        return weights
    model_config = ConfigDict(arbitrary_types_allowed=True)



class T2IAdapter(BaseModel):
    image: 'PIL.Image.Image' = Field(description="The T2I-Adapter image prompt", validate=False)
    t2i_adapter_model: 'LoadedModel' = Field(description="The T2I-Adapter model to use", validate=False)
    weight: Union[float, list[float]] = Field(default=1, description="The weight given to the T2I-Adapter")
    apply_range: ApplyRange = Field(description="The range of steps to apply the IP-Adapter")
    resize_mode: CONTROLNET_RESIZE_VALUES = Field(default="just_resize", description="The resize mode to use")
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("weight")
    @classmethod
    def validate_t2i_adapter_weight(cls, weights: float) -> float:
        to_validate = weights if isinstance(weights, list) else [weights]
        if any(i < -1 or i > 2 for i in to_validate):
            raise ValueError("Control weights must be within -1 to 2 range")
        return weights


@torch.no_grad()
def denoise_image(
    model: UNetModel,
    positive: BasicConditioningInfo,
    negative: BasicConditioningInfo,
    seed: int = 123454321,
    width: int = 1024,
    height: int = 1024,
    scheduler_name: str = "ddim",
    cfg_scale: float = 7.5,
    cfg_rescale_multiplier: float = 1.0,
    steps: int = 20,
    latents: Optional[Latents] = None,
    denoise_mask: Optional[DenoiseMask] = None,
    control: Optional[ControlNet] = None,
    ip_adapter: Optional[IPAdapter] = None,
    t2i_adapter: Optional[T2IAdapter] = None,
) -> Latents:
    
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
        t_end_idx = len(
            list(filter(lambda ts: ts >= t_end_val, _timesteps[t_start_idx:]))
        )

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
                {
                    "generator": torch.Generator(device=device).manual_seed(
                        seed ^ 0xFFFFFFFF
                    )
                }
            )
        if isinstance(scheduler, TCDScheduler):
            scheduler_step_kwargs.update({"eta": 1.0})

        return timesteps, init_timestep, scheduler_step_kwargs

    def prep_inpaint_mask(
        denoise_mask: DenoiseMask, latents: torch.Tensor
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor], bool]:
        if denoise_mask is None:
            return None, None, False

        mask = denoise_mask.mask_image
        mask = tv_resize(mask, latents.shape[-2:], tv_transforms.InterpolationMode.BILINEAR, antialias=False)
        if denoise_mask.masked_latents is not None:
            masked_latents = denoise_mask.masked_latents
        else:
            masked_latents = torch.where(mask < 0.5, 0.0, latents)

        return mask, masked_latents, denoise_mask.gradient

    def parse_controlnet_field(
        exit_stack: ExitStack,
        control_input: ControlNet | list[ControlNet] | None,
        ext_manager: ExtensionsManager,
    ) -> None:
        # Normalize control_input to a list.
        control_list: list[ControlNet]
        if isinstance(control_input, ControlNet):
            control_list = [control_input]
        elif isinstance(control_input, list):
            control_list = control_input
        elif control_input is None:
            control_list = []
        else:
            raise ValueError(f"Unexpected control_input type: {type(control_input)}")

        for control_info in control_list:
            model = exit_stack.enter_context(control_info.control_model)
            ext_manager.add_extension(
                ControlNetExt(
                    model=model,
                    image=control_info.image,
                    weight=control_info.control_weight,
                    begin_step_percent=control_info.apply_range.begin_step_percent,
                    end_step_percent=control_info.apply_range.end_step_percent,
                    control_mode=control_info.control_mode,
                    resize_mode=control_info.resize_mode,
                )
            )

    def parse_t2i_adapter_field(
        exit_stack: ExitStack,
        t2i_adapters: Optional[Union[T2IAdapter, list[T2IAdapter]]],
        ext_manager: ExtensionsManager,
        bgr_mode: bool = False,
    ) -> None:
        if t2i_adapters is None:
            return

        # Handle the possibility that t2i_adapters could be a list or a single T2IAdapterField.
        if isinstance(t2i_adapters, T2IAdapter):
            t2i_adapters = [t2i_adapters]

        for t2i_adapter in t2i_adapters:
            image = t2i_adapter.image
            if bgr_mode:  # SDXL t2i trained on cv2's BGR outputs, but PIL won't convert straight to BGR
                r, g, b = image.split()
                image = PIL.Image.merge("RGB", (b, g, r))
            
            downscale = 0
            if t2i_adapter.t2i_adapter_model.config.base == BaseModelType.StableDiffusion1:
                downscale = 8
            elif t2i_adapter.t2i_adapter_model.config.base == BaseModelType.StableDiffusionXL:
                downscale = 4
            else:
                raise ValueError(f"Unexpected T2I-Adapter base model type: '{t2i_adapter.t2i_adapter_model.config.base}'.")

            ext_manager.add_extension(
                T2IAdapterExt(
                    t2i_model=t2i_adapter.t2i_adapter_model,
                    unet_downscale=downscale,
                    image=t2i_adapter.image,
                    weight=t2i_adapter.weight,
                    begin_step_percent=t2i_adapter.apply_range.begin_step_percent,
                    end_step_percent=t2i_adapter.apply_range.end_step_percent,
                    resize_mode=t2i_adapter.resize_mode,
                )
            )
    ##################################################
    # Start of the denoise process
    ##################################################

    unet = model.unet
    scheduler = model.scheduler
    device = TorchDevice.choose_torch_device()
    dtype = TorchDevice.choose_torch_dtype()
    unet_config = model.scheduler.config
    noise = get_noise(width=width, height=height, device=device, seed=seed)

    if latents is not None:
        latents = latents.tensor
    else:
        latents = torch.zeros_like(noise)

    print("conditioning created: ", positive, negative)
    
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
        cfg_scale=cfg_scale,
        steps=steps,
        cfg_rescale_multiplier=0,
    )
    print("conditioning data created: ", conditioning_data)

    scheduler = get_scheduler(
        scheduler_info=scheduler,
        scheduler_name=scheduler_name,
        seed=seed,
        unet_config=unet_config,
    )

    timesteps, init_timestep, scheduler_step_kwargs = init_scheduler(
        scheduler,
        seed=seed,
        device=device,
        steps=steps,
        denoising_start=0,
        denoising_end=1,
    )

    ext_manager = ExtensionsManager()

    ### cfg rescale
    if cfg_rescale_multiplier > 0:
        ext_manager.add_extension(RescaleCFGExt(cfg_rescale_multiplier))

    ### freeu
    if model.freeu_config:
        ext_manager.add_extension(FreeUExt(model.freeu_config))

    ### lora
    if model.loras:
        for lora_field in model.loras:
            ext_manager.add_extension(
                LoRAExt(
                    lora_model=lora_field.lora,
                    weight=lora_field.weight,
                )
            )
    ### seamless
    if model.seamless_axes:
        ext_manager.add_extension(SeamlessExt(model.seamless_axes))

    ### inpaint
    mask, masked_latents, is_gradient_mask = prep_inpaint_mask(denoise_mask, latents)
    # NOTE: We used to identify inpainting models by inspecting the shape of the loaded UNet model weights. Now we
    # use the ModelVariantType config. During testing, there was a report of a user with models that had an
    # incorrect ModelVariantType value. Re-installing the model fixed the issue. If this issue turns out to be
    # prevalent, we will have to revisit how we initialize the inpainting extensions.
    if unet_config.variant == ModelVariantType.Inpaint:
        ext_manager.add_extension(InpaintModelExt(mask, masked_latents, is_gradient_mask))
    elif mask is not None:
        ext_manager.add_extension(InpaintExt(mask, is_gradient_mask))

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
        # later should be smth like:
        # for extension_field in self.extensions:
        #    ext = extension_field.to_extension(exit_stack, context, ext_manager)
        #    ext_manager.add_extension(ext)
        parse_controlnet_field(exit_stack, control, ext_manager)
        bgr_mode = unet.config.base == BaseModelType.StableDiffusionXL
        parse_t2i_adapter_field(exit_stack, t2i_adapter, ext_manager, bgr_mode)

        ext_manager.run_callback(ExtensionCallbackType.SETUP, denoise_ctx)

        with (
            unet.model_on_device() as (cached_weights, unet),
            ModelPatcher.patch_unet_attention_processor(
                unet, denoise_ctx.inputs.attention_processor_cls
            ),
            # ext: controlnet
            ext_manager.patch_extensions(denoise_ctx),
            # ext: freeu, seamless, ip adapter, lora
            ext_manager.patch_unet(unet, cached_weights),
        ):
            sd_backend = StableDiffusionBackend(unet, scheduler)
            denoise_ctx.unet = unet
            result_latents = sd_backend.latents_from_embeddings(
                denoise_ctx, ext_manager
            )

        # https://discuss.huggingface.co/t/memory-usage-by-later-pipeline-stages/23699
        result_latents = result_latents.detach().to("cpu")
        TorchDevice.empty_cache()

    print("result_latents: ", result_latents)
    return Latents(tensor=result_latents)

@torch.no_grad()
def decode_latents(model: VAEModel, result_latents: Latents) -> PIL.Image.Image | None:
    vae = model.vae
    assert isinstance(vae.model, (AutoencoderKL, AutoencoderTiny))
    with (vae.model_on_device() as (_, vae),):
        result_latents = result_latents.tensor.to(
            device=TorchDevice.choose_torch_device()
        )
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
            return image


class FLuxLatents(BaseModel):
    tensor: torch.Tensor = Field(description="The latents to be denoised", validate=False)
    model_config = ConfigDict(arbitrary_types_allowed=True)

@torch.no_grad()
def flux_denoise_image(
    model: FluxModel,
    positive: FLUXConditioningInfo | list[FLUXConditioningInfo],
    negative: FLUXConditioningInfo | list[FLUXConditioningInfo] | None = None,
    init_latents: FLuxLatents | None = None,
    denoise_mask: torch.Tensor | None = None,
    control: FluxControlNet | list[FluxControlNet] | None = None,
    controlnet_vae: VAEModel | None = None,
    ip_adapter: IPAdapter | list[IPAdapter] | None = None,
    control_lora: Optional[ControlLoRAModel] = None,
    seed: int = 123454321,
    width: int = 1024,
    height: int = 1024,
    cfg_scale: float = 1.0,
    cfg_scale_start_step: int = 0,
    cfg_scale_end_step: int = -1,
    steps: int = 4,
    guidance: float = 4.0,
    add_noise: bool = True,
    denoising_start: float = 0.0,
    denoising_end: float = 1.0,
) -> FLuxLatents:

    def _prep_inpaint_mask(latents: torch.Tensor) -> torch.Tensor | None:
        """Prepare the inpaint mask.

        - Loads the mask
        - Resizes if necessary
        - Casts to same device/dtype as latents
        - Expands mask to the same shape as latents so that they line up after 'packing'

        Args:
            context (InvocationContext): The invocation context, for loading the inpaint mask.
            latents (torch.Tensor): A latent image tensor. In 'unpacked' format. Used to determine the target shape,
                device, and dtype for the inpaint mask.

        Returns:
            torch.Tensor | None: Inpaint mask. Values of 0.0 represent the regions to be fully denoised, and 1.0
                represent the regions to be preserved.
        """
        if denoise_mask is None:
            return None

        mask = denoise_mask

        # The input denoise_mask contains values in [0, 1], where 0.0 represents the regions to be fully denoised, and
        # 1.0 represents the regions to be preserved.
        # We invert the mask so that the regions to be preserved are 0.0 and the regions to be denoised are 1.0.
        mask = 1.0 - mask

        _, _, latent_height, latent_width = latents.shape
        mask = tv_resize(
            img=mask,
            size=[latent_height, latent_width],
            interpolation=tv_transforms.InterpolationMode.BILINEAR,
            antialias=False,
        )

        mask = mask.to(device=latents.device, dtype=latents.dtype)

        # Expand the inpaint mask to the same shape as `latents` so that when we 'pack' `mask` it lines up with
        # `latents`.
        return mask.expand_as(latents)

    def prep_cfg_scale(
        cfg_scale: float | list[float],
        timesteps: list[float],
        cfg_scale_start_step: int,
        cfg_scale_end_step: int,
    ) -> list[float]:
        """Prepare the cfg_scale schedule.

        - Clips the cfg_scale schedule based on cfg_scale_start_step and cfg_scale_end_step.
        - If cfg_scale is a list, then it is assumed to be a schedule and is returned as-is.
        - If cfg_scale is a scalar, then a linear schedule is created from cfg_scale_start_step to cfg_scale_end_step.
        """
        # num_steps is the number of denoising steps, which is one less than the number of timesteps.
        num_steps = len(timesteps) - 1

        # Normalize cfg_scale to a list if it is a scalar.
        cfg_scale_list: list[float]
        if isinstance(cfg_scale, float):
            cfg_scale_list = [cfg_scale] * num_steps
        elif isinstance(cfg_scale, list):
            cfg_scale_list = cfg_scale
        else:
            raise ValueError(f"Unsupported cfg_scale type: {type(cfg_scale)}")
        assert len(cfg_scale_list) == num_steps

        # Handle negative indices for cfg_scale_start_step and cfg_scale_end_step.
        start_step_index = cfg_scale_start_step
        if start_step_index < 0:
            start_step_index = num_steps + start_step_index
        end_step_index = cfg_scale_end_step
        if end_step_index < 0:
            end_step_index = num_steps + end_step_index

        # Validate the start and end step indices.
        if not (0 <= start_step_index < num_steps):
            raise ValueError(
                f"Invalid cfg_scale_start_step. Out of range: {cfg_scale_start_step}."
            )
        if not (0 <= end_step_index < num_steps):
            raise ValueError(
                f"Invalid cfg_scale_end_step. Out of range: {cfg_scale_end_step}."
            )
        if start_step_index > end_step_index:
            raise ValueError(
                f"cfg_scale_start_step ({cfg_scale_start_step}) must be before cfg_scale_end_step "
                + f"({cfg_scale_end_step})."
            )

        # Set values outside the start and end step indices to 1.0. This is equivalent to disabling cfg_scale for those
        # steps.
        clipped_cfg_scale = [1.0] * num_steps
        clipped_cfg_scale[start_step_index : end_step_index + 1] = cfg_scale_list[
            start_step_index : end_step_index + 1
        ]

        return clipped_cfg_scale
    
    def _prep_controlnet_extensions(
        control: Optional[FluxControlNet | list[FluxControlNet]],
        controlnet_vae: Optional[VAEModel],
        latent_height: int,
        latent_width: int,
        dtype: torch.dtype,
        device: torch.device,
    ) -> list[XLabsControlNetExtension | InstantXControlNetExtension]:
        # Normalize the controlnet input to list[ControlField].
        controlnets: list[FluxControlNet]
        if control is None:
            controlnets = []
        elif isinstance(control, FluxControlNet):
            controlnets = [control]
        elif isinstance(control, list):
            controlnets = control

        # TODO(ryand): Add a field to the model config so that we can distinguish between XLabs and InstantX ControlNets
        # before loading the models. Then make sure that all VAE encoding is done before loading the ControlNets to
        # minimize peak memory.

        # Calculate the controlnet conditioning tensors.
        # We do this before loading the ControlNet models because it may require running the VAE, and we are trying to
        # keep peak memory down.
        controlnet_conds: list[torch.Tensor] = []
        for controlnet in controlnets:
            image = controlnet.image

            # HACK(ryand): We have to load the ControlNet model to determine whether the VAE needs to be run. We really
            # shouldn't have to load the model here. There's a risk that the model will be dropped from the model cache
            # before we load it into VRAM and thus we'll have to load it again (context:
            # https://github.com/invoke-ai/InvokeAI/issues/7513).
            controlnet_model = controlnet.control_model
            if isinstance(controlnet_model.model, InstantXControlNetFlux):
                if controlnet_vae is None:
                    raise ValueError("A ControlNet VAE is required when using an InstantX FLUX ControlNet.")
                vae_info = controlnet_vae.vae
                controlnet_conds.append(
                    InstantXControlNetExtension.prepare_controlnet_cond(
                        controlnet_image=image,
                        vae_info=vae_info,
                        latent_height=latent_height,
                        latent_width=latent_width,
                        dtype=dtype,
                        device=device,
                        resize_mode=controlnet.resize_mode,
                    )
                )
            elif isinstance(controlnet_model.model, XLabsControlNetFlux):
                controlnet_conds.append(
                    XLabsControlNetExtension.prepare_controlnet_cond(
                        controlnet_image=image,
                        latent_height=latent_height,
                        latent_width=latent_width,
                        dtype=dtype,
                        device=device,
                        resize_mode=controlnet.resize_mode,
                    )
                )

        # Finally, load the ControlNet models and initialize the ControlNet extensions.
        controlnet_extensions: list[XLabsControlNetExtension | InstantXControlNetExtension] = []
        for controlnet, controlnet_cond in zip(controlnets, controlnet_conds, strict=True):
            model = controlnet.control_model.model

            if isinstance(model, XLabsControlNetFlux):
                controlnet_extensions.append(
                    XLabsControlNetExtension(
                        model=model,
                        controlnet_cond=controlnet_cond,
                        weight=controlnet.control_weight,
                        begin_step_percent=controlnet.begin_step_percent,
                        end_step_percent=controlnet.end_step_percent,
                    )
                )
            elif isinstance(model, InstantXControlNetFlux):
                instantx_control_mode: torch.Tensor | None = None
                if controlnet.instantx_control_mode is not None and controlnet.instantx_control_mode >= 0:
                    instantx_control_mode = torch.tensor(controlnet.instantx_control_mode, dtype=torch.long)
                    instantx_control_mode = instantx_control_mode.reshape([-1, 1])

                controlnet_extensions.append(
                    InstantXControlNetExtension(
                        model=model,
                        controlnet_cond=controlnet_cond,
                        instantx_control_mode=instantx_control_mode,
                        weight=controlnet.control_weight,
                        begin_step_percent=controlnet.begin_step_percent,
                        end_step_percent=controlnet.end_step_percent,
                    )
                )
            else:
                raise ValueError(f"Unsupported ControlNet model type: {type(model)}")

        return controlnet_extensions
    
    def _prep_ip_adapter_extensions(
        ip_adapter_fields: list[IPAdapter],
        pos_image_prompt_clip_embeds: list[torch.Tensor],
        neg_image_prompt_clip_embeds: list[torch.Tensor],
        exit_stack: ExitStack,
        dtype: torch.dtype,
    ) -> tuple[list[XLabsIPAdapterExtension], list[XLabsIPAdapterExtension]]:
        pos_ip_adapter_extensions: list[XLabsIPAdapterExtension] = []
        neg_ip_adapter_extensions: list[XLabsIPAdapterExtension] = []
        for ip_adapter_field, pos_image_prompt_clip_embed, neg_image_prompt_clip_embed in zip(
            ip_adapter_fields, pos_image_prompt_clip_embeds, neg_image_prompt_clip_embeds, strict=True
        ):
            ip_adapter_model = ip_adapter_field.ip_adapter_model.model
            assert isinstance(ip_adapter_model, XlabsIpAdapterFlux)
            ip_adapter_model = ip_adapter_model.to(dtype=dtype)
            if ip_adapter_field.mask is not None:
                raise ValueError("IP-Adapter masks are not yet supported in Flux.")
            ip_adapter_extension = XLabsIPAdapterExtension(
                model=ip_adapter_model,
                image_prompt_clip_embed=pos_image_prompt_clip_embed,
                weight=ip_adapter_field.weight,
                begin_step_percent=ip_adapter_field.begin_step_percent,
                end_step_percent=ip_adapter_field.end_step_percent,
            )
            ip_adapter_extension.run_image_proj(dtype=dtype)
            pos_ip_adapter_extensions.append(ip_adapter_extension)

            ip_adapter_extension = XLabsIPAdapterExtension(
                model=ip_adapter_model,
                image_prompt_clip_embed=neg_image_prompt_clip_embed,
                weight=ip_adapter_field.weight,
                begin_step_percent=ip_adapter_field.begin_step_percent,
                end_step_percent=ip_adapter_field.end_step_percent,
            )
            ip_adapter_extension.run_image_proj(dtype=dtype)
            neg_ip_adapter_extensions.append(ip_adapter_extension)

        return pos_ip_adapter_extensions, neg_ip_adapter_extensions

    def _lora_iterator(model: FluxModel, control_lora: Optional[Union[ControlLoRAModel, list[ControlLoRAModel]]]) -> Iterator[Tuple[ModelPatchRaw, float]]:
        loras: list[Union[LoRAModel, ControlLoRAModel]] = [*model.loras]
        if control_lora:
            # Note: Since FLUX structural control LoRAs modify the shape of some weights, it is important that they are
            # applied last.
            loras.append(control_lora)
        for lora in loras:
            lora_info = lora.lora.lora
            assert isinstance(lora_info.model, ModelPatchRaw)
            yield (lora_info.model, lora.weight)
            del lora_info

    def _normalize_ip_adapter_fields() -> list[IPAdapter]:
        if ip_adapter is None:
            return []
        elif isinstance(ip_adapter, IPAdapter):
            return [ip_adapter]
        elif isinstance(ip_adapter, list):
            return ip_adapter
        
    def _prep_ip_adapter_image_prompt_clip_embeds(
        ip_adapter_fields: list[IPAdapter],
        device: torch.device,
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """Run the IPAdapter CLIPVisionModel, returning image prompt embeddings."""
        clip_image_processor = CLIPImageProcessor()

        pos_image_prompt_clip_embeds: list[torch.Tensor] = []
        neg_image_prompt_clip_embeds: list[torch.Tensor] = []
        for ip_adapter_field in ip_adapter_fields:
            # `ip_adapter_field.image` could be a list or a single ImageField. Normalize to a list here.
            ipa_image_fields: list[PIL.Image.Image]
            if isinstance(ip_adapter_field.image, PIL.Image.Image):
                ipa_image_fields = [ip_adapter_field.image]
            elif isinstance(ip_adapter_field.image, list):
                ipa_image_fields = ip_adapter_field.image
            else:
                raise ValueError(f"Unsupported IP-Adapter image type: {type(ip_adapter_field.image)}")

            if len(ipa_image_fields) != 1:
                raise ValueError(
                    f"FLUX IP-Adapter only supports a single image prompt (received {len(ipa_image_fields)})."
                )

            ipa_images = [*ipa_image_fields]

            pos_images: list[npt.NDArray[np.uint8]] = []
            neg_images: list[npt.NDArray[np.uint8]] = []
            for ipa_image in ipa_images:
                assert ipa_image.mode == "RGB"
                pos_image = np.array(ipa_image)
                # We use a black image as the negative image prompt for parity with
                # https://github.com/XLabs-AI/x-flux-comfyui/blob/45c834727dd2141aebc505ae4b01f193a8414e38/nodes.py#L592-L593
                # An alternative scheme would be to apply zeros_like() after calling the clip_image_processor.
                neg_image = np.zeros_like(pos_image)
                pos_images.append(pos_image)
                neg_images.append(neg_image)

            with ip_adapter_field.image_encoder_model as image_encoder_model:
                assert isinstance(image_encoder_model, CLIPVisionModelWithProjection)

                clip_image: torch.Tensor = clip_image_processor(images=pos_images, return_tensors="pt").pixel_values
                clip_image = clip_image.to(device=device, dtype=image_encoder_model.dtype)
                pos_clip_image_embeds = image_encoder_model(clip_image).image_embeds

                clip_image = clip_image_processor(images=neg_images, return_tensors="pt").pixel_values
                clip_image = clip_image.to(device=device, dtype=image_encoder_model.dtype)
                neg_clip_image_embeds = image_encoder_model(clip_image).image_embeds

            pos_image_prompt_clip_embeds.append(pos_clip_image_embeds)
            neg_image_prompt_clip_embeds.append(neg_clip_image_embeds)

        return pos_image_prompt_clip_embeds, neg_image_prompt_clip_embeds
        
    ################################################################################
    # Start of the main function
    ################################################################################

    inference_dtype = torch.bfloat16

    # Load the input latents, if provided.
    if init_latents is not None:
        init_latents = init_latents.tensor.to(
            device=TorchDevice.choose_torch_device(), dtype=inference_dtype
        )

    # Prepare input noise.
    noise = get_noise_flux(
        num_samples=1,
        height=height,
        width=width,
        device=TorchDevice.choose_torch_device(),
        dtype=inference_dtype,
        seed=seed,
    )
    b, _c, latent_h, latent_w = noise.shape
    packed_h = latent_h // 2
    packed_w = latent_w // 2

    # Convert positive and negative to lists.
    if isinstance(positive, FLUXConditioningInfo):
        positive = [positive]
    if isinstance(negative, FLUXConditioningInfo):
        negative = [negative]

    # Load the conditioning data.
    pos_text_conditionings = _load_text_conditioning(
        cond_list=positive,
        masks=None,
        packed_height=packed_h,
        packed_width=packed_w,
        dtype=inference_dtype,
        device=TorchDevice.choose_torch_device(),
    )
    neg_text_conditionings: list[FluxTextConditioning] | None = None
    if negative is not None:
        neg_text_conditionings = _load_text_conditioning(
            cond_list=negative,
            masks=None,
            packed_height=packed_h,
            packed_width=packed_w,
            dtype=inference_dtype,
            device=TorchDevice.choose_torch_device(),
        )
    pos_regional_prompting_extension = (
        RegionalPromptingExtension.from_text_conditioning(
            pos_text_conditionings, img_seq_len=packed_h * packed_w
        )
    )
    neg_regional_prompting_extension = (
        RegionalPromptingExtension.from_text_conditioning(
            neg_text_conditionings, img_seq_len=packed_h * packed_w
        )
        if neg_text_conditionings
        else None
    )

    transformer_config = model.transformer.config
    is_schnell = "schnell" in getattr(transformer_config, "config_path", "")

    # Calculate the timestep schedule.
    timesteps = get_schedule(
        num_steps=steps,
        image_seq_len=packed_h * packed_w,
        shift=not is_schnell,
    )

    # Clip the timesteps schedule based on denoising_start and denoising_end.
    timesteps = clip_timestep_schedule_fractional(
        timesteps, denoising_start, denoising_end
    )

    # Prepare input latent image.
    if init_latents is not None:
        # If init_latents is provided, we are doing image-to-image.
        if add_noise:
            # Noise the orig_latents by the appropriate amount for the first timestep.
            t_0 = timesteps[0]
            x = t_0 * noise + (1.0 - t_0) * init_latents
        else:
            x = init_latents
    else:
        # init_latents are not provided, so we are not doing image-to-image (i.e. we are starting from pure noise).
        if denoising_start > 1e-5:
            raise ValueError(
                "denoising_start should be 0 when initial latents are not provided."
            )

        x = noise

    # If len(timesteps) == 1, then short-circuit. We are just noising the input latents, but not taking any
    # denoising steps.
    if len(timesteps) <= 1:
        return x

    # if is_schnell and control_lora:
    #     raise ValueError("Control LoRAs cannot be used with FLUX Schnell")

    # Prepare the extra image conditioning tensor if a FLUX structural control image is provided.
    # img_cond = _prep_structural_control_img_cond(context)
    img_cond = None

    inpaint_mask = _prep_inpaint_mask(x)

    img_ids = generate_img_ids(
        h=latent_h, w=latent_w, batch_size=b, device=x.device, dtype=x.dtype
    )

    # Pack all latent tensors.
    init_latents = pack(init_latents) if init_latents is not None else None
    inpaint_mask = pack(inpaint_mask) if inpaint_mask is not None else None
    img_cond = pack(img_cond) if img_cond is not None else None
    noise = pack(noise)
    x = pack(x)

    # Now that we have 'packed' the latent tensors, verify that we calculated the image_seq_len, packed_h, and
    # packed_w correctly.
    assert packed_h * packed_w == x.shape[1]

    # Prepare inpaint extension.
    inpaint_extension: InpaintExtension | None = None
    if inpaint_mask is not None:
        assert init_latents is not None
        inpaint_extension = InpaintExtension(
            init_latents=init_latents,
            inpaint_mask=inpaint_mask,
            noise=noise,
        )

    # Compute the IP-Adapter image prompt clip embeddings.
    # We do this before loading other models to minimize peak memory.
    ip_adapter_fields = _normalize_ip_adapter_fields()
    pos_image_prompt_clip_embeds, neg_image_prompt_clip_embeds = _prep_ip_adapter_image_prompt_clip_embeds(
        ip_adapter_fields, device=x.device
    )

    cfg_scale = prep_cfg_scale(
        cfg_scale=cfg_scale,
        timesteps=timesteps,
        cfg_scale_start_step=cfg_scale_start_step,
        cfg_scale_end_step=cfg_scale_end_step,
    )

    with ExitStack() as exit_stack:
        # Prepare ControlNet extensions.
        # Note: We do this before loading the transformer model to minimize peak memory (see implementation).
        controlnet_extensions = _prep_controlnet_extensions(
            control=control,
            controlnet_vae=controlnet_vae,
            latent_height=latent_h,
            latent_width=latent_w,
            dtype=inference_dtype,
            device=x.device,
        )

        # Load the transformer model.
        (cached_weights, transformer) = exit_stack.enter_context(
            model.transformer.model_on_device()
        )
        assert isinstance(transformer, Flux)
        config = transformer_config
        assert config is not None

        # Determine if the model is quantized.
        # If the model is quantized, then we need to apply the LoRA weights as sidecar layers. This results in
        # slower inference than direct patching, but is agnostic to the quantization format.
        if config.format in [ModelFormat.Checkpoint]:
            model_is_quantized = False
        elif config.format in [
            ModelFormat.BnbQuantizedLlmInt8b,
            ModelFormat.BnbQuantizednf4b,
            ModelFormat.GGUFQuantized,
        ]:
            model_is_quantized = True
        else:
            raise ValueError(f"Unsupported model format: {config.format}")

        # Apply LoRA models to the transformer.
        # Note: We apply the LoRA after the transformer has been moved to its target device for faster patching.
        exit_stack.enter_context(
            LayerPatcher.apply_smart_model_patches(
                model=transformer,
                patches=_lora_iterator(model, control_lora),
                prefix=FLUX_LORA_TRANSFORMER_PREFIX,
                dtype=inference_dtype,
                cached_weights=cached_weights,
                force_sidecar_patching=model_is_quantized,
            )
        )

        # Prepare IP-Adapter extensions.
        pos_ip_adapter_extensions, neg_ip_adapter_extensions = (
            _prep_ip_adapter_extensions(
                ip_adapter_fields=ip_adapter_fields,
                pos_image_prompt_clip_embeds=pos_image_prompt_clip_embeds,
                neg_image_prompt_clip_embeds=neg_image_prompt_clip_embeds,
                exit_stack=exit_stack,
                dtype=inference_dtype,
            )
        )

        x = flux_denoise(
            model=transformer,
            img=x,
            img_ids=img_ids,
            pos_regional_prompting_extension=pos_regional_prompting_extension,
            neg_regional_prompting_extension=neg_regional_prompting_extension,
            timesteps=timesteps,
            guidance=guidance,
            cfg_scale=cfg_scale,
            inpaint_extension=inpaint_extension,
            img_cond=img_cond,
            controlnet_extensions=controlnet_extensions,
            pos_ip_adapter_extensions=pos_ip_adapter_extensions,
            neg_ip_adapter_extensions=neg_ip_adapter_extensions,
            step_callback=None,
        )

    result_latents = unpack(x.float(), height, width)
    result_latents = result_latents.detach().to("cpu")
    return FLuxLatents(tensor=result_latents)


@torch.no_grad()
def flux_decode_latents(
    vae: VAEModel, result_latents: FLuxLatents
) -> PIL.Image.Image | None:
    def _estimate_working_memory(latents: torch.Tensor, vae: AutoEncoder) -> int:
        LATENT_SCALE_FACTOR = 8
        """Estimate the working memory required by the invocation in bytes."""
        # It was found experimentally that the peak working memory scales linearly with the number of pixels and the
        # element size (precision).
        out_h = LATENT_SCALE_FACTOR * latents.shape[-2]
        out_w = LATENT_SCALE_FACTOR * latents.shape[-1]
        element_size = next(vae.parameters()).element_size()
        scaling_constant = 1090  # Determined experimentally.
        working_memory = out_h * out_w * element_size * scaling_constant

        # We add a 20% buffer to the working memory estimate to be safe.
        working_memory = working_memory * 1.2
        return int(working_memory)

    latents = result_latents.tensor
    estimated_working_memory = _estimate_working_memory(result_latents.tensor, vae.vae.model)
    with vae.vae.model_on_device(working_mem_bytes=estimated_working_memory) as (
        _,
        vae,
    ):
        assert isinstance(vae, AutoEncoder)
        vae_dtype = next(iter(vae.parameters())).dtype
        latents = latents.to(device=TorchDevice.choose_torch_device(), dtype=vae_dtype)
        img = vae.decode(latents)

    img = img.clamp(-1, 1)
    img = rearrange(img[0], "c h w -> h w c")  # noqa: F821
    img_pil = PIL.Image.fromarray((127.5 * (img + 1.0)).byte().cpu().numpy())
    return img_pil
