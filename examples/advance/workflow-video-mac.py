"""AnimateDiff on Mac. Download weights once with yarn test:video:smoke --download-only."""
from ssui import workflow, Prompt, Video
from ssui.config import SSUIConfig
from ssui_video.AnimateDiff import AnimateDiffModel, AnimateDiffTextToVideo

config = SSUIConfig()


@workflow
def txt2vid_animatediff(prompt: Prompt, negative_prompt: Prompt) -> Video:
    model = None
    if not config.is_prepare():
        model = AnimateDiffModel.load_local()
    frames = AnimateDiffTextToVideo(config("Generate Video"), model, prompt, negative_prompt)
    return Video("mp4", frames, fps=4)
