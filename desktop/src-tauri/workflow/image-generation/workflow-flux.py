from ssui import workflow, Prompt, Image, Noise
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxLora, FluxDenoise, FluxLatentDecode
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
def txt2imgWithLora(model: FluxModel, loras: List[FluxLora], positive: Prompt, negative: Prompt) -> Tuple[Image, Image]:
    model_w_lora = model
    for lora in loras:
        model_w_lora = FluxLora(config("Apply Lora"), model_w_lora, lora)
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    image = FluxLatentDecode(config("Latent to Image"), model, latent)
    
    positive2, negative2 = FluxClip(config("Prompt To Condition with Lora"), model, positive, negative)
    random_noise2 = Noise(config("Generate Noise with Lora"))
    latent2 = FluxLatent(config("Noise To Latent with Lora"), random_noise2, model_w_lora)
    latent2 = FluxDenoise(config("Denoise with Lora"), model_w_lora, latent2, positive2, negative2)
    image2 = FluxLatentDecode(config("Latent to Image with Lora"), model, latent2)
    
    return image, image2 