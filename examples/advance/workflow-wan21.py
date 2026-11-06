from ssui import workflow, Prompt, Video
from ssui.config import SSUIConfig
from ssui_video.Wan21Resident import Wan21Model, Wan21TextToVideo

config = SSUIConfig()


@workflow
def text_to_video(model: Wan21Model, prompt: Prompt, negative_prompt: Prompt) -> Video:
    frames = Wan21TextToVideo(config('Generate video'), model, prompt, negative_prompt)
    return Video('mp4', frames, fps=8)
