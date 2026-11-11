from backend.lora import validate_lora, apply_manager_lora
from ssui.model_memory import ModelMemoryOptions, configure_diffsynth_manager, run_pipeline
import torch
from backend.quantization.workflow import fp8_storage_dtype
from ._runtime import wan_runtime

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider

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
    def load(quantization: str = "none", lora_path: str = "", lora_weight: float = 1.0, *, cpu_offload: bool = True) -> "HunyuanVideoModel":
        validate_lora(lora_path, lora_weight)
        options = ModelMemoryOptions(quantization, cpu_offload, allow_fp8=True)
        runtime = wan_runtime()
        storage_dtype = fp8_storage_dtype("none" if quantization == "int8" else quantization, runtime["torch_dtype"], device=runtime["device"])
        model_manager = ModelManager(device="cpu", torch_dtype=runtime["torch_dtype"])
        download_models(["HunyuanVideo"])

        # Stage weights on CPU; the pipeline computes on the selected accelerator.
        model_manager.load_models(
            ["models/HunyuanVideo/transformers/mp_rank_00_model_states.pt"],
            torch_dtype=storage_dtype,
            device="cpu",
        )

        # Preserve CUDA checkpoint precision; MPS uses its safe runtime dtype.
        model_manager.load_models(
            [
                "models/HunyuanVideo/text_encoder/model.safetensors",
                "models/HunyuanVideo/text_encoder_2",
                "models/HunyuanVideo/vae/pytorch_model.pt",
            ],
            torch_dtype=torch.float16 if runtime["device"].startswith("cuda") else runtime["torch_dtype"],
            device="cpu",
        )
        apply_manager_lora(model_manager, lora_path, lora_weight)
        configure_diffsynth_manager(model_manager, options, runtime["device"])
        return HunyuanVideoModel(model_manager)


class HunyuanVideoLoraModel:
    def __init__(
        self,
        base_model: HunyuanVideoModel,
        model_id: str = "AI-ModelScope/walking_animation_hunyuan_video",
        origin_file_path: str = "kxsr_walking_anim_v1-5.safetensors",
        lora_path: str = "",
        lora_weight: float = 1.0,
    ):
        self.model_manager = base_model.model_manager
        if not lora_path and lora_weight != 0:
            import math
            if not math.isfinite(lora_weight):
                raise ValueError("LoRA weight must be finite")
            download_customized_models(
                model_id=model_id, origin_file_path=origin_file_path,
                local_dir="models/lora",
            )
            lora_path = "models/lora/" + origin_file_path
        apply_manager_lora(self.model_manager, lora_path, lora_weight)



class HunyuanImageToVideoModel:
    """HunyuanVideo I2V-720p 图生视频模型。"""

    def __init__(self, model_manager: ModelManager = None):
        self.model_manager = model_manager

    @staticmethod
    def load(quantization: str = "none", lora_path: str = "", lora_weight: float = 1.0, *, cpu_offload: bool = True) -> "HunyuanImageToVideoModel":
        validate_lora(lora_path, lora_weight)
        options = ModelMemoryOptions(quantization, cpu_offload, allow_fp8=True)
        runtime = wan_runtime()
        storage_dtype = fp8_storage_dtype("none" if quantization == "int8" else quantization, runtime["torch_dtype"], device=runtime["device"])
        model_manager = ModelManager(device="cpu", torch_dtype=runtime["torch_dtype"])
        download_models(["HunyuanVideoI2V"])

        model_manager.load_models(
            ["models/HunyuanVideoI2V/transformers/mp_rank_00_model_states.pt"],
            torch_dtype=storage_dtype,
            device="cpu",
        )
        model_manager.load_models(
            [
                "models/HunyuanVideoI2V/text_encoder/model.safetensors",
                "models/HunyuanVideoI2V/text_encoder_2",
                "models/HunyuanVideoI2V/vae/pytorch_model.pt",
            ],
            torch_dtype=torch.float16 if runtime["device"].startswith("cuda") else runtime["torch_dtype"],
            device="cpu",
        )
        apply_manager_lora(model_manager, lora_path, lora_weight)
        configure_diffsynth_manager(model_manager, options, runtime["device"])
        return HunyuanImageToVideoModel(model_manager)


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
    pipe = HunyuanVideoPipeline.from_model_manager(
        base_model.model_manager, **wan_runtime(), enable_vram_management=False
    )
    # This LoRA requires shift=9.0.
    pipe.scheduler = FlowMatchScheduler(shift=9.0, sigma_min=0.0, extra_one_step=True)
    options = getattr(base_model.model_manager, "memory_options", ModelMemoryOptions(cpu_offload=True))
    if options.cpu_offload:
        if options.quantization == "int8":
            pipe.enable_cpu_offload()
        else:
            pipe.enable_vram_management()
    video = run_pipeline(pipe,
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


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 500, 1), default=129)
@param("num_inference_steps", Slider(1, 50, 1), default=24)
@param("height", Slider(1, 1000, 1), default=720)
@param("width", Slider(1, 1000, 1), default=1280)
def HunyuanImageToVideo(
    config: SSUIConfig, base_model: HunyuanImageToVideoModel, image: Image, prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    pipe = HunyuanVideoPipeline.from_model_manager(
        base_model.model_manager, **wan_runtime(), enable_vram_management=False
    )
    options = getattr(base_model.model_manager, "memory_options", ModelMemoryOptions(cpu_offload=True))
    if options.cpu_offload:
        if options.quantization == "int8":
            pipe.enable_cpu_offload()
        else:
            pipe.enable_vram_management()
    video = run_pipeline(pipe,
        prompt=prompt.text,
        input_images=[image._image],
        i2v_resolution="720p",
        seed=config["seed"],
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        tile_size=(17, 16, 16),
        tile_stride=(12, 12, 12),
    )
    return [Image(image) for image in video]
