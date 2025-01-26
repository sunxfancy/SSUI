from .base import Prompt, Noise
from .annotation import param
from .controller import Switch, Slider

class SD1Model:
    pass

class SD1Condition:
    pass

@param("ignoreLastLayer", Switch(), default=False)
def SD1Clip(config, model: SD1Model, positive: Prompt, negative: Prompt):
    return SD1Condition(), SD1Condition()

@param("width", Slider(512, 4096, 64), default=512)
@param("height", Slider(512, 4096, 64), default=512)
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


@param("step", Slider(1, 100, 1), default=20)
@param("CFG", Slider(0, 1, 0.05), default=0.7)
def SD1Denoise(config, model: SD1Model, latent: SD1Latent, positive: SD1Condition, negative: SD1Condition):
    pass

def SD1LatentDecode(config, model: SD1Model, latent: SD1Latent):
    pass

def SD1IPAdapter(config):
    pass    

