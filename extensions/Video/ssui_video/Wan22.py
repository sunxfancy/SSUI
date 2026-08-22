import os

import torch

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch
from diffsynth.pipelines.wan_video_new import WanVideoPipeline
from diffsynth.utils import ModelConfig


# Wan 2.2 本地节点（依赖已升级的 vendored diffsynth 1.1.9）。
# Wan 2.2 是目前 diffsynth 能支持到的最新 Wan 系列：
#   - TI2V-5B：文生视频 / 图生视频 / 首尾帧 一体化，5B 参数量，24GB 显存可跑；
#   - T2V-A14B / I2V-A14B：MoE 双专家（high_noise + low_noise）14B 级，质量更接近 Seedance，
#     建议 48GB+ 显存，24GB 需配合 FP8（把下面 torch_dtype 改为 torch.float8_e4m3fn）。
# 权重通过 ModelScope 下载（可在环境变量中覆盖本地根目录）。
WAN22_TI2V_MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B"
WAN22_T2V_MODEL_ID = "Wan-AI/Wan2.2-T2V-A14B"
WAN22_I2V_MODEL_ID = "Wan-AI/Wan2.2-I2V-A14B"
# Wan2.2 与 Wan2.1 共享 UMT5-XXL 文本编码器、tokenizer 和 VAE（1.1.9 会自动重定向下载）
WAN21_T2V_LIGHT_MODEL_ID = "Wan-AI/Wan2.1-T2V-1.3B"

LOCAL_MODEL_PATH = os.environ.get("SSUI_WAN_MODEL_ROOT", "models")

# 官方推荐的负面提示词（Wan 官方示例原样）
WAN22_NEGATIVE_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，"
    "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
    "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
    "杂乱的背景，三条腿，背景人很多，倒着走"
)


