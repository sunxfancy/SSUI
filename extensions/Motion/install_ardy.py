"""Install pinned ARDY inference into a child environment, preserving GPU PyTorch."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[2]
REVISION = 'e706e27acc88070918308a10922b8f7174d0825e'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=ROOT / '.venv/ardy')
    parser.add_argument('--source', type=Path, default=ROOT / '.build/ardy/source')
    args = parser.parse_args()
    target = args.path.resolve()
    if target == Path(sys.prefix).resolve():
        raise ValueError('ARDY must use a separate child environment')
    source = args.source.resolve()
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', 'https://github.com/nv-tlabs/ardy.git', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', REVISION], check=True)
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != REVISION:
        raise RuntimeError(f'Expected ARDY source {REVISION}, found {actual}; use a separate pinned checkout')
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(target)], check=True)
    subprocess.run([str(python), '-m', 'ensurepip', '--upgrade'], check=True)
    site = subprocess.check_output([str(python), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True).strip()
    Path(site, 'ssui_parent_venv.pth').write_text(sysconfig.get_path('purelib') + '\n', encoding='utf-8')
    env = dict(os.environ, ARDY_SKIP_MOTION_CORRECTION='1')
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', str(source)], env=env, check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(Path(__file__).with_name('requirements-ardy.txt'))], check=True)
    subprocess.run([str(python), '-c', 'import ardy, torch, transformers; print("ARDY:", ardy.__file__); print("torch:", torch.__version__, "CUDA:", torch.cuda.is_available(), "transformers:", transformers.__version__)'], check=True)
    (target / 'ssui-provenance.json').write_text(json.dumps({'source': 'https://github.com/nv-tlabs/ardy', 'revision': REVISION, 'parent_python': sys.executable, 'postprocessing': False}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
