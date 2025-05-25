from ssui import workflow, Prompt, Image, Mesh
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxDenoise, FluxLatentDecode
from ssui.config import SSUIConfig
from ssui_3dmodel.Trellis import TrellisModel, GenModel
from typing import List, Tuple

config = SSUIConfig()


@workflow
def txt2img(model: FluxModel, positive: Prompt, negative: Prompt) -> Image:
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    return FluxLatentDecode(config("Latent to Image"), model, latent)

@workflow
def img2mesh(image: Image) -> Mesh:
    model = TrellisModel.load("jetx/trellis-image-large")
    return GenModel(config("GenModel"), model, image)