class Wan22TI2VModel:
    """Wan 2.2 TI2V-5B 模型（文生 / 图生 / 首尾帧一体）。"""

    def __init__(self, pipe: WanVideoPipeline = None):
        self.pipe = pipe

    @staticmethod
    def load() -> "Wan22TI2VModel":
        pipe = WanVideoPipeline.from_pretrained(
            torch_dtype=torch.bfloat16,  # 可改为 torch.float8_e4m3fn 启用 FP8 量化
            device="cuda",
            model_configs=[
                ModelConfig(
                    model_id=WAN22_TI2V_MODEL_ID,
                    origin_file_pattern="models_t5_umt5-xxl-enc-bf16.pth",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_TI2V_MODEL_ID,
                    origin_file_pattern="diffusion_pytorch_model*.safetensors",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_TI2V_MODEL_ID,
                    origin_file_pattern="Wan2.2_VAE.pth",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
            ],
            tokenizer_config=ModelConfig(
                model_id=WAN21_T2V_LIGHT_MODEL_ID,
                origin_file_pattern="google/umt5-xxl/",
                local_model_path=LOCAL_MODEL_PATH,
            ),
        )
        pipe.enable_vram_management(num_persistent_param_in_dit=None)
        return Wan22TI2VModel(pipe)


class Wan22T2VA14BModel:
    """Wan 2.2 T2V-A14B 文生视频模型（MoE 双专家）。"""

    def __init__(self, pipe: WanVideoPipeline = None):
        self.pipe = pipe

    @staticmethod
    def load() -> "Wan22T2VA14BModel":
        pipe = WanVideoPipeline.from_pretrained(
            torch_dtype=torch.bfloat16,
            device="cuda",
            model_configs=[
                ModelConfig(
                    model_id=WAN22_T2V_MODEL_ID,
                    origin_file_pattern="high_noise_model/diffusion_pytorch_model*.safetensors",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_T2V_MODEL_ID,
                    origin_file_pattern="low_noise_model/diffusion_pytorch_model*.safetensors",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_T2V_MODEL_ID,
                    origin_file_pattern="models_t5_umt5-xxl-enc-bf16.pth",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_T2V_MODEL_ID,
                    origin_file_pattern="Wan2.1_VAE.pth",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
            ],
            tokenizer_config=ModelConfig(
                model_id=WAN21_T2V_LIGHT_MODEL_ID,
                origin_file_pattern="google/umt5-xxl/",
                local_model_path=LOCAL_MODEL_PATH,
            ),
        )
        pipe.enable_vram_management(num_persistent_param_in_dit=None)
        return Wan22T2VA14BModel(pipe)


class Wan22I2VA14BModel:
    """Wan 2.2 I2V-A14B 图生视频模型（MoE 双专家，支持首尾帧）。"""

    def __init__(self, pipe: WanVideoPipeline = None):
        self.pipe = pipe

    @staticmethod
    def load() -> "Wan22I2VA14BModel":
        pipe = WanVideoPipeline.from_pretrained(
            torch_dtype=torch.bfloat16,
            device="cuda",
            model_configs=[
                ModelConfig(
                    model_id=WAN22_I2V_MODEL_ID,
                    origin_file_pattern="high_noise_model/diffusion_pytorch_model*.safetensors",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_I2V_MODEL_ID,
                    origin_file_pattern="low_noise_model/diffusion_pytorch_model*.safetensors",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_I2V_MODEL_ID,
                    origin_file_pattern="models_t5_umt5-xxl-enc-bf16.pth",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
                ModelConfig(
                    model_id=WAN22_I2V_MODEL_ID,
                    origin_file_pattern="Wan2.1_VAE.pth",
                    offload_device="cpu",
                    local_model_path=LOCAL_MODEL_PATH,
                ),
            ],
            tokenizer_config=ModelConfig(
                model_id=WAN21_T2V_LIGHT_MODEL_ID,
                origin_file_pattern="google/umt5-xxl/",
                local_model_path=LOCAL_MODEL_PATH,
            ),
        )
        pipe.enable_vram_management(num_persistent_param_in_dit=None)
        return Wan22I2VA14BModel(pipe)


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 300, 1), default=81)
@param("num_inference_steps", Slider(1, 100, 1), default=50)
@param("height", Slider(16, 1280, 16), default=480)
@param("width", Slider(16, 1280, 16), default=832)
@param("tiled", Switch(), default=True)
def Wan22TextToVideo(
    config: SSUIConfig, base_model: Wan22TI2VModel, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    video = base_model.pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text if negative_prompt.text else WAN22_NEGATIVE_PROMPT,
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        seed=config["seed"],
        tiled=config["tiled"],
    )
    return [Image(image) for image in video]


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 300, 1), default=81)
@param("num_inference_steps", Slider(1, 100, 1), default=50)
@param("height", Slider(16, 1280, 16), default=480)
@param("width", Slider(16, 1280, 16), default=832)
@param("tiled", Switch(), default=True)
def Wan22ImageToVideo(
    config: SSUIConfig,
    base_model: Wan22TI2VModel,
    image: Image,
    prompt: Prompt,
    negative_prompt: Prompt,
    end_image: Image = None,
) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    video = base_model.pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text if negative_prompt.text else WAN22_NEGATIVE_PROMPT,
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


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 300, 1), default=81)
@param("num_inference_steps", Slider(1, 100, 1), default=50)
@param("height", Slider(16, 1280, 16), default=480)
@param("width", Slider(16, 1280, 16), default=832)
@param("switch_diT_boundary", Slider(0, 1, 0.05), default=0.875)
@param("tiled", Switch(), default=True)
def Wan22T2VA14BTextToVideo(
    config: SSUIConfig, base_model: Wan22T2VA14BModel, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    video = base_model.pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text if negative_prompt.text else WAN22_NEGATIVE_PROMPT,
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        switch_DiT_boundary=config["switch_diT_boundary"],
        seed=config["seed"],
        tiled=config["tiled"],
    )
    return [Image(image) for image in video]


@param("seed", Random(), default=42)
@param("num_frames", Slider(1, 300, 1), default=81)
@param("num_inference_steps", Slider(1, 100, 1), default=50)
@param("height", Slider(16, 1280, 16), default=480)
@param("width", Slider(16, 1280, 16), default=832)
@param("switch_diT_boundary", Slider(0, 1, 0.05), default=0.9)
@param("tiled", Switch(), default=True)
def Wan22I2VA14BImageToVideo(
    config: SSUIConfig,
    base_model: Wan22I2VA14BModel,
    image: Image,
    prompt: Prompt,
    negative_prompt: Prompt,
    end_image: Image = None,
) -> list[Image]:
    if config.is_prepare():
        return [Image()]
    video = base_model.pipe(
        prompt=prompt.text,
        negative_prompt=negative_prompt.text if negative_prompt.text else WAN22_NEGATIVE_PROMPT,
        input_image=image._image,
        end_image=end_image._image if end_image is not None else None,
        height=config["height"],
        width=config["width"],
        num_frames=config["num_frames"],
        num_inference_steps=config["num_inference_steps"],
        switch_DiT_boundary=config["switch_diT_boundary"],
        seed=config["seed"],
        tiled=config["tiled"],
    )
    return [Image(image) for image in video]
