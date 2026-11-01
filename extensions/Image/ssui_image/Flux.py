from typing import Optional,List
from pathlib import Path
import torch
import PIL

from ssui.config import SSUIConfig
from .api.conditioning import BasicConditioningInfo, create_flux_conditioning
from .api.denoise import (
    ApplyRange,
    flux_decode_latents,
    flux_denoise_image,
    FluxControlNet as FluxControlNetField,
    FLuxLatents,
)
from .api.model import (
    ModelLoaderService,
    FluxModel as ApiFluxModel,
    T5EncoderModel,
    ClipModel,
    VAEModel,
    load_flux_model,
    LoRAModel,
    load_lora,
    ControlNetModel,
    load_controlnet,
    load_vae,
)
from ssui.base import Prompt, Image
from ssui.annotation import param
from ssui.controller import Random, Select, Switch, Slider

_loader_instance = None


def getModelLoader():
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ModelLoaderService()
    return _loader_instance


class FluxModel:
    def __init__(
        self,
        model_path: str = "",
        t5_encoder_path: str = "",
        clip_path: str = "",
        vae_path: str = "",
        transformer: Optional[ApiFluxModel] = None,
        t5_model: Optional[T5EncoderModel] = None,
        clip_model: Optional[ClipModel] = None,
        vae: Optional[VAEModel] = None,
    ):
        self.model_path = model_path
        self.t5_encoder_path = t5_encoder_path
        self.clip_path = clip_path
        self.vae_path = vae_path
        self.transformer = transformer
        self.t5_model = t5_model
        self.clip_model = clip_model
        self.vae = vae

    @staticmethod
    def load(model_path: str, t5_encoder_path: str, clip_path: str, vae_path: str):
        transformer, t5_model, clip_model, vae = load_flux_model(
            getModelLoader(), model_path, t5_encoder_path, clip_path, vae_path
        )
        return FluxModel(model_path, t5_encoder_path, clip_path, vae_path, transformer, t5_model, clip_model, vae)


class FluxCondition:
    def __init__(self, condition_info: Optional[BasicConditioningInfo] = None):
        self.condition_info = condition_info


@param("ignoreLastLayer", Switch(), default=False)
def FluxClip(config: SSUIConfig, model: FluxModel, positive: Prompt, negative: Prompt):
    if config.is_prepare():
        return FluxCondition(), FluxCondition()

    print("FluxClip executed")
    print("ignoreLastLayer:", config["ignoreLastLayer"])
    print("positive:", positive.text)
    print("negative:", negative.text)

    positive_condition = create_flux_conditioning(
        positive.text, t5_encoder=model.t5_model, clip_model=model.clip_model
    )
    negative_condition = create_flux_conditioning(
        negative.text, t5_encoder=model.t5_model, clip_model=model.clip_model
    )

    return FluxCondition(positive_condition), FluxCondition(negative_condition)


@param(
    "width",
    Slider(1024, 4096, 64, labels=[1024, 1536, 1920, 2048, 3840, 4096]),
    default=1024,
)
@param(
    "height",
    Slider(1024, 4096, 64, labels=[1024, 1536, 1920, 2048, 3840, 4096]),
    default=1024,
)
class FluxLatent:
    def __init__(self, config: SSUIConfig, tensor: Optional[torch.Tensor] = None):
        self.width: int = config["width"]
        self.height: int = config["height"]
        self.tensor: Optional[torch.Tensor] = tensor

        if config.is_prepare():
            return

        print("FluxLatent executed")
        print("width:", self.width)
        print("height:", self.height)

    @staticmethod
    def from_image(image: Image) -> "FluxLatent":
        pass


class FluxLora:
    def __init__(self, path: str = "", lora: Optional[LoRAModel] = None, weight:float = 0.75):
        self.path = path
        self.lora = lora
        self.weight = weight
    @staticmethod
    def load_one(path: str, weight: float = 0.75) -> "FluxLora":
        lora_model = load_lora(getModelLoader(), Path(path), weight)
        return FluxLora(path=path, lora=lora_model, weight=weight)

    @staticmethod
    def load(path: List[Path],weights: Optional[List[float]] = None) ->"List[FluxLora]":
        if weights is not None and (len(path) != len(weights)):
            raise ValueError("LoRA paths list and weights list must have the same length")
        
        if weights is None: lora_weights = [0.75] * len(path)
        else:
            lora_weights = weights
        fluxlora = []
        for i, lora_path in enumerate(path):
            lora_models = load_lora(getModelLoader(),lora_path, lora_weights[i])
            fluxlora.append(FluxLora(lora=lora_models,weight=lora_weights[i]))

        return fluxlora


