from backend.lora import validate_lora, apply_manager_lora
from ssui.model_memory import ModelMemoryOptions, configure_diffsynth_manager, run_pipeline
import os
from pathlib import Path
from diffsynth import (
    ModelManager,
    SDImagePipeline,
    SDVideoPipeline,
    save_video,
    download_models,
)
import torch
import PIL.Image
from backend.util.devices import TorchDevice
from backend.quantization.workflow import int8_quantizer, quantize_manager_components
from ssui.annotation import param
from ssui.base import Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider


class AnimateDiffModel:
    def __init__(
        self,
        checkpoint_path: str = "",
        motion_path: str = "",
        quantization: str = "none",
        lora_path: str = "",
        lora_weight: float = 1.0,
        *, cpu_offload: bool = False,
    ):
        validate_lora(lora_path, lora_weight)
        options = ModelMemoryOptions(quantization, cpu_offload)
        quantize = int8_quantizer(quantization)
        if bool(checkpoint_path) != bool(motion_path):
            raise ValueError("Provide both checkpoint_path and motion_path, or neither")
        if not checkpoint_path:
            download_models(["DreamShaper_8", "AnimateDiff_v2"])
            checkpoint_path = "models/stable_diffusion/dreamshaper_8.safetensors"
            motion_path = "models/AnimateDiff/mm_sd_v15_v2.ckpt"

        # Load models
        device = TorchDevice.choose_torch_device()
        self.model_manager = ModelManager(
            torch_dtype=TorchDevice.choose_torch_dtype(device), device="cpu" if quantization != "none" or cpu_offload else str(device)
        )
        self.model_manager.load_models(
            [
                checkpoint_path,
                motion_path,
            ]
        )

        apply_manager_lora(self.model_manager, lora_path, lora_weight)
        if quantization != "none":
            quantize_manager_components(self.model_manager, quantize, ("sd_unet", "sd_text_encoder"))
        configure_diffsynth_manager(self.model_manager, options, str(device), quantize=False)

    @staticmethod
    def load(checkpoint_path: str = "", motion_path: str = "", quantization: str = "none",
             lora_path: str = "", lora_weight: float = 1.0, *, cpu_offload: bool = False) -> "AnimateDiffModel":
        return AnimateDiffModel(checkpoint_path, motion_path, quantization, lora_path, lora_weight, cpu_offload=cpu_offload)

    @staticmethod
    def load_local(quantization: str = "none", lora_path: str = "", lora_weight: float = 1.0, *, cpu_offload: bool = False) -> "AnimateDiffModel":
        """Load the verified local weights used by the Mac example workflow."""
        root = Path(__file__).resolve().parents[3] / "models/video-smoke"
        checkpoint = Path(os.environ.get("SSUI_ANIMATEDIFF_CHECKPOINT", root / "sd1/dreamshaper_8.safetensors"))
        motion = Path(os.environ.get("SSUI_ANIMATEDIFF_MOTION", root / "animatediff/mm_sd_v15_v2.ckpt"))
        if not checkpoint.is_file() or not motion.is_file():
            raise FileNotFoundError("Download AnimateDiff weights first: yarn test:video:smoke --download-only")
        return AnimateDiffModel(str(checkpoint), str(motion), quantization=quantization, lora_path=lora_path, lora_weight=lora_weight, cpu_offload=cpu_offload)


@param("width", Slider(64, 1024, 64), default=256)
@param("height", Slider(64, 1024, 64), default=256)
@param("num_frames", Slider(2, 128, 1), default=8)
@param("cfg_scale", Slider(1, 20, 1), default=7.5)
@param("num_inference_steps", Slider(2, 100, 1), default=20)
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
    if getattr(base_model.model_manager, "memory_options", ModelMemoryOptions()).cpu_offload:
        pipe_image.enable_cpu_offload()
    image = run_pipeline(pipe_image,
        prompt=prompt.text,
        seed=config["seed"],
        negative_prompt=negative_prompt.text,
        cfg_scale=config["cfg_scale"],
        num_inference_steps=config["num_inference_steps"],
        height=config["height"],
        width=config["width"],
    )

    # Text + Image -> Video (6GB VRAM is enough!)
    pipe = SDVideoPipeline.from_model_manager(base_model.model_manager)
    if getattr(base_model.model_manager, "memory_options", ModelMemoryOptions()).cpu_offload:
        pipe.enable_cpu_offload()
    output_video = run_pipeline(pipe,
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
