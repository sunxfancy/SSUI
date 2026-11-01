"""Local Wan 2.1 T2V-1.3B with all weights resident on a 24 GB GPU."""
from pathlib import Path
import torch
from ssui.annotation import param
from ssui.base import Image, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider


class Wan21Model:
    def __init__(self, pipeline=None):
        self.pipeline = pipeline

    @staticmethod
    def load(model_path: str) -> 'Wan21Model':
        from diffsynth import ModelManager, WanVideoPipeline
        root = Path(model_path)
        files = [root / 'diffusion_pytorch_model.safetensors',
                 root / 'models_t5_umt5-xxl-enc-bf16.pth', root / 'Wan2.1_VAE.pth']
        if not all(path.is_file() for path in files):
            raise ValueError('Wan2.1 T2V directory must contain DiT, UMT5 and VAE weights')
        manager = ModelManager(torch_dtype=torch.bfloat16, device='cuda')
        manager.load_models([str(path) for path in files])
        # Keeping these models resident avoids copying the 11 GB UMT5 model
        # back to a small host during transitions between pipeline stages.
        return Wan21Model(WanVideoPipeline.from_model_manager(manager))


@param('width', Slider(128, 832, 16), default=256)
@param('height', Slider(128, 832, 16), default=256)
@param('num_frames', Slider(5, 81, 4), default=17)
@param('num_inference_steps', Slider(1, 100, 1), default=12)
@param('seed', Random(), default=42)
def Wan21TextToVideo(config: SSUIConfig, model: Wan21Model,
                     prompt: Prompt, negative_prompt: Prompt) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    frames = int(config['num_frames'])
    if frames < 5 or (frames - 1) % 4:
        raise ValueError('Wan frame count must be 4n+1, at least 5')
    result = model.pipeline(prompt=prompt.text, negative_prompt=negative_prompt.text,
                            height=config['height'], width=config['width'],
                            num_frames=frames, num_inference_steps=config['num_inference_steps'],
                            seed=config['seed'], tiled=True)
    return [Image(frame) for frame in result]
