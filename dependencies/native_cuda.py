"""Install and launch the tested Linux NVIDIA native stack without system changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

RESOURCES = Path(__file__).resolve().parent
ROOT = RESOURCES.parent


def runtime_env(root, prefix, env=None):
    env = dict(os.environ if env is None else env)
    python_root = Path(sys.executable).parent.parent
    cache = Path(env.get('SSUI_NATIVE_CACHE', root / '.venv/native-cuda/cache'))
    env.update(CUDA_HOME=str(prefix), CC=str(prefix / 'bin/x86_64-conda-linux-gnu-cc'),
               CXX=str(prefix / 'bin/x86_64-conda-linux-gnu-c++'),
               CONDA_BUILD_SYSROOT=str(prefix / 'x86_64-conda-linux-gnu/sysroot'),
               TORCH_EXTENSIONS_DIR=str(cache / 'torch-extensions'),
               TMPDIR=str(cache / 'tmp'), MAX_JOBS=env.get('MAX_JOBS', '1'))
    env['PATH'] = os.pathsep.join([str(prefix / 'bin'), str(python_root / 'bin'), env.get('PATH', '')])
    headers = [prefix / 'targets/x86_64-linux/include']
    headers.extend(python_root.glob('lib/python*/site-packages/nvidia/*/include'))
    includes = os.pathsep.join(str(p) for p in headers if p.is_dir())
    for key in ('CPATH', 'CPLUS_INCLUDE_PATH'):
        env[key] = includes + (os.pathsep + env[key] if env.get(key) else '')
    for path in (cache / 'tmp', cache / 'torch-extensions'):
        path.mkdir(parents=True, exist_ok=True)
    return env


def supported():
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        return False
    import torch
    return torch.cuda.is_available() and torch.version.cuda is not None


def check_installed_pins(filename):
    from importlib.metadata import version
    from packaging.requirements import Requirement
    for raw in filename.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', '--')):
            continue
        if line.startswith('-r '):
            check_installed_pins(filename.parent / line[3:].strip())
            continue
        requirement = Requirement(line)
        installed = version(requirement.name)
        if requirement.specifier and not requirement.specifier.contains(installed, prereleases=True):
            raise RuntimeError(f'{requirement.name} {installed} does not match {requirement.specifier}; reinstall the native model stack')


def verify():
    check_installed_pins(RESOURCES / 'requirements-native-cuda-linux.txt')
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    import torch
    import nvdiffrast.torch as dr
    import diff_gaussian_rasterization
    import kaolin
    import spconv.pytorch
    import bitsandbytes
    if not torch.cuda.is_available():
        raise RuntimeError('NVIDIA CUDA is not available; check nvidia-smi and driver first')
    context = dr.RasterizeCudaContext()
    vertices = torch.tensor([[[-.7, -.7, 0, 1], [.7, -.7, 0, 1], [0, .7, 0, 1]]],
                            device='cuda', requires_grad=True)
    faces = torch.tensor([[0, 1, 2]], device='cuda', dtype=torch.int32)
    raster, _ = dr.rasterize(context, vertices, faces, resolution=[16, 16])
    raster.sum().backward()
    assert torch.isfinite(vertices.grad).all() and vertices.grad.abs().sum() > 0
    print('NATIVE_CUDA_FORWARD_BACKWARD_PASS', flush=True)


def install(root, required=False):
    if not supported():
        if required:
            raise RuntimeError('Native CUDA setup requires Linux x86_64 and a working NVIDIA CUDA driver')
        print('Native NVIDIA stack not applicable to this machine; base install retained', flush=True)
        return
    import torch
    if sys.version_info[:2] != (3, 12) or not torch.__version__.startswith('2.4.1') or torch.version.cuda != '12.4':
        raise RuntimeError('Tested native stack requires Python 3.12 / torch 2.4.1+cu124; install the Linux lock first')
    base = root / '.venv/native-cuda'
    base.mkdir(parents=True, exist_ok=True)
    marker = base / 'runtime.json'
    fingerprint = hashlib.sha256(b'linux-native-v2' + b''.join((RESOURCES / name).read_bytes() for name in
        ('native-cuda-linux.explicit.txt', 'requirements-native-cuda-linux.txt', 'requirements-motion.txt'))).hexdigest()
    try:
        previous = json.loads(marker.read_text()) if marker.exists() else {}
    except (ValueError, OSError):
        previous = {}
    if previous.get('fingerprint') == fingerprint and (Path(previous.get('prefix', '')) / 'bin/nvcc').is_file():
        checked = subprocess.run([sys.executable, str(RESOURCES / 'native_cuda.py'), '--root', str(root), 'doctor'])
        if checked.returncode == 0:
            return
        print('Native check failed; reinstalling the pinned stack', flush=True)
    # Build into a distinct prefix; a failed upgrade keeps the old runtime usable.
    prefix_base = Path(os.environ['SSUI_NATIVE_CACHE']) / 'toolchains' if os.environ.get('SSUI_NATIVE_CACHE') else base
    toolchain_id = hashlib.sha256((RESOURCES / 'native-cuda-linux.explicit.txt').read_bytes()).hexdigest()[:12]
    prefix = prefix_base / ('env-' + toolchain_id)
    env = dict(os.environ)
    cache = Path(env.get('SSUI_NATIVE_CACHE', base / 'cache'))
    temp = cache / 'tmp'
    temp.mkdir(parents=True, exist_ok=True)
    env.update(TMPDIR=str(temp), MAMBA_ROOT_PREFIX=str(cache / 'mamba'))
    mamba = base / 'bin/micromamba'
    if not mamba.exists():
        # Extract only the executable; never extract arbitrary archive paths.
        url = 'https://micro.mamba.pm/api/micromamba/linux-64/2.10.0'
        with tempfile.TemporaryDirectory(dir=temp) as folder:
            archive = Path(folder) / 'micromamba.tar.bz2'
            with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            with tarfile.open(archive) as bundle:
                member = bundle.getmember('bin/micromamba')
                if not member.isfile():
                    raise RuntimeError('Invalid micromamba executable')
                mamba.parent.mkdir(parents=True, exist_ok=True)
                staged_mamba = mamba.with_suffix('.tmp')
                staged_mamba.write_bytes(bundle.extractfile(member).read())
                staged_mamba.chmod(0o755)
                if subprocess.check_output([str(staged_mamba), '--version'], text=True).strip() != '2.10.0':
                    raise RuntimeError('Invalid micromamba version')
                os.replace(staged_mamba, mamba)
    version = subprocess.check_output([str(mamba), '--version'], text=True).strip()
    if version != '2.10.0':
        raise RuntimeError(f'Unexpected micromamba version: {version}')
    if not (prefix / 'bin/nvcc').is_file() or not (prefix / 'bin/x86_64-conda-linux-gnu-c++').is_file():
        subprocess.run([str(mamba), 'create', '-y', '-p', str(prefix), '-f',
                        str(RESOURCES / 'native-cuda-linux.explicit.txt')], env=env, check=True)
    env = runtime_env(root, prefix, env)
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'ninja', 'wheel', 'setuptools==69.5.1'], env=env, check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-build-isolation', '-r',
                    str(RESOURCES / 'requirements-native-cuda-linux.txt')], env=env, check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], env=env, check=True)
    subprocess.run([sys.executable, str(RESOURCES / 'native_cuda.py'), 'verify'], env=env, check=True)
    temp_marker = marker.with_suffix('.tmp')
    temp_marker.write_text(json.dumps({'fingerprint': fingerprint, 'prefix': str(prefix)}, indent=2))
    os.replace(temp_marker, marker)
    print('Linux native CUDA installation verified', flush=True)


def launch_env(root):
    marker = root / '.venv/native-cuda/runtime.json'
    if sys.platform != 'linux' or not marker.exists():
        return dict(os.environ)
    try:
        prefix = Path(json.loads(marker.read_text())['prefix'])
    except (ValueError, KeyError):
        print('Native CUDA metadata is invalid; run .venv/bin/python dependencies/native_cuda.py install --required', file=sys.stderr)
        return dict(os.environ)
    if not (prefix / 'bin/nvcc').is_file():
        print('Native CUDA compiler is missing; run .venv/bin/python dependencies/native_cuda.py install --required', file=sys.stderr)
        return dict(os.environ)
    return runtime_env(root, prefix)


def use_space_free_python(root, args):
    """Torch 2.4's compiler/linker commands cannot quote every venv path.

    Keep user files in place, but launch Python through a stable private alias;
    build sources/toolchains use a physical cache path without whitespace.
    """
    if sys.platform != 'linux' or not any(c.isspace() for c in str(root)):
        return
    if not (root / '.venv/bin/python').exists():
        return
    cache = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')).absolute()
    if any(c.isspace() for c in str(cache)):
        cache = Path('/tmp') / ('ssui-native-' + str(os.getuid()))
    aliases = cache / 'ssui-native-roots'
    aliases.mkdir(parents=True, mode=0o700, exist_ok=True)
    if aliases.stat().st_uid != os.getuid():
        raise RuntimeError('Native alias cache is not owned by this user')
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    alias = aliases / key
    if alias.is_symlink():
        if alias.resolve() != root.resolve():
            raise RuntimeError('Native alias points to a different installation')
    elif alias.exists():
        raise RuntimeError('Native alias path is already occupied')
    else:
        alias.symlink_to(root, target_is_directory=True)
    env = dict(os.environ, SSUI_NATIVE_CACHE=str(aliases / (key + '-cache')))
    command = list(args.command)
    # exec must preserve the alias when the caller supplied the real Python path.
    offset = 1 if command[:1] == ['--'] else 0
    if args.action == 'exec' and len(command) > offset and command[offset].startswith(str(root) + os.sep):
        command[offset] = str(alias) + command[offset][len(str(root)):]
    python = str(alias / '.venv/bin/python')
    os.execve(python, [python, str(RESOURCES / 'native_cuda.py'), '--root', str(alias),
                      args.action, *command], env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('action', choices=['install', 'doctor', 'verify', 'exec'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.root.absolute()
    use_space_free_python(root, args)
    if args.action == 'install':
        install(root, required='--required' in args.command)
    elif args.action == 'verify':
        verify()
    elif args.action == 'doctor':
        if not (root / '.venv/native-cuda/runtime.json').is_file():
            raise RuntimeError('Native CUDA is not installed; run yarn install:native')
        metadata = json.loads((root / '.venv/native-cuda/runtime.json').read_text())
        if not (Path(metadata.get('prefix', '')) / 'bin/nvcc').is_file():
            raise RuntimeError('Managed CUDA compiler missing; run .venv/bin/python dependencies/native_cuda.py install --required')
        subprocess.run([sys.executable, str(RESOURCES / 'native_cuda.py'), 'verify'], env=launch_env(root), check=True)
    else:
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not command:
            parser.error('exec requires a command after --')
        repairing = len(command) > 2 and Path(command[1]).name == 'native_cuda.py' and 'install' in command[2:]
        os.execvpe(command[0], command, dict(os.environ) if repairing else launch_env(root))


if __name__ == '__main__':
    main()
