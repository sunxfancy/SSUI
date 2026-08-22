import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image as PILImage

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch, Select


# LTX-2.5（Lightricks）本地节点。
# 注意：LTX-2.5 官方栈要求 Python >= 3.12 / PyTorch ~= 2.7 / CUDA >= 12.7，
# 与 SSUI 主环境的 torch 2.4.1 冲突，所以节点通过 subprocess 调用独立的 LTX 虚拟环境。
# 建议环境变量：
#   SSUI_LTX_PYTHON      LTX venv 的 python 可执行文件（默认依次探测 ltx-venv 与系统 python）
#   SSUI_LTX_MODEL_ROOT  权重根目录（默认 models/ltx-2.5，按官方 README 的目录布局）
# 权重（HF 门控仓库 Lightricks/LTX-2.5，约 66GiB）：
#   diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors  （快速蒸馏版）
#   diffusion_models/ltx-2.5-22b-dev-transformer-bf16.safetensors        （全量版，I2V 用）
#   text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors
#   vae/ltx-2.5-video-vae-bf16.safetensors
#   vae/ltx-2.5-audio-vae-bf16.safetensors
#   latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors
LTX_MODEL_ROOT = os.environ.get("SSUI_LTX_MODEL_ROOT", "models/ltx-2.5")
LTX_PYTHON = os.environ.get("SSUI_LTX_PYTHON", "")

LTX_DISTILLED_TRANSFORMER = os.environ.get(
    "SSUI_LTX_TRANSFORMER",
    os.path.join(LTX_MODEL_ROOT, "diffusion_models", "ltx-2.5-22b-distilled-transformer-bf16.safetensors"),
)
LTX_DEV_TRANSFORMER = os.environ.get(
    "SSUI_LTX_TRANSFORMER_DEV",
    os.path.join(LTX_MODEL_ROOT, "diffusion_models", "ltx-2.5-22b-dev-transformer-bf16.safetensors"),
)
LTX_TEXT_ENCODER = os.environ.get(
    "SSUI_LTX_TEXT_ENCODER",
    os.path.join(LTX_MODEL_ROOT, "text_encoders", "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"),
)
LTX_VIDEO_VAE = os.environ.get(
    "SSUI_LTX_VIDEO_VAE",
    os.path.join(LTX_MODEL_ROOT, "vae", "ltx-2.5-video-vae-bf16.safetensors"),
)
LTX_AUDIO_VAE = os.environ.get(
    "SSUI_LTX_AUDIO_VAE",
    os.path.join(LTX_MODEL_ROOT, "vae", "ltx-2.5-audio-vae-bf16.safetensors"),
)
LTX_SPATIAL_UPSAMPLER = os.environ.get(
    "SSUI_LTX_SPATIAL_UPSAMPLER",
    os.path.join(LTX_MODEL_ROOT, "latent_upscale_models", "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"),
)


