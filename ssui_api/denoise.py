from dataclasses import dataclass
import PIL
from einops import rearrange
from backend.flux.denoise import denoise as flux_denoise
from backend.flux.extensions.inpaint_extension import InpaintExtension
from backend.flux.extensions.regional_prompting_extension import (
    RegionalPromptingExtension,
)
from backend.flux.model import Flux
from backend.flux.modules.autoencoder import AutoEncoder
from backend.flux.text_conditioning import FluxTextConditioning
from backend.model_manager.config import ModelFormat
from backend.model_patcher import ModelPatcher
from backend.stable_diffusion.denoise_context import DenoiseContext, DenoiseInputs
from backend.stable_diffusion.diffusion.conditioning_data import (
    BasicConditioningInfo,
    FLUXConditioningInfo,
)
from backend.stable_diffusion.diffusion_backend import StableDiffusionBackend
from backend.stable_diffusion.extension_callback_type import ExtensionCallbackType
from backend.stable_diffusion.extensions_manager import ExtensionsManager
from backend.util.devices import TorchDevice
import inspect
from contextlib import ExitStack
from torchvision.transforms.functional import resize as tv_resize
import torchvision.transforms as tv_transforms

from typing import Any, Dict, Tuple, Union
import torch


from backend.model_manager import AnyModel, AnyModelConfig
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
from .model import FluxModel, UNetModel, VAEModel
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


@dataclass
class Latents:
    tensor: torch.Tensor


@torch.no_grad()
def denoise_image(
    model: UNetModel,
    positive: BasicConditioningInfo,
    negative: BasicConditioningInfo,
    seed: int,
    width: int,
    height: int,
    scheduler_name: str,
    cfg_scale: float,
    steps: int,
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

    unet = model.unet
    scheduler = model.scheduler

    device = TorchDevice.choose_torch_device()
    dtype = TorchDevice.choose_torch_dtype()

    print("conditioning created: ", positive, negative)
    seed = 123454321
    noise = get_noise(width=width, height=height, device=device, seed=seed)
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
        unet_config=model.scheduler.config,
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
            ModelPatcher.patch_unet_attention_processor(
                unet, denoise_ctx.inputs.attention_processor_cls
            ),
            ext_manager.patch_extensions(denoise_ctx),
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
    return Latents(result_latents)


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


@dataclass
class FLuxLatents:
    tensor: torch.Tensor


@torch.no_grad()
def flux_denoise_image(
    model: FluxModel,
    positive: FLUXConditioningInfo | list[FLUXConditioningInfo],
    negative: FLUXConditioningInfo | list[FLUXConditioningInfo] | None = None,
    init_latents: FLuxLatents | None = None,
    denoise_mask: torch.Tensor | None = None,
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
            cond_field=negative,
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

    cfg_scale = prep_cfg_scale(
        cfg_scale=cfg_scale,
        timesteps=timesteps,
        cfg_scale_start_step=cfg_scale_start_step,
        cfg_scale_end_step=cfg_scale_end_step,
    )

    with ExitStack() as exit_stack:
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
        # exit_stack.enter_context(
        #     LayerPatcher.apply_smart_model_patches(
        #         model=transformer,
        #         patches=self._lora_iterator(context),
        #         prefix=FLUX_LORA_TRANSFORMER_PREFIX,
        #         dtype=inference_dtype,
        #         cached_weights=cached_weights,
        #         force_sidecar_patching=model_is_quantized,
        #     )
        # )

        # Prepare IP-Adapter extensions.
        # pos_ip_adapter_extensions, neg_ip_adapter_extensions = (
        #     self._prep_ip_adapter_extensions(
        #         pos_image_prompt_clip_embeds=pos_image_prompt_clip_embeds,
        #         neg_image_prompt_clip_embeds=neg_image_prompt_clip_embeds,
        #         ip_adapter_fields=ip_adapter_fields,
        #         context=context,
        #         exit_stack=exit_stack,
        #         dtype=inference_dtype,
        #     )
        # )

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
            controlnet_extensions=[],
            pos_ip_adapter_extensions=[],
            neg_ip_adapter_extensions=[],
            step_callback=None,
        )

    result_latents = unpack(x.float(), height, width)
    result_latents = result_latents.detach().to("cpu")
    return FLuxLatents(result_latents)


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
