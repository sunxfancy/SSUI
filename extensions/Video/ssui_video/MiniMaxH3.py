import os
import shutil
import subprocess
import sys
import tempfile
import uuid

from ssui.annotation import param
from ssui.base import Prompt, Image, Video
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
#   SSUI_H3_NF4_MODEL_ROOT  DiffSynth-Studio NF4 权重目录
#   SSUI_H3_DIFFSYNTH_ROOT  当前 DiffSynth-Studio 源码 checkout（可选）
H3_MODEL_ID = os.environ.get("SSUI_H3_MODEL_ID", "MiniMaxAI/MiniMax-H3")
H3_PYTHON = os.environ.get("SSUI_H3_PYTHON", "")
H3_RUNNER = os.path.join(os.path.dirname(__file__), "h3_runner.py")
H3_NF4_RUNNER = os.path.join(os.path.dirname(__file__), "h3_nf4_runner.py")
H3_NF4_MODEL_ROOT = os.environ.get(
    "SSUI_H3_NF4_MODEL_ROOT", os.path.join("models", "minimax-h3-nf4")
)
H3_DIFFSYNTH_ROOT = os.environ.get("SSUI_H3_DIFFSYNTH_ROOT", "")
H3_PROCESSOR_MODEL_ID = os.environ.get("SSUI_H3_PROCESSOR_MODEL_ID", "MiniMax/MiniMax-H3")
H3_VRAM_RESERVE_GIB = os.environ.get("SSUI_H3_VRAM_RESERVE_GIB", "2")


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


def _run_h3(
    config: SSUIConfig,
    task: str,
    prompt: Prompt,
    image: Image = None,
    last_image: Image = None,
) -> Video:
    tmpdir = tempfile.mkdtemp(prefix="ssui_h3_")
    output_dir = os.path.abspath("output")
    os.makedirs(output_dir, exist_ok=True)
    output = os.path.join(output_dir, f"h3_{uuid.uuid4().hex}.mp4")
    try:
        quantization = config["quantization"]
        runner = H3_NF4_RUNNER if quantization == "nf4" else H3_RUNNER
        cmd = [
            _h3_python(),
            runner,
            "--task", task,
            "--prompt", prompt.text,
            "--num-frames", str(config["num_frames"]),
            "--num-inference-steps", str(config["num_inference_steps"]),
            "--height", str(config["height"]),
            "--width", str(config["width"]),
            "--seed", str(config["seed"]),
            "--output", output,
        ]
        if quantization == "nf4":
            cmd += [
                "--model-root", H3_NF4_MODEL_ROOT,
                "--processor-model-id", H3_PROCESSOR_MODEL_ID,
                "--vram-reserve-gib", H3_VRAM_RESERVE_GIB,
            ]
            if H3_DIFFSYNTH_ROOT:
                cmd += ["--diffsynth-root", H3_DIFFSYNTH_ROOT]
        else:
            cmd += [
                "--model-id", H3_MODEL_ID,
                "--quantization", quantization,
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
                "MiniMax H3 生成失败。请确认 h3-venv 与所选后端依赖、权重均已安装。\n"
                + tail
            )
        if not os.path.exists(output):
            raise RuntimeError("MiniMax H3 未生成输出文件: " + output)
        return Video(format="mp4", path=output, fps=24, metadata={"audio": True})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@param("seed", Random(), default=42)
@param("num_frames", Slider(5, 365, 1), default=124)
@param("num_inference_steps", Slider(1, 60, 1), default=50)
@param("height", Slider(32, 1536, 32), default=768)
@param("width", Slider(32, 1536, 32), default=1344)
@param("quantization", Select("none", "int8", "nf4"), default="none")
def H3TextToVideo(config: SSUIConfig, prompt: Prompt) -> Video:
    """MiniMax H3 文生视频（t2va，768p + 原生音频；独立 H3 venv 运行）。"""
    if config.is_prepare():
        return Video()
    return _run_h3(config, "t2va", prompt)


@param("seed", Random(), default=42)
@param("num_frames", Slider(5, 365, 1), default=124)
@param("num_inference_steps", Slider(1, 60, 1), default=50)
@param("height", Slider(32, 1536, 32), default=768)
@param("width", Slider(32, 1536, 32), default=1344)
@param("quantization", Select("none", "int8", "nf4"), default="none")
def H3ImageToVideo(
    config: SSUIConfig,
    image: Image,
    prompt: Prompt,
    last_image: Image = None,
) -> Video:
    """MiniMax H3 图生视频（fl2va，可选尾帧；768p + 原生音频；独立 H3 venv 运行）。"""
    if config.is_prepare():
        return Video()
    return _run_h3(config, "fl2va", prompt, image=image, last_image=last_image)
