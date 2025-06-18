from ssui import workflow, Voice, Prompt
from ssui.config import SSUIConfig
from ssui_video.Wan import WanVideoModel, WanImageTextToVideo
config = SSUIConfig()


@workflow
def img2voice(text: Prompt) -> Voice:
    if config.is_prepare():
        model = WanVideoModel()
    else:
        model = WanVideoModel.load()
    
