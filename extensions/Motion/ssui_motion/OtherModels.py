"""Source-based motion models sharing SSUI's MotionClip output contract."""
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


def _run_model(config, prompt, engine):
    root = Path(__file__).resolve().parents[3]
    python = runtime_python(engine)
    if not Path(python).is_file():
        raise RuntimeError(f'{engine} 隔离环境不存在，请运行 yarn install:{engine}。')
    stem = root / 'output' / (engine + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    stem.parent.mkdir(parents=True, exist_ok=True)
    command = [str(python), str(Path(__file__).with_name('_other_motion_runner.py')), engine,
               '--prompt', prompt.text, '--duration', str(config['duration']), '--seed', str(config['seed']),
               '--device', config['device'], '--output', str(stem)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace', env=runtime_environment(engine),
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    tail = deque(maxlen=100)
    for line in process.stdout:
        print_runtime_line(line)
        tail.append(line)
    if process.wait():
        raise RuntimeError(f'{engine} 生成失败：\n' + ''.join(tail)[-5000:])
    with open(str(stem) + '.motion.json', encoding='utf-8') as stream:
        manifest = json.load(stream)
    if not Path(str(stem) + '.npz').is_file():
        raise RuntimeError(f'{engine} 未生成 NPZ 文件')
    return MotionClip(path=str(stem) + '.motion.json', npz_path=str(stem) + '.npz',
                      model=manifest['metadata']['model'], fps=manifest['fps'], frames=len(manifest['positions']))


@param('duration', Slider(2, 9, 0.5), default=4.0)
@param('seed', Random(), default=42)
@param('device', Select('auto', 'cuda', 'cpu'), default='auto')
def GenerateMSFlowMotion(config: SSUIConfig, prompt: Prompt) -> MotionClip:
    """Generate 22-joint motion using MotionSpaceFlow XYZ."""
    if config.is_prepare():
        return MotionClip()
    if not prompt.text.strip():
        raise ValueError('动作描述不能为空。')
    return _run_model(config, prompt, 'msflow')


@param('duration', Slider(2, 10, 0.5), default=4.0)
@param('seed', Random(), default=42)
@param('device', Select('auto', 'cuda', 'cpu'), default='auto')
def GenerateHYMotion(config: SSUIConfig, prompt: Prompt) -> MotionClip:
    """Generate skeletal motion using HY-Motion 1.0 Lite."""
    if config.is_prepare():
        return MotionClip()
    if not prompt.text.strip():
        raise ValueError('动作描述不能为空。')
    return _run_model(config, prompt, 'hy-motion')
