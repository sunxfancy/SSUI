from ssui import Image, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_image.MOSSImage import MOSSImageGenerate, MOSSImageModel


config = SSUIConfig()


@workflow
def txt2img(model: MOSSImageModel, prompt: Prompt, negative_prompt: Prompt) -> Image:
    # Load OpenMOSS-Team/MOSS-Image-SFT (or a local Base/SFT bundle) in the model
    # input. A layout JSON string can be supplied directly as the positive prompt.
    return MOSSImageGenerate(config("MOSS Generate"), model, prompt, negative_prompt)
