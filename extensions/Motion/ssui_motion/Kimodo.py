import datetime
import os
import subprocess
import sys
import json
from pathlib import Path
from collections import deque

from ssui.annotation import param
from ssui.base import Prompt, MotionClip
from ssui.config import SSUIConfig
from ssui.controller import Random, Select, Slider, Switch


KIMODO_MODELS = (
    "Kimodo-SOMA-RP-v1.1",
    "Kimodo-SOMA-SEED-v1.1",
    "Kimodo-G1-RP-v1",
    "Kimodo-G1-SEED-v1",
)


def _kimodo_python() -> str:
    configured = os.environ.get("SSUI_KIMODO_PYTHON")
    if configured:
        return configured

    root = Path(__file__).resolve().parents[3]
    candidates = (
        root / ".venv/kimodo/Scripts/python.exe",
        root / ".venv/kimodo/bin/python",
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    raise RuntimeError(
        "Kimodo 隔离环境不存在。请先运行 "
        "extensions/Motion/install_kimodo.ps1。"
    )


def _kimodo_runner() -> str:
    return os.path.join(os.path.dirname(__file__), "_kimodo_runner.py")


def _run_kimodo(config: SSUIConfig, prompt: Prompt) -> str:
    output_dir = os.path.abspath("output")
    os.makedirs(output_dir, exist_ok=True)
    output_stem = os.path.join(
        output_dir,
        "kimodo_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
    )

    command = [
        _kimodo_python(),
        _kimodo_runner(),
        prompt.text,
        "--model",
        config["model"],
        "--duration",
        str(config["duration"]),
        "--diffusion_steps",
        str(config["diffusion_steps"]),
        "--seed",
        str(config["seed"]),
        "--output",
        output_stem,
        # The Windows setup deliberately skips Kimodo's optional native
        # motion_correction extension. Core generation does not require it.
        "--no-postprocess",
    ]
    if config["export_bvh"] and "SOMA" in config["model"]:
        command.append("--bvh")

    env = os.environ.copy()
    env.setdefault("LOCAL_CACHE", "True")
    env.setdefault("TEXT_ENCODER_MODE", "local")
    env["TEXT_ENCODER_DEVICE"] = config["text_encoder_device"]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    output_lines = deque(maxlen=100)
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        output_lines.append(line)
    process.wait()

    if process.returncode != 0:
        tail = "".join(output_lines)[-5000:]
        if "awaiting a review from the repo authors" in tail:
            raise RuntimeError(
                "Kimodo 生成失败：Hugging Face 的 Llama 3 访问申请仍在等待审批。\n"
                + tail
            )
        if any(marker in tail for marker in ("GatedRepoError", "401 Client Error", "403 Client Error")):
            raise RuntimeError("Kimodo 模型访问失败，请检查 Hugging Face 登录和模型访问权限。\n" + tail)
        raise RuntimeError(
            "Kimodo 生成失败，请检查隔离环境和下方运行日志。\n" + tail
        )

    output_path = output_stem + ".npz"
    if not os.path.isfile(output_path):
        raise RuntimeError("Kimodo 未生成预期文件: " + output_path)
    return output_path


@param("model", Select(*KIMODO_MODELS), default="Kimodo-SOMA-RP-v1.1")
@param("duration", Slider(1, 20, 0.5), default=5.0)
@param("diffusion_steps", Slider(1, 200, 1), default=100)
@param("seed", Random(), default=42)
@param("text_encoder_device", Select("cuda", "cpu"), default="cuda")
@param("export_bvh", Switch(), default=False)
def KimodoTextToMotion(config: SSUIConfig, prompt: Prompt) -> str:
    """使用 NVIDIA Kimodo 从文本生成动作，返回生成的 NPZ 文件路径。"""
    if config.is_prepare():
        return ""
    return _run_kimodo(config, prompt)


@param("model", Select(*KIMODO_MODELS), default="Kimodo-SOMA-RP-v1.1")
@param("duration", Slider(1, 20, 0.5), default=5.0)
@param("diffusion_steps", Slider(1, 200, 1), default=100)
@param("seed", Random(), default=42)
@param("text_encoder_device", Select("cuda", "cpu"), default="cuda")
@param("export_bvh", Switch(), default=True)
def GenerateKimodoMotion(config: SSUIConfig, prompt: Prompt) -> MotionClip:
    """Generate a 3D motion clip with playback data and downloadable NPZ/BVH."""
    if config.is_prepare():
        return MotionClip()
    if not prompt.text.strip():
        raise ValueError("动作描述不能为空。")
    path = _run_kimodo(config, prompt)
    manifest_path = str(Path(path).with_suffix(".motion.json"))
    with open(manifest_path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    bvh_path = str(Path(path).with_suffix(".bvh"))
    return MotionClip(path=manifest_path, npz_path=path,
                      bvh_path=bvh_path if os.path.isfile(bvh_path) else None,
                      model=config["model"], fps=manifest["fps"], frames=len(manifest["positions"]))
