import torch

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider
from diffsynth import ModelManager, CogVideoPipeline, download_models


class CogVideoModel:
    """智谱 CogVideoX-5B 文生视频模型（开源、5B 参数，显存要求相对较低）。"""

    def __init__(self, model_manager: ModelManager = None):
        self.model_manager = model_manager

    @staticmethod
    def load() -> "CogVideoModel":
        model_manager = ModelManager()
        download_models(["CogVideoX-5B"])
        model_manager.load_models(
            [
                "models/CogVideo/CogVideoX-5b/transformer",
                "models/CogVideo/CogVideoX-5b/text_encoder",
                "models/CogVideo/CogVideoX-5b/vae/diffusion_pytorch_model.safetensors",
            ],
            torch_dtype=torch.float16,
            device="cuda",
        )
        return CogVideoModel(model_manager)


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 200, 1), default=49)
@param("num_inference_steps", Slider(1, 50, 1), default=20)
@param("height", Slider(16, 1024, 16), default=480)
@param("width", Slider(16, 1024, 16), default=720)
def CogVideoTextToVideo(
    config: SSUIConfig, base_model: CogVideoModel, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]

    pipe = CogVideoPipeline.from_model_manager(base_model.model_manager)
    video = pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text,
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        seed=config["seed"],
        tiled=True,
    )
    return [Image(image) for image in video]
