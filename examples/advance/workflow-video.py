from ssui import workflow, Prompt, Image, Video
from ssui.config import SSUIConfig
from ssui_video.Wan import WanVideoModel, WanImageTextToVideo
from ssui_video.Hunyuan import HunyuanVideoModel, HunyuanTextToVideo
config = SSUIConfig()


@workflow
def img2vid(image: Image, prompt: Prompt, negative_prompt: Prompt) -> Video:
    if config.is_prepare():
        model = WanVideoModel()
    else:
        model = WanVideoModel.load()
    video = WanImageTextToVideo(config("Generate Video"), model, image, prompt, negative_prompt)
    return Video("mp4", video, fps=30)


@workflow
def txt2vid(prompt: Prompt) -> Video:
    if config.is_prepare():
        model = HunyuanVideoModel()
    else:
        model = HunyuanVideoModel.load()
    video = HunyuanTextToVideo(config("Generate Video"), model, prompt)
    return Video("mp4", video, fps=30)
