from ssui import workflow, Prompt, Image, Video
from ssui.config import SSUIConfig
from ssui_video.Wan import WanVideoModel, WanImageTextToVideo
from ssui_video.Hunyuan import HunyuanVideoModel, HunyuanTextToVideo
config = SSUIConfig()


@workflow
def img2vid(image: Image, prompt: Prompt, negative_prompt: Prompt) -> Video:
    model = WanVideoModel()
    video = WanImageTextToVideo(config("Generate Video"), model, image, prompt, negative_prompt)
    return Video("mp4", video, fps=30)


@workflow
def txt2vid(prompt: Prompt, negative_prompt: Prompt) -> Video:
    model = HunyuanVideoModel()
    video = HunyuanTextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", video, fps=30)