class FluxControlNet:
    """FLUX ControlNet workflow node (XLabs / InstantX).

    Pairs a FLUX ControlNet model file with a control image and tuning
    parameters. InstantX union ControlNets additionally need a VAE to encode
    the control image (pass ``vae_path``); XLabs ControlNets don't.
    """

    def __init__(
        self,
        path: str = "",
        image_path: str = "",
        controlnet: Optional[ControlNetModel] = None,
        image: Optional[PIL.Image.Image] = None,
        vae: Optional[VAEModel] = None,
        vae_path: str = "",
        weight: float = 1.0,
        resize_mode: str = "just_resize",
        instantx_control_mode: int = -1,
        begin_step_percent: float = 0.0,
        end_step_percent: float = 1.0,
    ):
        self.path = path
        self.image_path = image_path
        self.controlnet = controlnet
        self.image = image
        self.vae = vae
        self.vae_path = vae_path
        self.weight = weight
        self.resize_mode = resize_mode
        self.instantx_control_mode = instantx_control_mode
        self.begin_step_percent = begin_step_percent
        self.end_step_percent = end_step_percent

    @staticmethod
    def load(
        path: str,
        image_path: str,
        vae_path: str = "",
        weight: float = 1.0,
        resize_mode: str = "just_resize",
        instantx_control_mode: int = -1,
        begin_step_percent: float = 0.0,
        end_step_percent: float = 1.0,
    ) -> "FluxControlNet":
        controlnet = load_controlnet(getModelLoader(), Path(path))
        image = PIL.Image.open(image_path).convert("RGB")
        vae = load_vae(getModelLoader(), Path(vae_path)) if vae_path else None
        return FluxControlNet(
            path=path,
            image_path=image_path,
            controlnet=controlnet,
            image=image,
            vae=vae,
            vae_path=vae_path,
            weight=weight,
            resize_mode=resize_mode,
            instantx_control_mode=instantx_control_mode,
            begin_step_percent=begin_step_percent,
            end_step_percent=end_step_percent,
        )

    def to_api_field(self) -> FluxControlNetField:
        if self.controlnet is None or self.image is None:
            raise ValueError(
                "FluxControlNet is not loaded; call FluxControlNet.load() first."
            )
        return FluxControlNetField(
            image=self.image,
            control_model=self.controlnet.controlnet,
            control_weight=self.weight,
            apply_range=ApplyRange(
                begin_step_percent=self.begin_step_percent,
                end_step_percent=self.end_step_percent,
            ),
            resize_mode=self.resize_mode,
            instantx_control_mode=self.instantx_control_mode,
        )

@param(
    "steps",
    Slider(1, 100, 1, labels=[1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
    default=4,
)
@param("CFG", Slider(0, 15, 0.1), default=1.0)
@param("CFG_start_step", Slider(0, 100, 1), default=0)
@param("CFG_end_step", Slider(-1, 100, 1), default=-1)
@param("guidance", Slider(0, 15, 0.1), default=4.0)
@param("add_noise", Switch(), default=True)
@param("denoising_start", Slider(0, 1.0, 0.01), default=0.0)
@param("denoising_end", Slider(0, 1.0, 0.01), default=1.0)
@param("seed", Random(), default=123454321)
def FluxDenoise(
    config,
    model: FluxModel,
    latent: FluxLatent,
    positive: FluxCondition,
    negative: FluxCondition,
    control: Optional[FluxControlNet] = None,
):
    if config.is_prepare():
        return FluxLatent(config("DenoiseToLatents"))

    print("FluxDenoise executed")
    print("steps:", config["steps"])
    print("CFG:", config["CFG"])
    print("seed:", config["seed"])

    # 创建FLuxLatents对象
    init_latents = None
    if latent.tensor is not None:
        init_latents = FLuxLatents(tensor=latent.tensor)

    tensor = flux_denoise_image(
        model=model.transformer,
        positive=positive.condition_info,
        negative=negative.condition_info,
        init_latents=init_latents,
        seed=config["seed"],
        width=latent.width,
        height=latent.height,
        cfg_scale=config["CFG"],
        steps=config["steps"],
        cfg_scale_start_step=config["CFG_start_step"],
        cfg_scale_end_step=config["CFG_end_step"],
        guidance=config["guidance"],
        add_noise=config["add_noise"],
        denoising_start=config["denoising_start"],
        denoising_end=config["denoising_end"],
        control=control.to_api_field() if control is not None else None,
        controlnet_vae=control.vae if control is not None else None,
    )
    return FluxLatent(config("DenoiseToLatents"), tensor.tensor)


def FluxLatentDecode(config, model: FluxModel, latent: FluxLatent):
    if config.is_prepare():
        return Image()

    print("FluxLatentDecode executed")

    # 创建FLuxLatents对象
    
    flux_latents = FLuxLatents(tensor=latent.tensor)
    
    image = flux_decode_latents(model.vae, flux_latents)
    return Image(image)

def FluxMergeLora(
    config,
    model: FluxModel,
    loraModel: List[FluxLora]
):
    if config.is_prepare():
        return FluxModel(config("Add Empty Lora to Flux"))

    print("FluxMergeLora executed")

    model.transformer.loras = loraModel
    model.clip_model.loras = loraModel
    model.t5_model.loras = loraModel
    
    return model
