"""Local Wan 2.1 1.3B; download with yarn test:wan:smoke --download-only."""
from ssui import workflow, Prompt, Video
from ssui.config import SSUIConfig
from ssui_video.Wan21 import Wan21T2V13BModel, Wan21TextToVideo

config = SSUIConfig()


@workflow
def txt2vid_wan21_13b(prompt: Prompt, negative_prompt: Prompt) -> Video:
    model = None if config.is_prepare() else Wan21T2V13BModel.load_local()
    frames = Wan21TextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", frames, fps=8)
