"""Install source-based motion runtimes without replacing the host GPU stack."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[2]
MODELS = {
    'hy-motion': ('https://github.com/Tencent-Hunyuan/HY-Motion-1.0.git', '4e426f5a1021cbcf7f375458c37b840ee7225229', 'hymotion'),
    'msflow': ('https://github.com/YU1ut/MSFlow.git', 'df3e73c3088cf0d72dfe006bbf34928b27275ab9', 'models.MMDiT_xyz'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=MODELS)
    parser.add_argument('--path', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    url, revision, module = MODELS[args.model]
    source = (args.source or ROOT / '.build' / args.model / 'source').resolve()
    target = (args.path or ROOT / '.venv' / args.model).resolve()
    if target == Path(sys.prefix).resolve():
        raise ValueError('Use an independent child environment')
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', url, str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', revision], check=True)
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != revision:
        raise RuntimeError(f'Expected source {revision}, found {actual}; use a separate pinned checkout')
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(target)], check=True)
    subprocess.run([str(python), '-m', 'ensurepip', '--upgrade'], check=True)
    site = subprocess.check_output([str(python), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True).strip()
    Path(site, 'ssui_parent_venv.pth').write_text(sysconfig.get_path('purelib') + '\n', encoding='utf-8')
    Path(site, 'ssui_motion_source.pth').write_text(str(source) + '\n', encoding='utf-8')
    # Platform adaptation: reuse native ARM64 numpy/torch and Transformers 4.57.6;
    # upstream pins old x86 wheels / NumPy 1.x without CPython 3.13 ARM64 builds.
    subprocess.run([str(python), '-m', 'pip', 'install', 'transformers==4.57.6', 'torchdiffeq==0.2.5', 'hydra-core>=1.3', 'omegaconf>=2.3', 'einops>=0.8.1', 'scipy>=1.10', 'PyYAML>=6'], check=True)
    subprocess.run([str(python), '-c', f'import importlib, torch; importlib.import_module("{module}"); print("CUDA:",torch.cuda.is_available(), "torch:",torch.__version__)'], check=True)
    (target / 'ssui-provenance.json').write_text(json.dumps({'source': url, 'revision': revision, 'parent_python': sys.executable, 'numpy': 'inherited native platform build', 'transformers': '4.57.6'}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
