from ssui import workflow, Prompt, Image, Noise
from ssui_image.SDXL import SDXLModel, SDXLClip, SDXLLatent, SDXLLora, SDXLDenoise, SDXLLatentDecode
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
def txt2imgWithLora(model: SDXLModel, loras: List[SDXLLora], positive: Prompt, negative: Prompt) -> Tuple[Image, Image]:
    model_w_lora = model
    for lora in loras:
        model_w_lora = SDXLLora(config("Apply Lora"), model_w_lora, lora)
    positive, negative = SDXLClip(config("Prompt To Condition"), model, positive, negative)
    latent = SDXLLatent(config("Create Empty Latent"))
    latent = SDXLDenoise(config("Denoise"), model, latent, positive, negative)
    image = SDXLLatentDecode(config("Latent to Image"), model, latent)
    
    positive2, negative2 = SDXLClip(config("Prompt To Condition with Lora"), model, positive, negative)
    random_noise2 = Noise(config("Generate Noise with Lora"))
    latent2 = SDXLLatent(config("Noise To Latent with Lora"), random_noise2, model_w_lora)
    latent2 = SDXLDenoise(config("Denoise with Lora"), model_w_lora, latent2, positive2, negative2)
    image2 = SDXLLatentDecode(config("Latent to Image with Lora"), model, latent2)
    return image, image2
