from .base import Prompt, Noise, Image
from .annotation import param
from .controller import Switch, Slider

class SD1Model:
    @staticmethod
    def load(path: str):
        SD1Model(path)

    def __init__(self, path: str):
        self.path = path
    

class SD1Condition:
    pass

@param("ignoreLastLayer", Switch(), default=False)
def SD1Clip(config, model: SD1Model, positive: Prompt, negative: Prompt):
    if config.is_prepare():
        return SD1Condition(), SD1Condition()

    print("SD1Clip executed")

    return SD1Condition(), SD1Condition()

@param("width", Slider(512, 4096, 64, labels=[512, 768, 1024, 1536, 1920, 2048, 3840, 4096]), default=512)
@param("height", Slider(512, 4096, 64, labels=[512, 768, 1024, 1536, 1920, 2048, 3840, 4096]), default=512)
class SD1Latent:
    def __init__(self, config, noise: Noise, model: SD1Model):
        width = config["width"]
        height = config["height"]
        self.noise = noise
        self.model = model

def SD1Decode(config):
    pass

class SD1Lora:
    def __init__(self, config):
        self.config = config


@param("step", Slider(1, 100, 1, labels=[1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]), default=20)
@param("CFG", Slider(0, 1, 0.05), default=0.7)
def SD1Denoise(config, model: SD1Model, latent: SD1Latent, positive: SD1Condition, negative: SD1Condition):
    if config.is_prepare():
        return

    print("SD1Denoise executed")
    return

def SD1LatentDecode(config, model: SD1Model, latent: SD1Latent):
    if config.is_prepare():
        return Image()

    print("SD1LatentDecode executed")
    return Image()

def SD1IPAdapter(config):
    pass    

