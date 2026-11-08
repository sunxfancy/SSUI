from backend.contracts.services import ProcessRunner, ExecutionContext
import datetime
import os
import subprocess
import sys
from importlib.util import find_spec
from backend.contracts.media import Prompt
from backend.contracts.services import InferenceConfig as SSUIConfig
KIMODO_MODELS = ('Kimodo-SOMA-RP-v1.1', 'Kimodo-SOMA-SEED-v1.1', 'Kimodo-G1-RP-v1', 'Kimodo-G1-SEED-v1')

def _kimodo_python() -> str:
    configured = os.environ.get('SSUI_KIMODO_PYTHON')
    if configured:
        return configured
    if find_spec('kimodo') is not None:
        return sys.executable
    candidates = (os.path.join('.venv', 'kimodo', 'Scripts', 'python.exe'), os.path.join('.venv', 'kimodo', 'bin', 'python'))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return sys.executable

def _kimodo_runner() -> str:
    return os.path.join(os.path.dirname(__file__), '_kimodo_runner.py')

def _run_kimodo(config: SSUIConfig, prompt: Prompt, *, process_runner: ProcessRunner, context: ExecutionContext) -> str:
    output_dir = os.fspath(context.output_dir.resolve())
    os.makedirs(output_dir, exist_ok=True)
    output_stem = os.path.join(output_dir, 'kimodo_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    command = [_kimodo_python(), _kimodo_runner(), prompt.text, '--model', config['model'], '--duration', str(config['duration']), '--diffusion_steps', str(config['diffusion_steps']), '--seed', str(config['seed']), '--output', output_stem, '--no-postprocess']
    if config['export_bvh'] and 'SOMA' in config['model']:
        command.append('--bvh')
    env = os.environ.copy()
    env.setdefault('LOCAL_CACHE', 'True')
    env.setdefault('TEXT_ENCODER_MODE', 'local')
    env['TEXT_ENCODER_DEVICE'] = config['text_encoder_device']
    process_runner.run(command, context=context, env=env)
    output_path = output_stem + '.npz'
    if not os.path.isfile(output_path):
        raise RuntimeError('Kimodo 未生成预期文件: ' + output_path)
    return output_path

def KimodoTextToMotion(config: SSUIConfig, prompt: Prompt, *, process_runner: ProcessRunner, context: ExecutionContext) -> str:
    """使用 NVIDIA Kimodo 从文本生成动作，返回生成的 NPZ 文件路径。"""
    if config.is_prepare():
        return ''
    return _run_kimodo(config, prompt, process_runner=process_runner, context=context)