def _ltx_python() -> str:
    if LTX_PYTHON:
        return LTX_PYTHON
    candidates = [
        os.path.join("ltx-venv", "Scripts", "python.exe"),  # Windows
        os.path.join("ltx-venv", "bin", "python"),          # Linux / macOS
        os.path.join("venv", "Scripts", "python.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def _run_ltx(module: str, args: list[str]) -> None:
    """调用 LTX venv 的 CLI，实时转发输出，失败时抛出带日志的错误。"""
    python = _ltx_python()
    cmd = [python, "-m", "ltx_pipelines." + module, *args]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log = []
    for line in proc.stdout:
        print(line, end="")
        log.append(line)
    proc.wait()
    if proc.returncode != 0:
        tail = "".join(log)[-3000:]
        raise RuntimeError(
            "LTX-2.5 生成失败。请确认已按 README 创建独立 venv 并安装 ltx-pipelines"
            "（Python>=3.12 / torch>=2.7），且权重已下载。\n" + tail
        )


def _read_video_frames(path: str) -> list[Image]:
    import imageio

    frames = []
    with imageio.get_reader(path) as reader:
        for frame in reader:
            frames.append(Image(PILImage.fromarray(frame)))
    return frames


@param("seed", Random(), default=42)
@param("num_frames", Slider(9, 497, 8), default=121)
@param("height", Slider(64, 1024, 64), default=512)
@param("width", Slider(64, 1024, 64), default=768)
@param("quantization", Select("none", "fp8-cast"), default="fp8-cast")
@param("offload", Select("none", "cpu", "disk"), default="cpu")
@param("enhance_prompt", Switch(), default=False)
def LTX2TextToVideo(
    config: SSUIConfig, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    """LTX-2.5 文生视频（蒸馏管线，8 步，最快；独立 LTX venv 运行）。"""
    if config.is_prepare():
        return [Image()]

    tmpdir = tempfile.mkdtemp(prefix="ssui_ltx_")
    output = os.path.join(tmpdir, "output.mp4")
    try:
        args = [
            "--transformer-path", LTX_DISTILLED_TRANSFORMER,
            "--text-encoder-path", LTX_TEXT_ENCODER,
            "--video-vae-path", LTX_VIDEO_VAE,
            "--audio-vae-path", LTX_AUDIO_VAE,
            "--spatial-upsampler-path", LTX_SPATIAL_UPSAMPLER,
            "--prompt", prompt.text,
            "--num-frames", str(config["num_frames"]),
            "--height", str(config["height"]),
            "--width", str(config["width"]),
            "--seed", str(config["seed"]),
            "--output-path", output,
        ]
        if negative_prompt.text:
            args += ["--negative-prompt", negative_prompt.text]
        if config["quantization"] != "none":
            args += ["--quantization", config["quantization"]]
        if config["offload"] != "none":
            args += ["--offload", config["offload"]]
        if config["enhance_prompt"]:
            args += ["--enhance-prompt"]
        _run_ltx("distilled", args)
        if not os.path.exists(output):
            raise RuntimeError("LTX-2.5 未生成输出文件: " + output)
        return _read_video_frames(output)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@param("seed", Random(), default=42)
@param("num_frames", Slider(9, 497, 8), default=121)
@param("num_inference_steps", Slider(1, 60, 1), default=40)
@param("height", Slider(32, 1024, 32), default=512)
@param("width", Slider(32, 1024, 32), default=768)
@param("image_strength", Slider(0, 1, 0.05), default=0.8)
@param("quantization", Select("none", "fp8-cast"), default="fp8-cast")
@param("offload", Select("none", "cpu", "disk"), default="cpu")
@param("enhance_prompt", Switch(), default=False)
def LTX2ImageToVideo(
    config: SSUIConfig, image: Image, prompt: Prompt, negative_prompt: Prompt
) -> list[Image]:
    """LTX-2.5 图生视频（单阶段管线，需要全量 dev 权重；独立 LTX venv 运行）。"""
    if config.is_prepare():
        return [Image()]

    tmpdir = tempfile.mkdtemp(prefix="ssui_ltx_")
    output = os.path.join(tmpdir, "output.mp4")
    first_frame = os.path.join(tmpdir, "first_frame.png")
    try:
        image._image.save(first_frame)
        args = [
            "--transformer-path", LTX_DEV_TRANSFORMER,
            "--text-encoder-path", LTX_TEXT_ENCODER,
            "--video-vae-path", LTX_VIDEO_VAE,
            "--audio-vae-path", LTX_AUDIO_VAE,
            "--prompt", prompt.text,
            "--image", first_frame, "0", str(config["image_strength"]),
            "--num-frames", str(config["num_frames"]),
            "--num-inference-steps", str(config["num_inference_steps"]),
            "--height", str(config["height"]),
            "--width", str(config["width"]),
            "--seed", str(config["seed"]),
            "--output-path", output,
        ]
        if negative_prompt.text:
            args += ["--negative-prompt", negative_prompt.text]
        if config["quantization"] != "none":
            args += ["--quantization", config["quantization"]]
        if config["offload"] != "none":
            args += ["--offload", config["offload"]]
        if config["enhance_prompt"]:
            args += ["--enhance-prompt"]
        _run_ltx("ti2vid_one_stage", args)
        if not os.path.exists(output):
            raise RuntimeError("LTX-2.5 未生成输出文件: " + output)
        return _read_video_frames(output)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
