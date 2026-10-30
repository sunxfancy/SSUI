"""SSUI adapter for isolated NVIDIA ARDY inference."""
from collections import deque
import datetime
import json
import os
from pathlib import Path
import subprocess

from ssui.annotation import param
from ssui.base import MotionClip, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Select, Slider
from ._runtime import runtime_environment, runtime_python, print_runtime_line

ARDY_MODELS = ('ARDY-SOMA-RP-30FPS-Horizon60', 'ARDY-Core-RP-20FPS-Horizon40')


def _ardy_python():
    candidate = runtime_python('ardy')
    if os.environ.get('SSUI_ARDY_PYTHON') or Path(candidate).is_file():
        return candidate
    raise RuntimeError('ARDY 隔离环境不存在，请运行 yarn install:ardy。')


def _run_ardy(config, prompt):
    stem = Path('output').resolve() / ('ardy_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    stem.parent.mkdir(parents=True, exist_ok=True)
    command = [_ardy_python(), str(Path(__file__).with_name('_ardy_runner.py')), prompt.text,
               '--model', config['model'], '--duration', str(config['duration']),
               '--diffusion_steps', str(config['diffusion_steps']), '--seed', str(config['seed']),
               '--output', str(stem), '--no-postprocess']
    env = dict(runtime_environment('ardy'), SSUI_ARDY_DEVICE=config['device'], TEXT_ENCODER_MODE='local')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace', env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    tail = deque(maxlen=100)
    for line in process.stdout:
        print_runtime_line(line)
        tail.append(line)
    if process.wait():
        raise RuntimeError('ARDY 生成失败：\n' + ''.join(tail)[-5000:])
    if not stem.with_suffix('.npz').is_file():
        raise RuntimeError('ARDY 未生成 NPZ 文件')
    return stem


@param('model', Select(*ARDY_MODELS), default=ARDY_MODELS[0])
@param('duration', Slider(1, 20, 0.5), default=4.0)
@param('diffusion_steps', Slider(1, 10, 1), default=10)
@param('seed', Random(), default=42)
@param('device', Select('auto', 'cuda', 'cpu'), default='auto')
def GenerateArdyMotion(config: SSUIConfig, prompt: Prompt) -> MotionClip:
    """从文字生成 ARDY 骨骼动作，支持三维预览及 NPZ 下载。"""
    if config.is_prepare():
        return MotionClip()
    if not prompt.text.strip():
        raise ValueError('动作描述不能为空。')
    stem = _run_ardy(config, prompt)
    manifest_path = str(stem) + '.motion.json'
    with open(manifest_path, encoding='utf-8') as stream:
        manifest = json.load(stream)
    return MotionClip(path=manifest_path, npz_path=str(stem) + '.npz',
                      model=config['model'], fps=manifest['fps'], frames=len(manifest['positions']))
