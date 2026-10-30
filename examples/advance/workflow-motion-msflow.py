from ssui import MotionClip, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_motion.OtherModels import GenerateMSFlowMotion

config = SSUIConfig()


@workflow
def txt2motion_msflow(prompt: Prompt) -> MotionClip:
    """Generate and preview 3D motion with MotionSpaceFlow XYZ."""
    return GenerateMSFlowMotion(config('MotionSpaceFlow Text To Motion'), prompt)
