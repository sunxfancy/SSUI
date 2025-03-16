import unittest
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
        self, model_path: Path, loader: Optional[Callable[[Path], AnyModel]] = None
    ) -> LoadedModelWithoutConfig:
        cache_key = str(model_path)
        try:
            return LoadedModelWithoutConfig(cache_record=self._ram_cache.get(key=cache_key), cache=self._ram_cache)
        except IndexError:
            pass

        def torch_load_file(checkpoint: Path) -> AnyModel:
            result = torch_load(checkpoint, map_location="cpu")
            return result

        def diffusers_load_directory(directory: Path) -> AnyModel:
            load_class = GenericDiffusersLoader(
                app_config=self._app_config,
                logger=self._logger,
                ram_cache=self._ram_cache,
                convert_cache=self.convert_cache,
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
        self._ram_cache.put(key=cache_key, model=raw_model)
        return LoadedModelWithoutConfig(cache_record=self._ram_cache.get(key=cache_key), cache=self._ram_cache)


def generate_image(prompt: str, negative: str):


    def run_denoise(seed, noise, latents, unet, scheduler, unet_config, positive_conditioning, negative_conditioning, cfg_scale, steps, cfg_rescale_multiplier):
        ext_manager = ExtensionsManager()

        device = TorchDevice.choose_torch_device()
        dtype = TorchDevice.choose_torch_dtype()

        _, _, latent_height, latent_width = latents.shape

        conditioning_data = get_conditioning_data(
            context=context,
            positive_conditioning_field=positive_conditioning,
            negative_conditioning_field=negative_conditioning,
            cfg_scale=cfg_scale,
            steps=steps,
            latent_height=latent_height,
            latent_width=latent_width,
            device=device,
            dtype=dtype,
            # TODO: old backend, remove
            cfg_rescale_multiplier=cfg_rescale_multiplier,
        )

        scheduler = get_scheduler(
            context=context,
            scheduler_info=unet.scheduler,
            scheduler_name=scheduler,
            seed=seed,
            unet_config=unet_config,
        )

        timesteps, init_timestep, scheduler_step_kwargs = self.init_scheduler(
            scheduler,
            seed=seed,
            device=device,
            steps=self.steps,
            denoising_start=self.denoising_start,
            denoising_end=self.denoising_end,
        )

        ### preview
        def step_callback(state: PipelineIntermediateState) -> None:
            context.util.sd_step_callback(state, unet_config.base)

        ext_manager.add_extension(PreviewExt(step_callback))

        ### cfg rescale
        if self.cfg_rescale_multiplier > 0:
            ext_manager.add_extension(RescaleCFGExt(self.cfg_rescale_multiplier))

        ### freeu
        if self.unet.freeu_config:
            ext_manager.add_extension(FreeUExt(self.unet.freeu_config))

        ### lora
        if self.unet.loras:
            for lora_field in self.unet.loras:
                ext_manager.add_extension(
                    LoRAExt(
                        node_context=context,
                        model_id=lora_field.lora,
                        weight=lora_field.weight,
                    )
                )
        ### seamless
        if self.unet.seamless_axes:
            ext_manager.add_extension(SeamlessExt(self.unet.seamless_axes))

        ### inpaint
        mask, masked_latents, is_gradient_mask = self.prep_inpaint_mask(context, latents)
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
        if noise is not None:
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

        # context for loading additional models
        with ExitStack() as exit_stack:
            # later should be smth like:
            # for extension_field in self.extensions:
            #    ext = extension_field.to_extension(exit_stack, context, ext_manager)
            #    ext_manager.add_extension(ext)
            self.parse_controlnet_field(exit_stack, context, self.control, ext_manager)
            bgr_mode = self.unet.unet.base == BaseModelType.StableDiffusionXL
            self.parse_t2i_adapter_field(exit_stack, context, self.t2i_adapter, ext_manager, bgr_mode)

            # ext: t2i/ip adapter
            ext_manager.run_callback(ExtensionCallbackType.SETUP, denoise_ctx)

            with (
                context.models.load(self.unet.unet).model_on_device() as (cached_weights, unet),
                ModelPatcher.patch_unet_attention_processor(unet, denoise_ctx.inputs.attention_processor_cls),
                # ext: controlnet
                ext_manager.patch_extensions(denoise_ctx),
                # ext: freeu, seamless, ip adapter, lora
                ext_manager.patch_unet(unet, cached_weights),
            ):
                sd_backend = StableDiffusionBackend(unet, scheduler)
                denoise_ctx.unet = unet
                result_latents = sd_backend.latents_from_embeddings(denoise_ctx, ext_manager)

        # https://discuss.huggingface.co/t/memory-usage-by-later-pipeline-stages/23699
        result_latents = result_latents.detach().to("cpu")
        TorchDevice.empty_cache()

        name = context.tensors.save(tensor=result_latents)
        return LatentsOutput.build(latents_name=name, latents=result_latents, seed=None)



class TestBackend(unittest.TestCase):
    def test_backend(self):
        generate_image("a beautiful girl", "a bad image")


