from ssui import workflow, Prompt, Image, Noise
from ssui_image.SDXL import SDXLModel, SDXLClip, SDXLLatent, SDXLLora, SDXLDenoise, SDXLLatentDecode,SDXLMergeLora
from ssui.config import SSUIConfig
from typing import List, Tuple

config = SSUIConfig()

@workflow
def txt2img(model: SDXLModel, positive: Prompt, negative: Prompt) -> Image:
    positive, negative = SDXLClip(config("Prompt To Condition"), model, positive, negative)
    latent = SDXLLatent(config("Create Empty Latent"))
    latent = SDXLDenoise(config("Denoise"), model, latent, positive, negative)
    return SDXLLatentDecode(config("Latent to Image"), model, latent)


@workflow
def txt2imgWithLora(model: SDXLModel, loras: List[SDXLLora], positive: Prompt, negative: Prompt) -> Image:
    model_w_lora = model    
    model_w_lora = SDXLMergeLora(config("Apply Lora"), model_w_lora, loras)
    positive, negative = SDXLClip(config("Prompt To Condition"), model, positive, negative)
    latent = SDXLLatent(config("Create Empty Latent"))
    latent = SDXLDenoise(config("Denoise"), model, latent, positive, negative)
    image = SDXLLatentDecode(config("Latent to Image"), model, latent)
    
    return image
