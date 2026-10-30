"""Fail early on known incompatible native runtime inputs; never emulate silently."""
import argparse
from runtime_config import runtime_for
import re
from pathlib import Path
import urllib.request


def check_lock(path, target):
    text = path.read_text()
    if target.endswith('arm64'):
        if re.search(r'https?://\S*(?:win_amd64|x86_64)\S*\.whl', text):
            raise ValueError(f'{path}: x86_64-only wheel URL cannot be used for {target}; provide a native dependency lock')
        if re.search(r'^torch==[^\n]*\+cu', text, re.M):
            raise ValueError(f'{path}: x86_64 CUDA torch lock cannot be reused for {target}; resolve and test native dependencies first')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--target', required=True)
    p.add_argument('--lock', type=Path)
    p.add_argument('--triple')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = runtime_for(a.target)
    triple = target['pythonTarget']
    if a.triple and a.triple != triple:
        raise ValueError('runtime triple differs from shared runtime configuration')
    check_lock(a.lock or root / 'dependencies' / target['lockFile'], a.target)
    version, release = target['pythonVersion'], target['pythonRelease']
    url = f'https://github.com/astral-sh/python-build-standalone/releases/download/{release}/cpython-{version}+{release}-{triple}-install_only_stripped.tar.gz'
    # Check the actual runtime the installer downloads, not just the CI Python.
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60) as response:
        if response.status != 200:
            raise ValueError(f'Python runtime unavailable for {a.target}')


if __name__ == '__main__':
    main()
