from ssui import MotionClip, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_motion.Ardy import GenerateArdyMotion

config = SSUIConfig()


@workflow
def txt2motion_ardy(prompt: Prompt) -> MotionClip:
    """Generate and preview skeletal motion with NVIDIA ARDY."""
    return GenerateArdyMotion(config('ARDY Text To Motion'), prompt)
