from backend.contracts.services import ProcessRunner, ExecutionContext
import os
import shutil
import subprocess
import sys
from importlib.util import find_spec
import tempfile
from PIL import Image as PILImage
from backend.contracts.media import Prompt, Image
from backend.contracts.services import InferenceConfig as SSUIConfig
LTX_MODEL_ROOT = os.environ.get('SSUI_LTX_MODEL_ROOT', 'models/ltx-2.5')
LTX_PYTHON = os.environ.get('SSUI_LTX_PYTHON', '')
LTX_DISTILLED_TRANSFORMER = os.environ.get('SSUI_LTX_TRANSFORMER', os.path.join(LTX_MODEL_ROOT, 'diffusion_models', 'ltx-2.5-22b-distilled-transformer-bf16.safetensors'))
LTX_DEV_TRANSFORMER = os.environ.get('SSUI_LTX_TRANSFORMER_DEV', os.path.join(LTX_MODEL_ROOT, 'diffusion_models', 'ltx-2.5-22b-dev-transformer-bf16.safetensors'))
LTX_TEXT_ENCODER = os.environ.get('SSUI_LTX_TEXT_ENCODER', os.path.join(LTX_MODEL_ROOT, 'text_encoders', 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors'))
LTX_VIDEO_VAE = os.environ.get('SSUI_LTX_VIDEO_VAE', os.path.join(LTX_MODEL_ROOT, 'vae', 'ltx-2.5-video-vae-bf16.safetensors'))
LTX_AUDIO_VAE = os.environ.get('SSUI_LTX_AUDIO_VAE', os.path.join(LTX_MODEL_ROOT, 'vae', 'ltx-2.5-audio-vae-bf16.safetensors'))
LTX_SPATIAL_UPSAMPLER = os.environ.get('SSUI_LTX_SPATIAL_UPSAMPLER', os.path.join(LTX_MODEL_ROOT, 'latent_upscale_models', 'ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors'))

def _ltx_python() -> str:
    if LTX_PYTHON:
        return LTX_PYTHON
    if find_spec('ltx_pipelines') is not None:
        return sys.executable
    candidates = [os.path.join('ltx-venv', 'Scripts', 'python.exe'), os.path.join('ltx-venv', 'bin', 'python'), os.path.join('venv', 'Scripts', 'python.exe')]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable

def _run_ltx(module: str, args: list[str], *, process_runner: ProcessRunner, context: ExecutionContext) -> None:
    """调用 LTX venv 的 CLI，实时转发输出，失败时抛出带日志的错误。"""
    python = _ltx_python()
    cmd = [python, '-m', 'ltx_pipelines.' + module, *args]
    process_runner.run(cmd, context=context)

def _read_video_frames(path: str) -> list[Image]:
    import imageio
    frames = []
    with imageio.get_reader(path) as reader:
        for frame in reader:
            frames.append(Image(PILImage.fromarray(frame)))
    return frames

def LTX2TextToVideo(config: SSUIConfig, prompt: Prompt, negative_prompt: Prompt, *, process_runner: ProcessRunner, context: ExecutionContext) -> list[Image]:
    """LTX-2.5 文生视频（蒸馏管线，8 步，最快；独立 LTX venv 运行）。"""
    if config.is_prepare():
        return [Image()]
    tmpdir = tempfile.mkdtemp(prefix='ssui_ltx_')
    output = os.path.join(tmpdir, 'output.mp4')
    try:
        args = ['--transformer-path', LTX_DISTILLED_TRANSFORMER, '--text-encoder-path', LTX_TEXT_ENCODER, '--video-vae-path', LTX_VIDEO_VAE, '--audio-vae-path', LTX_AUDIO_VAE, '--spatial-upsampler-path', LTX_SPATIAL_UPSAMPLER, '--prompt', prompt.text, '--num-frames', str(config['num_frames']), '--height', str(config['height']), '--width', str(config['width']), '--seed', str(config['seed']), '--output-path', output]
        if negative_prompt.text:
            args += ['--negative-prompt', negative_prompt.text]
        if config['quantization'] != 'none':
            args += ['--quantization', config['quantization']]
        if config['offload'] != 'none':
            args += ['--offload', config['offload']]
        if config['enhance_prompt']:
            args += ['--enhance-prompt']
        _run_ltx('distilled', args, process_runner=process_runner, context=context)
        if not os.path.exists(output):
            raise RuntimeError('LTX-2.5 未生成输出文件: ' + output)
        return _read_video_frames(output)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def LTX2ImageToVideo(config: SSUIConfig, image: Image, prompt: Prompt, negative_prompt: Prompt, *, process_runner: ProcessRunner, context: ExecutionContext) -> list[Image]:
    """LTX-2.5 图生视频（单阶段管线，需要全量 dev 权重；独立 LTX venv 运行）。"""
    if config.is_prepare():
        return [Image()]
    tmpdir = tempfile.mkdtemp(prefix='ssui_ltx_')
    output = os.path.join(tmpdir, 'output.mp4')
    first_frame = os.path.join(tmpdir, 'first_frame.png')
    try:
        image._image.save(first_frame)
        args = ['--transformer-path', LTX_DEV_TRANSFORMER, '--text-encoder-path', LTX_TEXT_ENCODER, '--video-vae-path', LTX_VIDEO_VAE, '--audio-vae-path', LTX_AUDIO_VAE, '--prompt', prompt.text, '--image', first_frame, '0', str(config['image_strength']), '--num-frames', str(config['num_frames']), '--num-inference-steps', str(config['num_inference_steps']), '--height', str(config['height']), '--width', str(config['width']), '--seed', str(config['seed']), '--output-path', output]
        if negative_prompt.text:
            args += ['--negative-prompt', negative_prompt.text]
        if config['quantization'] != 'none':
            args += ['--quantization', config['quantization']]
        if config['offload'] != 'none':
            args += ['--offload', config['offload']]
        if config['enhance_prompt']:
            args += ['--enhance-prompt']
        _run_ltx('ti2vid_one_stage', args, process_runner=process_runner, context=context)
        if not os.path.exists(output):
            raise RuntimeError('LTX-2.5 未生成输出文件: ' + output)
        return _read_video_frames(output)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
