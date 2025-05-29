import torch
from diffsynth import ModelManager, WanVideoPipeline
from modelscope import snapshot_download


from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch

class WanVideoModel:
    def __init__(self):
        self.model_manager = ModelManager()
        snapshot_download("PAI/Wan2.1-Fun-1.3B-InP", local_dir="models/PAI/Wan2.1-Fun-1.3B-InP")

        # Load models
        self.model_manager.load_models(
            [
                "models/PAI/Wan2.1-Fun-1.3B-InP/diffusion_pytorch_model.safetensors",
                "models/PAI/Wan2.1-Fun-1.3B-InP/models_t5_umt5-xxl-enc-bf16.pth",
                "models/PAI/Wan2.1-Fun-1.3B-InP/Wan2.1_VAE.pth",
                "models/PAI/Wan2.1-Fun-1.3B-InP/models_clip_open-clip-xlm-roberta-large-vit-huge-14.pth",
            ],
            torch_dtype=torch.bfloat16, # You can set `torch_dtype=torch.float8_e4m3fn` to enable FP8 quantization.
        )

@param("seed", Random(), default=42)
@param("tiled", Switch(default=True))
@param("num_frames", Slider(1, 200, 1), default=50)
def WanImageTextToVideo(config: SSUIConfig, base_model: WanVideoModel, image: Image, prompt: Prompt, negative_prompt: Prompt) -> list[Image]:
    pipe = WanVideoPipeline.from_model_manager(base_model.model_manager, torch_dtype=torch.bfloat16, device="cuda")
    pipe.enable_vram_management(num_persistent_param_in_dit=None)

    # Image-to-video
    video = pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text,
        num_inference_steps=config["num_frames"],
        input_image=image._image,
        # You can input `end_image=xxx` to control the last frame of the video.
        # The model will automatically generate the dynamic content between `input_image` and `end_image`.
        seed=config["seed"], tiled=config["tiled"]  
    )

    return [Image(image) for image in video]