from typing import Optional,List
from pathlib import Path
import torch
from backend.stable_diffusion.diffusion.conditioning_data import SDXLConditioningInfo
from ssui.config import SSUIConfig
from .api.conditioning import BasicConditioningInfo, create_sdxl_conditioning
from .api.denoise import decode_latents, denoise_image
from .api.model import (
    ModelLoaderService,
    UNetModel,
    ClipModel,
    VAEModel,
    load_model,
    load_sdxl_model,
    LoRAModel,
    load_lora
)
from ssui.base import Prompt, Image
from ssui.annotation import param
from ssui.controller import Select, Switch, Slider


_loader_instance = None


def getModelLoader():
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ModelLoaderService()
    return _loader_instance


class SDXLModel:
    def __init__(
        self,
        path: str = "",
        unet: Optional[UNetModel] = None,
        clip: Optional[ClipModel] = None,
        clip2: Optional[ClipModel] = None,
        vae: Optional[VAEModel] = None,
    ):
        self.path = path
        self.unet = unet
        self.clip = clip
        self.clip2 = clip2
        self.vae = vae

    @staticmethod
    def load(path: str) -> "SDXLModel":
        unet, clip, clip2, vae = load_sdxl_model(getModelLoader(), path)
        return SDXLModel(path, unet, clip, clip2, vae)


class SDXLCondition:
    def __init__(self, condition_info: Optional[SDXLConditioningInfo] = None):
        self.condition_info = condition_info


@param("ignoreLastLayer", Switch(), default=False)
def SDXLClip(config: SSUIConfig, model: SDXLModel, positive: Prompt, negative: Prompt):
    if config.is_prepare():
        return SDXLCondition(), SDXLCondition()

    print("SDXLClip executed")
    print("ignoreLastLayer:", config["ignoreLastLayer"])
    print("positive:", positive.text)
    print("negative:", negative.text)

    # TODO: 需要把这组参数处理一下
    positive_condition = create_sdxl_conditioning(positive.text, "", model.clip, model.clip2, 1024, 1024, 0, 0, 1024, 1024)
    negative_condition = create_sdxl_conditioning(negative.text, "", model.clip, model.clip2, 1024, 1024, 0, 0, 1024, 1024)

    return SDXLCondition(positive_condition), SDXLCondition(negative_condition)


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
class SDXLLatent:
    def __init__(self, config: SSUIConfig, tensor: Optional[torch.Tensor] = None):
        self.width: int = config["width"]
        self.height: int = config["height"]
        self.tensor: Optional[torch.Tensor] = tensor

        if config.is_prepare():
            return

        print("SDXLLatent executed")
        print("width:", self.width)
        print("height:", self.height)

    @staticmethod
    def from_image(image: Image) -> "SDXLLatent":
        pass


class SDXLLora:
    def __init__(self, path: str = "", lora: Optional[LoRAModel] = None, weight:float = 1.0):
        self.path = path
        self.lora = lora
        self.weight = weight
    @staticmethod
    def load(path: List[Path],weights: Optional[List[float]] = None) ->"List[SDXLLora]":
        if weights is not None and (len(path) != len(weights)):
            raise ValueError("LoRA paths list and weights list must have the same length")
        
        if weights is None: lora_weights = [1.0] * len(path)
        else:
            lora_weights = weights
        sdxlLora = []
        for i, lora_path in enumerate(path):
            lora_models = load_lora(getModelLoader(),lora_path, lora_weights[i])
            sdxlLora.append(SDXLLora(lora=lora_models,weight=lora_weights[i]))

        return sdxlLora
    
@param(
    "steps",
    Slider(1, 100, 1, labels=[1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
    default=30,
)
@param(
    "scheduler",
    Select(
        "ddim",
        "ddpm",
        "deis",
        "deis_k",
        "lms",
        "lms_k",
        "pndm",
        "heun",
        "heun_k",
        "euler",
        "euler_k",
        "euler_a",
        "kdpm_2",
        "kdpm_2_k",
        "kdpm_2_a",
        "kdpm_2_a_k",
        "dpmpp_2s",
        "dpmpp_2s_k",
        "dpmpp_2m",
        "dpmpp_2m_k",
        "dpmpp_2m_sde",
        "dpmpp_2m_sde_k",
        "dpmpp_3m",
        "dpmpp_3m_k",
        "dpmpp_sde",
        "dpmpp_sde_k",
        "unipc",
        "unipc_k",
        "lcm",
        "tcd",
    ),
    default="euler_a",
)
@param("CFG", Slider(0, 15, 0.1), default=7.5)
def SDXLDenoise(
    config: SSUIConfig,
    model: SDXLModel,
    latent: SDXLLatent,
    positive: SDXLCondition,
    negative: SDXLCondition,
):
    if config.is_prepare():
        return SDXLLatent(config("DenoiseToLatents"))

    print("SDXLDenoise executed")
    print("scheduler:", config["scheduler"])
    print("steps:", config["steps"])
    print("CFG:", config["CFG"])

    tensor = denoise_image(
        model=model.unet,
        positive=positive.condition_info,
        negative=negative.condition_info,
        seed=123454321,
        width=latent.width,
        height=latent.height,
        scheduler_name=config["scheduler"],
        steps=config["steps"],
        cfg_scale=config["CFG"],
    )
    return SDXLLatent(config("DenoiseToLatents"), tensor)


def SDXLLatentDecode(config: SSUIConfig, model: SDXLModel, latent: SDXLLatent):
    if config.is_prepare():
        return Image()

    print("SDXLLatentDecode executed")

    image = decode_latents(model.vae, latent.tensor)
    return Image(image)

def SDXLMergeLora(
    config,
    model: SDXLModel,
    loraModel: List[SDXLLora]
):
    if config.is_prepare():
        return SDXLModel(config("Add Empty Lora to SDXL"))

    print("SDXLMergeLora executed")

    model.unet.loras = loraModel
    model.clip.loras = loraModel
    model.clip2.loras = loraModel
    
    return model