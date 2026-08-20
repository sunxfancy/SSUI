"""稳定扩散（SD1/SDXL/Flux）工作流的确定性假实现。"""

import torch
from PIL import Image as PILImage

from ssui.base import Image


class FakeSD1Model:
    @staticmethod
    def load(path):
        return FakeSD1Model()

    def __init__(self):
        self.unet = object()
        self.vae = object()
        self.clip = object()


class FakeSDXLModel:
    @staticmethod
    def load(path):
        return FakeSDXLModel()

    def __init__(self):
        self.unet = object()
        self.vae = object()
        self.clip = object()
        self.clip2 = object()


class FakeFluxModel:
    @staticmethod
    def load(model_path, t5_encoder_path=None, clip_path=None, vae_path=None):
        return FakeFluxModel()

    def __init__(self):
        self.transformer = object()
        self.t5_model = object()
        self.clip_model = object()
        self.vae = object()


class FakeCondition:
    """模拟 CLIP 输出的 condition，shape 固定为 1x4x8x8。"""

    def __init__(self, tensor=None):
        self.condition_info = (
            tensor if tensor is not None else torch.zeros(1, 4, 8, 8)
        )
        self.tensor = self.condition_info


class FakeLatent:
    """模拟 Denoise 输出的 latent，shape 固定为 1x4x8x8。"""

    def __init__(self, tensor=None):
        self.tensor = tensor if tensor is not None else torch.zeros(1, 4, 8, 8)
        self.width = 64
        self.height = 64


def fake_clip(config, model, positive, negative):
    return FakeCondition(), FakeCondition()


def fake_latent(config, tensor=None):
    return FakeLatent(tensor)


def fake_denoise(config, model, latent, positive, negative):
    return latent


def fake_decode(config, *args, **kwargs):
    return Image(PILImage.new("RGB", (64, 64), (120, 60, 200)))
