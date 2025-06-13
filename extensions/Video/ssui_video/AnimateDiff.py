from diffsynth import (
    ModelManager,
    SDImagePipeline,
    SDVideoPipeline,
    save_video,
    download_models,
)
import torch
import PIL.Image
from ssui.annotation import param
from ssui.base import Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider


class AnimateDiffModel:
    def __init__(self):
        download_models(["DreamShaper_8", "AnimateDiff_v2"])

        # Load models
        self.model_manager = ModelManager(torch_dtype=torch.float16, device="cuda")
        self.model_manager.load_models(
            [
                "models/stable_diffusion/dreamshaper_8.safetensors",
                "models/AnimateDiff/mm_sd_v15_v2.ckpt",
            ]
        )


@param("width", Slider(1, 1000, 1), default=768)
@param("height", Slider(1, 1000, 1), default=512)
@param("num_frames", Slider(1, 1000, 1), default=64)
@param("cfg_scale", Slider(1, 20, 1), default=7.5)
@param("num_inference_steps", Slider(1, 100, 1), default=30)
@param("seed", Random(), default=42)
@param("denoising_strength", Slider(0, 1, 0.01), default=0.9)
def AnimateDiffTextToVideo(
    config: SSUIConfig,
    base_model: AnimateDiffModel,
    prompt: Prompt,
    negative_prompt: Prompt,
) -> list[PIL.Image.Image]:
    if config.is_prepare():
        return []

    # Text -> Image
    pipe_image = SDImagePipeline.from_model_manager(base_model.model_manager)
    torch.manual_seed(0)
    image = pipe_image(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text,
        cfg_scale=config["cfg_scale"],
        num_inference_steps=config["num_inference_steps"],
        height=config["height"],
        width=config["width"],
    )

    # Text + Image -> Video (6GB VRAM is enough!)
    pipe = SDVideoPipeline.from_model_manager(base_model.model_manager)
    output_video = pipe(
        prompt=prompt.text,
        seed=config["seed"],
        negative_prompt=negative_prompt.text,
        cfg_scale=config["cfg_scale"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        height=config["height"],
        width=config["width"],
        animatediff_batch_size=16,
        animatediff_stride=1,
        input_frames=[image] * config["num_frames"],
        denoising_strength=config["denoising_strength"],
    )

    return output_video
