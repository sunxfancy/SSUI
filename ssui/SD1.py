from .base import Prompt, Noise

class SD1Model:
    pass

class SD1Condition:
    pass

def SD1Clip(config, model: SD1Model, positive: Prompt, negative: Prompt):
    return SD1Condition(), SD1Condition()

class SD1Latent:
    def __init__(self, config, noise: Noise, model: SD1Model):
        self.config = config
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

