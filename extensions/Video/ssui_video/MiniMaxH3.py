import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image as PILImage

from ssui.annotation import param
from ssui.base import Prompt, Image
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Select


# MiniMax H3（33B 全模态 DiT，开源版最接近 Seedance 2.0 的效果）本地节点。
# H3-Context-IR 与 2K 重生成模块官方未开源，本地只能跑 H3-Base 的 768p 输出；
# 若要做 2K 工作流，需要按官方 Prompting Guidance 自行预处理提示词。
# H3 需要独立 venv（Python>=3.12 / torch>=2.7 / 新版 diffusers ModularPipeline），
# 本节点通过 subprocess 调用同目录的 h3_runner.py。
# 建议环境变量：
#   SSUI_H3_PYTHON   H3 venv 的 python 可执行文件（默认探测 h3-venv 与系统 python）
#   SSUI_H3_MODEL_ID 模型仓库 id（默认 MiniMaxAI/MiniMax-H3）
H3_MODEL_ID = os.environ.get("SSUI_H3_MODEL_ID", "MiniMaxAI/MiniMax-H3")
H3_PYTHON = os.environ.get("SSUI_H3_PYTHON", "")
H3_RUNNER = os.path.join(os.path.dirname(__file__), "h3_runner.py")


def _h3_python() -> str:
    if H3_PYTHON:
        return H3_PYTHON
    candidates = [
        os.path.join("h3-venv", "Scripts", "python.exe"),  # Windows
        os.path.join("h3-venv", "bin", "python"),          # Linux / macOS
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def _read_video_frames(path: str) -> list[Image]:
    import imageio

    frames = []
    with imageio.get_reader(path) as reader:
        for frame in reader:
            frames.append(Image(PILImage.fromarray(frame)))
    return frames


def _run_h3(
    config: SSUIConfig,
    task: str,
    prompt: Prompt,
    image: Image = None,
    last_image: Image = None,
) -> list[Image]:
    tmpdir = tempfile.mkdtemp(prefix="ssui_h3_")
    output = os.path.join(tmpdir, "output.mp4")
    try:
        cmd = [
            _h3_python(),
            H3_RUNNER,
            "--task", task,
            "--model-id", H3_MODEL_ID,
            "--prompt", prompt.text,
            "--num-frames", str(config["num_frames"]),
            "--height", str(config["height"]),
            "--width", str(config["width"]),
            "--seed", str(config["seed"]),
            "--quantization", config["quantization"],
            "--output", output,
        ]
        if image is not None:
            first_path = os.path.join(tmpdir, "first.png")
            image._image.save(first_path)
            cmd += ["--image", first_path]
        if last_image is not None:
            last_path = os.path.join(tmpdir, "last.png")
            last_image._image.save(last_path)
            cmd += ["--last-image", last_path]

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
                "MiniMax H3 生成失败。请确认 h3-venv 已按说明安装（新版 diffusers / "
                "torch>=2.7 / torchao），且已在 HF 同意 MiniMaxAI/MiniMax-H3 许可并登录。\n"
                + tail
            )
        if not os.path.exists(output):
            raise RuntimeError("MiniMax H3 未生成输出文件: " + output)
        return _read_video_frames(output)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@param("seed", Random(), default=42)
@param("num_frames", Slider(5, 365, 1), default=124)
@param("height", Slider(32, 1536, 32), default=768)
@param("width", Slider(32, 1536, 32), default=1344)
@param("quantization", Select("none", "int8"), default="none")
def H3TextToVideo(config: SSUIConfig, prompt: Prompt) -> list[Image]:
    """MiniMax H3 文生视频（t2va，768p + 原生音频；独立 H3 venv 运行）。"""
    if config.is_prepare():
        return [Image()]
    return _run_h3(config, "t2va", prompt)


@param("seed", Random(), default=42)
@param("num_frames", Slider(5, 365, 1), default=124)
@param("height", Slider(32, 1536, 32), default=768)
@param("width", Slider(32, 1536, 32), default=1344)
@param("quantization", Select("none", "int8"), default="none")
def H3ImageToVideo(
    config: SSUIConfig,
    image: Image,
    prompt: Prompt,
    last_image: Image = None,
) -> list[Image]:
    """MiniMax H3 图生视频（fl2va，可选尾帧；768p + 原生音频；独立 H3 venv 运行）。"""
    if config.is_prepare():
        return [Image()]
    return _run_h3(config, "fl2va", prompt, image=image, last_image=last_image)
