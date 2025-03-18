from dataclasses import dataclass
from typing import Optional
from ssui_api.conditioning import BasicConditioningInfo, create_conditioning
from ssui_api.denoise import decode_latents, denoise_image
from ssui_api.model import (
    ModelLoaderService,
    UNetModel,
    ClipModel,
    VAEModel,
    load_model,
)
from .base import Prompt, Noise, Image
from .annotation import param
from .controller import Select, Switch, Slider


_loader_instance = None


def getModelLoader():
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ModelLoaderService()
    return _loader_instance


class SD1Model:
    def __init__(
        self,
        path: str = "",
        unet: Optional[UNetModel] = None,
        clip: Optional[ClipModel] = None,
        vae: Optional[VAEModel] = None,
    ):
        self.path = path
        self.unet = unet
        self.clip = clip
        self.vae = vae

    @staticmethod
    def load(path: str):
        unet, clip, vae = load_model(getModelLoader(), path)
        return SD1Model(path, unet, clip, vae)


class SD1Condition:
    def __init__(self, condition_info: Optional[BasicConditioningInfo] = None):
        self.condition_info = condition_info


@param("ignoreLastLayer", Switch(), default=False)
def SD1Clip(config, model: SD1Model, positive: Prompt, negative: Prompt):
    if config.is_prepare():
        return SD1Condition(), SD1Condition()

    print("SD1Clip executed")
    print("ignoreLastLayer:", config["ignoreLastLayer"])
    print("positive:", positive.text)
    print("negative:", negative.text)
    
    positive_condition = create_conditioning(positive.text, model.clip)
    negative_condition = create_conditioning(negative.text, model.clip)

    return SD1Condition(positive_condition), SD1Condition(negative_condition)


@param(
    "width",
    Slider(512, 4096, 64, labels=[512, 768, 1024, 1536, 1920, 2048, 3840, 4096]),
    default=512,
)
@param(
    "height",
    Slider(512, 4096, 64, labels=[512, 768, 1024, 1536, 1920, 2048, 3840, 4096]),
    default=512,
)
class SD1Latent:
    def __init__(self, config, tensor=None):
        self.width = config["width"]
        self.height = config["height"]
        self.tensor = tensor
        
        if config.is_prepare():
            return
        
        print("SD1Latent executed")
        print("width:", self.width)
        print("height:", self.height)

    @staticmethod
    def from_image(image: Image) -> "SD1Latent":
        pass


def SD1Decode(config):
    pass


class SD1Lora:
    def __init__(self, config):
        self.config = config


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
    default="ddim",
)
@param("CFG", Slider(0, 15, 0.1), default=7.5)
def SD1Denoise(
    config,
    model: SD1Model,
    latent: SD1Latent,
    positive: SD1Condition,
    negative: SD1Condition,
):
    if config.is_prepare():
        return SD1Latent(config("DenoiseToLatents"))

    print("SD1Denoise executed")
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
    return SD1Latent(config("DenoiseToLatents"), tensor)


def SD1LatentDecode(config, model: SD1Model, latent: SD1Latent):
    if config.is_prepare():
        return Image()

    print("SD1LatentDecode executed")

    image = decode_latents(model.vae, latent.tensor)
    return Image(image)


def SD1IPAdapter(config):
    pass
