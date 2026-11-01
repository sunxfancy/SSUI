from ssui import Image, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_video.QwenImage import (
    QwenImageEditModel,
    QwenImageModel,
    QwenPixelArtEdit,
    QwenPixelArtGenerate,
)


config = SSUIConfig()


@workflow
def text_to_pixel_asset(
    model: QwenImageModel,
    positive: Prompt,
    negative: Prompt,
) -> Image:
    return QwenPixelArtGenerate(config("Qwen Pixel Art"), model, positive, negative)


@workflow
def reference_to_pixel_asset(
    model: QwenImageEditModel,
    reference: Image,
    positive: Prompt,
    negative: Prompt,
) -> Image:
    return QwenPixelArtEdit(
        config("Qwen Pixel Art Edit"), model, reference, positive, negative
    )
