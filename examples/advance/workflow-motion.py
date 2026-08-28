from ssui import Prompt, workflow
from ssui.config import SSUIConfig
from ssui_motion.Kimodo import KimodoTextToMotion


config = SSUIConfig()


@workflow
def txt2motion_kimodo(prompt: Prompt) -> str:
    """Generate 3D human or robot motion with NVIDIA Kimodo on Windows AMDGPU."""
    return KimodoTextToMotion(config("Kimodo Text To Motion"), prompt)
