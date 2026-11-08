from backend.contracts.services import ProcessRunner, ExecutionContext
import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
import tempfile
import uuid
from backend.contracts.media import Prompt, Image, Video
from backend.contracts.services import InferenceConfig as SSUIConfig
H3_MODEL_ID = os.environ.get('SSUI_H3_MODEL_ID', 'MiniMaxAI/MiniMax-H3')
H3_PYTHON = os.environ.get('SSUI_H3_PYTHON', '')
H3_RUNNER = os.path.join(os.path.dirname(__file__), 'h3_runner.py')
H3_NF4_RUNNER = os.path.join(os.path.dirname(__file__), 'h3_nf4_runner.py')
H3_NF4_MODEL_ROOT = os.environ.get('SSUI_H3_NF4_MODEL_ROOT', os.path.join('models', 'minimax-h3-nf4'))
H3_DIFFSYNTH_ROOT = os.environ.get('SSUI_H3_DIFFSYNTH_ROOT', '')
H3_PROCESSOR_MODEL_ID = os.environ.get('SSUI_H3_PROCESSOR_MODEL_ID', 'MiniMax/MiniMax-H3')
H3_VRAM_RESERVE_GIB = os.environ.get('SSUI_H3_VRAM_RESERVE_GIB', '2')

def _h3_python() -> str:
    if H3_PYTHON:
        return H3_PYTHON
    try:
        from packaging.version import Version
        if Version(version('diffusers')) >= Version('0.42.1'):
            return sys.executable
    except PackageNotFoundError:
        pass
    candidates = [os.path.join('h3-venv', 'Scripts', 'python.exe'), os.path.join('h3-venv', 'bin', 'python')]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable

def _run_h3(config: SSUIConfig, task: str, prompt: Prompt, image: Image=None, last_image: Image=None, *, process_runner: ProcessRunner, context: ExecutionContext) -> Video:
    tmpdir = tempfile.mkdtemp(prefix='ssui_h3_')
    output_dir = os.fspath(context.output_dir.resolve())
    os.makedirs(output_dir, exist_ok=True)
    output = os.path.join(output_dir, f'h3_{uuid.uuid4().hex}.mp4')
    try:
        quantization = config['quantization']
        runner = H3_NF4_RUNNER if quantization == 'nf4' else H3_RUNNER
        cmd = [_h3_python(), runner, '--task', task, '--prompt', prompt.text, '--num-frames', str(config['num_frames']), '--num-inference-steps', str(config['num_inference_steps']), '--height', str(config['height']), '--width', str(config['width']), '--seed', str(config['seed']), '--output', output]
        if quantization == 'nf4':
            cmd += ['--model-root', H3_NF4_MODEL_ROOT, '--processor-model-id', H3_PROCESSOR_MODEL_ID, '--vram-reserve-gib', H3_VRAM_RESERVE_GIB]
            if H3_DIFFSYNTH_ROOT:
                cmd += ['--diffsynth-root', H3_DIFFSYNTH_ROOT]
        else:
            cmd += ['--model-id', H3_MODEL_ID, '--quantization', quantization]
        if image is not None:
            first_path = os.path.join(tmpdir, 'first.png')
            image._image.save(first_path)
            cmd += ['--image', first_path]
        if last_image is not None:
            last_path = os.path.join(tmpdir, 'last.png')
            last_image._image.save(last_path)
            cmd += ['--last-image', last_path]
        process_runner.run(cmd, context=context)
        if not os.path.exists(output):
            raise RuntimeError('MiniMax H3 未生成输出文件: ' + output)
        return Video(format='mp4', path=output, fps=24, metadata={'audio': True})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def H3TextToVideo(config: SSUIConfig, prompt: Prompt, *, process_runner: ProcessRunner, context: ExecutionContext) -> Video:
    """MiniMax H3 文生视频（t2va，768p + 原生音频；独立 H3 venv 运行）。"""
    if config.is_prepare():
        return Video()
    return _run_h3(config, 't2va', prompt, process_runner=process_runner, context=context)

def H3ImageToVideo(config: SSUIConfig, image: Image, prompt: Prompt, last_image: Image=None, *, process_runner: ProcessRunner, context: ExecutionContext) -> Video:
    """MiniMax H3 图生视频（fl2va，可选尾帧；768p + 原生音频；独立 H3 venv 运行）。"""
    if config.is_prepare():
        return Video()
    return _run_h3(config, 'fl2va', prompt, image=image, last_image=last_image, process_runner=process_runner, context=context)
