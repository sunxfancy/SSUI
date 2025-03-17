import PIL
from backend.model_patcher import ModelPatcher
from backend.stable_diffusion.denoise_context import DenoiseContext, DenoiseInputs
from backend.stable_diffusion.diffusion.conditioning_data import (
    BasicConditioningInfo,
   
)
from backend.stable_diffusion.diffusion_backend import StableDiffusionBackend
from backend.stable_diffusion.extension_callback_type import ExtensionCallbackType
from backend.stable_diffusion.extensions_manager import ExtensionsManager
from backend.util.devices import TorchDevice
import inspect
from contextlib import ExitStack

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

from .conditioning import get_conditioning_data
from .model import UNetModel, VAEModel



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
def denoise_image(model: UNetModel, positive: BasicConditioningInfo, negative: BasicConditioningInfo, seed: int, width: int, height: int, scheduler_name: str, cfg_scale: float, steps: int):
    unet = model.unet
    scheduler = model.scheduler

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
    return result_latents


def decode_latents(model: VAEModel, result_latents: torch.Tensor) -> PIL.Image.Image | None:
    vae = model.vae
    assert isinstance(vae.model, (AutoencoderKL, AutoencoderTiny))
    with (
        vae.model_on_device() as (_, vae),
    ):
        result_latents = result_latents.to(device=TorchDevice.choose_torch_device())
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
