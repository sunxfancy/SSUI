from ssui import MotionClip, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_motion.OtherModels import GenerateHYMotion

config = SSUIConfig()


@workflow
def txt2motion_hy(prompt: Prompt) -> MotionClip:
    """Generate and preview 3D motion with Tencent HY-Motion Lite."""
    return GenerateHYMotion(config('HY-Motion Text To Motion'), prompt)
