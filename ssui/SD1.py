from .base import Prompt, Noise
from .annotation import param

class SD1Model:
    pass

class SD1Condition:
    pass

@param("ignoreLastLayer", bool, default=False)
def SD1Clip(config, model: SD1Model, positive: Prompt, negative: Prompt):
    return SD1Condition(), SD1Condition()

@param("width", int, default=512)
@param("height", int, default=512)
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

def SD1Denoise(config, model: SD1Model, latent: SD1Latent, positive: SD1Condition, negative: SD1Condition):
    pass

def SD1LatentDecode(config, model: SD1Model, latent: SD1Latent):
    pass

def SD1IPAdapter(config):
    pass    

