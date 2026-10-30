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
BUILD_ENV = dict(MAX_JOBS='3', CMAKE_BUILD_PARALLEL_LEVEL='3',
    MACOSX_DEPLOYMENT_TARGET='13.0', USE_CUDA='0', USE_MPS='0',
    USE_DISTRIBUTED='1', USE_GLOO='1', USE_MPI='0', USE_NCCL='0', BUILD_TEST='0', USE_KINETO='0',
    USE_OPENMP='0', USE_MKLDNN='0', USE_FBGEMM='0', USE_NNPACK='0',
    USE_QNNPACK='0', USE_PYTORCH_QNNPACK='0', USE_XNNPACK='0',
    USE_FFMPEG='0', BUILD_SOX='0', TORCHVISION_USE_FFMPEG='0',
    TORCHVISION_USE_VIDEO_CODEC='0', FORCE_CUDA='0')


def restore_torch_checkpoint(root, output):
    """Recover the completed Torch wheel from a later packaging failure, by hash."""
    checkpoint = json.loads((root / 'dependencies/macos-torch-checkpoint.json').read_text())
    recipe = dict(source=SOURCES['torch'], environment=BUILD_ENV, python=platform.python_version())
    fingerprint = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
    if fingerprint != checkpoint['recipe'] or os.environ.get('GITHUB_REPOSITORY') != checkpoint['repository']:
        return False
    directory = root / '.build' / 'torch-checkpoint'
    try:
        run('gh', 'run', 'download', str(checkpoint['run']), '--repo', checkpoint['repository'],
            '--name', 'macos-intel-wheels', '--dir', str(directory))
        wheel = directory / checkpoint['filename']
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != checkpoint['sha256']:
            raise RuntimeError('Torch checkpoint checksum mismatch')
        shutil.copy2(wheel, output / wheel.name)
        print('Recovered completed native Torch wheel with pinned recipe and SHA256', flush=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('Torch checkpoint unavailable; building from pinned source', flush=True)
        return False


def run(*args, cwd=None, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main():
    if sys.platform != 'darwin' or platform.machine() != 'x86_64':
        raise RuntimeError('requires native Intel macOS Python')
    root = Path.cwd()
    output = root / 'native-wheels'
    output.mkdir(exist_ok=True)
    env = dict(os.environ, **BUILD_ENV)
    restored_torch = restore_torch_checkpoint(root, output)
    records = []
    for name, (repo, commit, version) in SOURCES.items():
        source = root / '.build' / repo
        source.mkdir(parents=True, exist_ok=True)
        if name != 'torch' or not restored_torch:
            run('git', 'init', str(source))
            run('git', 'fetch', '--depth=1', f'https://github.com/pytorch/{repo}.git', commit, cwd=source)
            run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=source)
            run('git', 'submodule', 'update', '--init', '--recursive', '--depth=1', cwd=source)
            build_env = dict(env, BUILD_VERSION=version+'+ssui.cpu',
                             PYTORCH_BUILD_VERSION=version+'+ssui.cpu', PYTORCH_BUILD_NUMBER='1')
            run(sys.executable, '-m', 'pip', 'wheel', '--verbose', '--no-deps', '--no-build-isolation',
                '.', '--wheel-dir', str(output), cwd=source, env=build_env)
        wheel = next(output.glob(name+'-*.whl'))
        if name == 'torchvision':
            # Vendor image-codec dylibs instead of depending on the runner's Homebrew.
            repaired = root / '.build' / 'repaired'
            import torch
            repair_env = dict(env, DYLD_LIBRARY_PATH=str(Path(torch.__file__).parent / 'lib'))
            run('delocate-wheel', '--require-archs', 'x86_64', '--exclude', '/torch/lib/', '-w', str(repaired), str(wheel), env=repair_env)
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
