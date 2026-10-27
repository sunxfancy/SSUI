from ssui import MotionClip, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_motion.Kimodo import GenerateKimodoMotion


config = SSUIConfig()


@workflow
def txt2motion_kimodo(prompt: Prompt) -> MotionClip:
    """Generate and preview 3D human or robot motion with NVIDIA Kimodo."""
    return GenerateKimodoMotion(config("Kimodo Text To Motion"), prompt)
