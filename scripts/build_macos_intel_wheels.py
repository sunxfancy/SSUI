"""Build the native CPU PyTorch stack missing from upstream Intel macOS wheels."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

SOURCES = {
    'torch': ('pytorch', 'ba56102387ef21a3b04b357e5b183d48f0afefc7', '2.8.0'),
    'torchvision': ('vision', '824e8c8726b65fd9d5abdc9702f81c2b0c4c0dc8', '0.23.0'),
    'torchaudio': ('audio', '6e1c7fe9ff6d82b8665d0a46d859d3357d2ebaaa', '2.8.0'),
}


def run(*args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main():
    if sys.platform != 'darwin' or platform.machine() != 'x86_64':
        raise RuntimeError('requires native Intel macOS Python')
    root = Path.cwd()
    output = root / 'native-wheels'
    output.mkdir(exist_ok=True)
    env = dict(os.environ, MAX_JOBS='3', CMAKE_BUILD_PARALLEL_LEVEL='3',
               MACOSX_DEPLOYMENT_TARGET='13.0', USE_CUDA='0', USE_MPS='0',
               USE_DISTRIBUTED='0', BUILD_TEST='0', USE_KINETO='0',
               USE_OPENMP='0', USE_MKLDNN='0', USE_FBGEMM='0', USE_NNPACK='0',
               USE_QNNPACK='0', USE_PYTORCH_QNNPACK='0', USE_XNNPACK='0',
               USE_FFMPEG='0', BUILD_SOX='0', TORCHVISION_USE_FFMPEG='0',
               TORCHVISION_USE_VIDEO_CODEC='0', FORCE_CUDA='0')
    records = []
    for name, (repo, commit, version) in SOURCES.items():
        source = root / '.build' / repo
        source.mkdir(parents=True, exist_ok=True)
        run('git', 'init', str(source))
        run('git', 'fetch', '--depth=1', f'https://github.com/pytorch/{repo}.git', commit, cwd=source)
        run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=source)
        run('git', 'submodule', 'update', '--init', '--recursive', '--depth=1', cwd=source)
        build_env = dict(env, BUILD_VERSION=version+'+ssui.cpu',
                         PYTORCH_BUILD_VERSION=version+'+ssui.cpu', PYTORCH_BUILD_NUMBER='1')
        run(sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
            '.', '--wheel-dir', str(output), cwd=source, env=build_env)
        wheel = next(output.glob(name+'-*.whl'))
        if name == 'torchvision':
            # Vendor image-codec dylibs instead of depending on the runner's Homebrew.
            repaired = root / '.build' / 'repaired'
            run('delocate-wheel', '--require-archs', 'x86_64', '-w', str(repaired), str(wheel))
            wheel.unlink()
            shutil.move(str(next(repaired.glob('*.whl'))), output)
            wheel = next(output.glob(name+'-*.whl'))
        run(sys.executable, '-m', 'pip', 'install', '--no-deps', str(wheel))
        records.append(dict(name=name, version=version+'+ssui.cpu', source=commit,
                            filename=wheel.name, sha256=hashlib.sha256(wheel.read_bytes()).hexdigest()))
    run(sys.executable, '-c', "import torch,torchvision,torchaudio; assert torch.arange(4).sum().item()==6; assert torchvision.ops.nms(torch.tensor([[0.,0.,1.,1.]]),torch.tensor([.9]),.5).tolist()==[0]; assert torchaudio.functional.resample(torch.zeros(1,160),16000,8000).shape==(1,80)")
    (output / 'manifest.json').write_text(json.dumps(dict(target='macos-x86_64',
        python=platform.python_version(), wheels=records), indent=2)+'\n')


if __name__ == '__main__':
    main()
