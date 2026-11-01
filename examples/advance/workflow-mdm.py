from ssui import workflow, Prompt, Video
from ssui.config import SSUIConfig
from ssui_motion.MDM import MDMModel, MDMTextToMotion

config = SSUIConfig()


@workflow
def text_to_motion(model: MDMModel, prompt: Prompt) -> Video:
    """Generate HumanML joint trajectories, retain motion.npz, and show preview."""
    motion = MDMTextToMotion(config('Generate motion'), model, prompt)
    if config.is_prepare():
        return Video('mp4', [], fps=20)
    return motion.preview()
