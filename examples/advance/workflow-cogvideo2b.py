from ssui import workflow, Prompt, Video
from ssui.config import SSUIConfig
from ssui_video.CogVideo2B import CogVideo2BModel, CogVideo2BTextToVideo

config = SSUIConfig()


@workflow
def text_to_video(model: CogVideo2BModel, prompt: Prompt, negative_prompt: Prompt) -> Video:
    frames = CogVideo2BTextToVideo(config('Generate video'), model, prompt, negative_prompt)
    return Video('mp4', frames, fps=8)
