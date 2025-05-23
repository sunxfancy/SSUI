
from ssui import workflow, Prompt, Image, Noise
from ssui_image.SD1 import SD1Model, SD1Clip, SD1Latent, SD1Lora, SD1Denoise, SD1LatentDecode,SD1MergeLora, SD1IPAdapter
from ssui.config import SSUIConfig
from typing import List, Tuple

config = SSUIConfig()

@workflow
def txt2img(model: SD1Model, positive: Prompt, negative: Prompt) -> Image:
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
def txt2imgWithLora(model: SD1Model, loras: List[SD1Lora], positive: Prompt, negative: Prompt) -> Image:
    model_w_lora = model
    model_w_lora = SD1MergeLora(config("Apply Lora"), model_w_lora, loras)
    positive, negative = SD1Clip(config("Prompt To Condition"), model, positive, negative)
    latent = SD1Latent(config("Create Empty Latent"))
    latent = SD1Denoise(config("Denoise"), model, latent, positive, negative)
    image = SD1LatentDecode(config("Latent to Image"), latent)
    
    return image
