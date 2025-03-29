
from ssui import workflow, Prompt, Image, Noise
from ssui_image.SD1 import SD1Model, SD1Clip, SD1Latent, SD1Lora, SD1Denoise, SD1LatentDecode, SD1IPAdapter
from ssui.config import SSUIConfig
from typing import List, Tuple

config = SSUIConfig()

@workflow
def txt2img(model: SD1Model, positive: Prompt, negative: Prompt) -> Image:
    print(model, positive, negative)
    positive, negative = SD1Clip(config("Prompt To Condition"), model, positive, negative)
    latent = SD1Latent(config("Create Empty Latent"))
    latent = SD1Denoise(config("Denoise"), model, latent, positive, negative)
    return SD1LatentDecode(config("Latent to Image"), model, latent)


@workflow
def txt2imgWithRef(model: SD1Model, positive: Prompt, negative: Prompt, reference: Image) -> Tuple[Image, Image]:
    positive, negative = SD1Clip(config("Prompt To Condition"), model, positive, negative)
    latent = SD1Latent(config("Create Empty Latent"))
    adapter = SD1IPAdapter(config("Image Reference"), reference)
    latent = SD1Denoise(config("Denoise"), model, latent, positive, negative, adapter)
    return SD1LatentDecode(config("Latent to Image"), latent)


@workflow
def txt2imgWithLora(model: SD1Model, loras: List[SD1Lora], positive: Prompt, negative: Prompt) -> Tuple[Image, Image]:
    model_w_lora = model
    for lora in loras:
        model_w_lora = SD1Lora(config("Apply Lora"), model_w_lora, lora)
    positive, negative = SD1Clip(config("Prompt To Condition"), model, positive, negative)
    latent = SD1Latent(config("Create Empty Latent"))
    latent = SD1Denoise(config("Denoise"), model, latent, positive, negative)
    image = SD1LatentDecode(config("Latent to Image"), latent)
    
    positive2, negative2 = SD1Clip(config("Prompt To Condition with Lora"), model, positive, negative)
    random_noise2 = Noise(config("Generate Noise with Lora"))
    latent2 = SD1Latent(config("Noise To Latent with Lora"), random_noise2, model_w_lora)
    latent2 = SD1Denoise(config("Denoise with Lora"), model_w_lora, latent2, positive2, negative2)
    image2 = SD1LatentDecode(config("Latent to Image with Lora"), latent)
    
    return image, image2

