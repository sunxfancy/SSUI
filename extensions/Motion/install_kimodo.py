"""Install the pinned official Kimodo runtime in an independent environment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

REVISION = '1aece8c124d73d255ceff5086d983b844c9f4e94'
ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=ROOT/'.venv/kimodo')
    args = parser.parse_args()
    target = args.path.resolve()
    python = target/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(target)
    env = dict(os.environ, SKIP_MOTION_CORRECTION_IN_SETUP='1')
    constraints = ['-c',str(Path(__file__).with_name('kimodo-macos-constraints.txt'))] if sys.platform == 'darwin' else []
    subprocess.run([str(python), '-m', 'pip', 'install', *constraints, 'torch>=2.6,<3',
                    f'kimodo @ git+https://github.com/nv-tlabs/kimodo.git@{REVISION}'],env=env,check=True)
    subprocess.run([str(python), '-c', 'import torch, kimodo; print("torch:",torch.__version__,"MPS:",torch.backends.mps.is_available(),"Kimodo:",kimodo.__file__)'],check=True)


if __name__ == '__main__':
    main()
