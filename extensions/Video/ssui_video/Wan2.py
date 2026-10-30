from ._runtime import wan_runtime
import torch
from backend.quantization.workflow import fp8_storage_dtype, load_dit_with_storage_dtype

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch
from diffsynth import ModelManager, WanVideoPipeline
from modelscope import snapshot_download


# Wan 2.1 旗舰版 (14B) 本地节点。
# 相比仓库原有的 Wan2.1-Fun-1.3B，14B 在动作质量、语义跟随与细节上明显更强，
# 是当前 vendored diffsynth 能直接跑的最高质量开源视频模型之一。
# 显存建议：24GB+ 显卡（DiT 在 CPU 侧加载，配合显存管理按需换入）；
# load(quantization="fp8") 只压缩 DiT 存储，计算精度由运行时选择。
WAN2_T2V_MODEL_ID = "Wan-AI/Wan2.1-T2V-14B"
WAN2_T2V_LIGHT_MODEL_ID = "Wan-AI/Wan2.1-T2V-1.3B"  # 共享 UMT5 文本编码器与 VAE
WAN2_I2V_MODEL_ID = "Wan-AI/Wan2.1-I2V-14B-720P"
WAN2_I2V_CLIP_MODEL_ID = "Wan-AI/Wan2.1-I2V-14B-480P"  # 共享 CLIP 图像编码器


class Wan2T2VModel:
    """Wan 2.1 T2V-14B 文生视频模型。"""

    def __init__(self, model_manager: ModelManager = None):
        self.model_manager = model_manager

    @staticmethod
    def load(quantization: str = "none") -> "Wan2T2VModel":
        runtime = wan_runtime()
        fp8_storage_dtype(quantization, runtime["torch_dtype"], device=runtime["device"])
        model_manager = ModelManager(device="cpu", torch_dtype=runtime["torch_dtype"])
        snapshot_download(WAN2_T2V_MODEL_ID, local_dir="models/" + WAN2_T2V_MODEL_ID)
        snapshot_download(WAN2_T2V_LIGHT_MODEL_ID, local_dir="models/" + WAN2_T2V_LIGHT_MODEL_ID)
        load_dit_with_storage_dtype(
            model_manager,
            [
                "models/" + WAN2_T2V_MODEL_ID + "/diffusion_pytorch_model.safetensors",
                "models/" + WAN2_T2V_LIGHT_MODEL_ID + "/models_t5_umt5-xxl-enc-bf16.pth",
                "models/" + WAN2_T2V_LIGHT_MODEL_ID + "/Wan2.1_VAE.pth",
            ],
            quantization=quantization,
            torch_dtype=runtime["torch_dtype"],
            device="cpu",
        )
        return Wan2T2VModel(model_manager)


class Wan2I2VModel:
    """Wan 2.1 I2V-14B-720P 图生视频模型（支持首尾帧控制）。"""

    def __init__(self, model_manager: ModelManager = None):
        self.model_manager = model_manager

    @staticmethod
    def load(quantization: str = "none") -> "Wan2I2VModel":
        runtime = wan_runtime()
        fp8_storage_dtype(quantization, runtime["torch_dtype"], device=runtime["device"])
        model_manager = ModelManager(device="cpu", torch_dtype=runtime["torch_dtype"])
        snapshot_download(WAN2_I2V_MODEL_ID, local_dir="models/" + WAN2_I2V_MODEL_ID)
        snapshot_download(WAN2_T2V_LIGHT_MODEL_ID, local_dir="models/" + WAN2_T2V_LIGHT_MODEL_ID)
        snapshot_download(WAN2_I2V_CLIP_MODEL_ID, local_dir="models/" + WAN2_I2V_CLIP_MODEL_ID)
        load_dit_with_storage_dtype(
            model_manager,
            [
                "models/" + WAN2_I2V_MODEL_ID + "/diffusion_pytorch_model.safetensors",
                "models/" + WAN2_T2V_LIGHT_MODEL_ID + "/models_t5_umt5-xxl-enc-bf16.pth",
                "models/" + WAN2_T2V_LIGHT_MODEL_ID + "/Wan2.1_VAE.pth",
                "models/" + WAN2_I2V_CLIP_MODEL_ID + "/models_clip_open-clip-xlm-roberta-large-vit-huge-14.pth",
            ],
            quantization=quantization,
            torch_dtype=runtime["torch_dtype"],
            device="cpu",
        )
        return Wan2I2VModel(model_manager)


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 200, 1), default=81)
@param("num_inference_steps", Slider(1, 100, 1), default=50)
@param("cfg_scale", Slider(1, 10, 0.1), default=5)
@param("height", Slider(16, 1280, 16), default=480)
@param("width", Slider(16, 1280, 16), default=832)
@param("tiled", Switch(), default=True)
def Wan2TextToVideo(
    config: SSUIConfig, base_model: Wan2T2VModel, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]

    pipe = WanVideoPipeline.from_model_manager(
        base_model.model_manager, **wan_runtime()
    )
    pipe.enable_vram_management(num_persistent_param_in_dit=0)
    video = pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text,
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        cfg_scale=config["cfg_scale"],
        seed=config["seed"],
        tiled=config["tiled"],
    )
    return [Image(image) for image in video]


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 200, 1), default=81)
@param("num_inference_steps", Slider(1, 100, 1), default=50)
@param("height", Slider(16, 1280, 16), default=480)
@param("width", Slider(16, 1280, 16), default=832)
@param("tiled", Switch(), default=True)
def Wan2ImageToVideo(
    config: SSUIConfig,
    base_model: Wan2I2VModel,
    image: Image,
    prompt: Prompt,
    negative_prompt: Prompt,
    end_image: Image = None,
) -> list[Image]:
    if config.is_prepare():
        return [Image()]

    pipe = WanVideoPipeline.from_model_manager(
        base_model.model_manager, **wan_runtime()
    )
    pipe.enable_vram_management(num_persistent_param_in_dit=0)
    video = pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text,
        input_image=image._image,
        end_image=end_image._image if end_image is not None else None,
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        seed=config["seed"],
        tiled=config["tiled"],
    )
    return [Image(image) for image in video]
