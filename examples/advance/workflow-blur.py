from ssui import workflow, Prompt, Image
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxDenoise, FluxLatentDecode
from ssui.config import SSUIConfig
from PIL import ImageFilter

config = SSUIConfig()


@workflow
def txt2img(model: FluxModel, positive: Prompt, negative: Prompt) -> Image:
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    return FluxLatentDecode(config("Latent to Image"), model, latent)

@workflow
def txt2img_blur(model: FluxModel, positive: Prompt, negative: Prompt, blur_radius: float) -> Image:
    image = txt2img(model, positive, negative)
    image._image = image._image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    return image





