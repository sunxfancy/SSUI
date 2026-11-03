from ssui.model_memory import ModelMemoryOptions, configure_diffsynth_manager, run_pipeline
from backend.quantization.workflow import int8_quantizer, quantize_manager_components
from ._runtime import wan_runtime

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
    def load(quantization: str = "none", *, cpu_offload: bool | None = None) -> "CogVideoModel":
        quantize = int8_quantizer(quantization)
        runtime = wan_runtime()
        device = runtime["device"]
        options = ModelMemoryOptions(quantization, device == "mps" if cpu_offload is None else cpu_offload)
        model_manager = ModelManager(
            torch_dtype=runtime["torch_dtype"],
            device="cpu" if options.cpu_offload or quantization != "none" else device,
        )
        download_models(["CogVideoX-5B"])
        model_manager.load_models(
            [
                "models/CogVideo/CogVideoX-5b/transformer",
                "models/CogVideo/CogVideoX-5b/text_encoder",
                "models/CogVideo/CogVideoX-5b/vae/diffusion_pytorch_model.safetensors",
            ],
        )
        if quantization != "none":
            quantize_manager_components(model_manager, quantize, ("cog_dit", "flux_text_encoder_2"))
        configure_diffsynth_manager(model_manager, options, str(device), quantize=False)
        return CogVideoModel(model_manager)


@param("seed", Random(), default=42)
@param("num_frames", Slider(9, 201, 8), default=49)
@param("num_inference_steps", Slider(1, 50, 1), default=20)
@param("height", Slider(16, 1024, 16), default=480)
@param("width", Slider(16, 1024, 16), default=720)
def CogVideoTextToVideo(
    config: SSUIConfig, base_model: CogVideoModel, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]

    if config["num_frames"] < 9 or config["num_frames"] % 8 != 1:
        raise ValueError("CogVideo requires 8n+1 frames, at least 9, for causal VAE decoding")
    pipe = CogVideoPipeline.from_model_manager(base_model.model_manager, **wan_runtime())
    options = getattr(base_model.model_manager, "memory_options", ModelMemoryOptions(cpu_offload=True))
    if options.cpu_offload:
        if options.quantization == "int8":
            pipe.enable_cpu_offload()
        else:
            pipe.enable_vram_management()
    video = run_pipeline(pipe,
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
