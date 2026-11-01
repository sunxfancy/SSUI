from typing import List

from ssui import Image, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_image.Flux2 import Flux2KleinGenerate, Flux2KleinModel


config = SSUIConfig()


@workflow
def txt2img(model: Flux2KleinModel, prompt: Prompt) -> Image:
    return Flux2KleinGenerate(config("Generate"), model, prompt, [])


@workflow
def edit(
    model: Flux2KleinModel,
    reference_images: List[Image],
    prompt: Prompt,
) -> Image:
    return Flux2KleinGenerate(
        config("Generate or Edit"),
        model,
        prompt,
        reference_images,
    )
