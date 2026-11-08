import torch

from backend.contracts.media import Prompt, Image
from backend.contracts.services import InferenceConfig as SSUIConfig
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
