import torch

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider

torch.cuda.set_per_process_memory_fraction(1.0, 0)
from diffsynth import (
    ModelManager,
    HunyuanVideoPipeline,
    download_models,
    FlowMatchScheduler,
    download_customized_models,
)


class HunyuanVideoModel:
    def __init__(self, model_manager: ModelManager = None):
        self.model_manager = model_manager

    @staticmethod
    def load() -> "HunyuanVideoModel":
        model_manager = ModelManager()
        download_models(["HunyuanVideo"])

        # The DiT model is loaded in bfloat16.
        model_manager.load_models(
            ["models/HunyuanVideo/transformers/mp_rank_00_model_states.pt"],
            torch_dtype=torch.bfloat16,  # you can use torch_dtype=torch.float8_e4m3fn to enable quantization.
            device="cpu",
        )

        # The other modules are loaded in float16.
        model_manager.load_models(
            [
                "models/HunyuanVideo/text_encoder/model.safetensors",
                "models/HunyuanVideo/text_encoder_2",
                "models/HunyuanVideo/vae/pytorch_model.pt",
            ],
            torch_dtype=torch.float16,
            device="cpu",
        )
        return HunyuanVideoModel(model_manager)


class HunyuanVideoLoraModel:
    def __init__(
        self,
        base_model: HunyuanVideoModel,
        model_id: str = "AI-ModelScope/walking_animation_hunyuan_video",
        origin_file_path: str = "kxsr_walking_anim_v1-5.safetensors",
    ):
        # We support LoRA inference. You can use the following code to load your LoRA model.
        # Example LoRA: https://civitai.com/models/1032126/walking-animation-hunyuan-video
        download_customized_models(
            model_id=model_id,
            origin_file_path=origin_file_path,
            local_dir="models/lora",
        )[0]
        base_model.model_manager.load_lora(
            "models/lora/" + origin_file_path, lora_alpha=1.0
        )


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 500, 1), default=129)
@param("num_inference_steps", Slider(1, 50, 1), default=18)
@param("height", Slider(1, 1000, 1), default=512)
@param("width", Slider(1, 1000, 1), default=384)
def HunyuanTextToVideo(
    config: SSUIConfig, base_model: HunyuanVideoModel, prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    # The computation device is "cuda".
    pipe = HunyuanVideoPipeline.from_model_manager(
        base_model.model_manager, torch_dtype=torch.bfloat16, device="cuda"
    )
    # This LoRA requires shift=9.0.
    pipe.scheduler = FlowMatchScheduler(shift=9.0, sigma_min=0.0, extra_one_step=True)
    video = pipe(
        prompt=prompt.text,
        seed=config["seed"],
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        tile_size=(17, 16, 16),
        tile_stride=(12, 12, 12),
    )
    return [Image(image) for image in video]
