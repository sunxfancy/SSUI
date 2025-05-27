from ssui import workflow, Prompt, Image, Noise
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxLora, FluxDenoise, FluxLatentDecode,FluxMergeLora
from ssui.config import SSUIConfig
from typing import List, Tuple

config = SSUIConfig()

@workflow
def txt2img(model: FluxModel, positive: Prompt, negative: Prompt) -> Image:
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    return FluxLatentDecode(config("Latent to Image"), model, latent)


@workflow
def txt2imgWithLora(model: FluxModel, loras: List[FluxLora], positive: Prompt, negative: Prompt) -> Image:
    model_w_lora = model
    model_w_lora = FluxMergeLora(config("Apply Lora"), model_w_lora, loras)
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    image = FluxLatentDecode(config("Latent to Image"), model, latent)
    
    return image 