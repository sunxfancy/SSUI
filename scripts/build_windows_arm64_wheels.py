"""Build source-only Python dependencies on native Windows ARM64, never on x64.

The resulting complete wheelhouse is installed in a fresh environment before it
is accepted. Source-built wheels are separately bundled with the desktop app so
end users do not need MSVC, Rust, CMake or VTK build tools.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, *, cwd=ROOT, env=None):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def require_native():
    if sys.platform != 'win32' or sysconfig.get_platform() != 'win-arm64':
        raise RuntimeError('requires native Windows ARM64 Python (no x64 emulation)')
    if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'arm64':
        raise RuntimeError('activate the ARM64 MSVC developer environment first')


def checkout(recipe, path):
    if not (path / '.git').exists():
        path.mkdir(parents=True, exist_ok=True)
        run(['git', 'init', path])
        run(['git', 'remote', 'add', 'origin', recipe['repository']], cwd=path)
    run(['git', 'fetch', '--depth', '1', 'origin', recipe['commit']], cwd=path)
    run(['git', 'checkout', '--detach', recipe['commit']], cwd=path)
    run(['git', 'submodule', 'update', '--init', '--recursive', '--depth', '1'], cwd=path)


def verify_wheel(path):
    from packaging.utils import parse_wheel_filename
    _, _, _, tags = parse_wheel_filename(path.name)
    if any(t.platform not in ('any', 'win_arm64') for t in tags):
        raise ValueError(f'foreign wheel tag: {path.name}')
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(('.dll', '.pyd')):
                continue
            data = archive.read(member)
            if data[:2] != b'MZ' or len(data) < 64:
                raise ValueError(f'invalid PE in {path.name}: {member}')
            offset = struct.unpack_from('<I', data, 0x3c)[0]
            if data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0xaa64:
                raise ValueError(f'non-ARM64 runtime binary in {path.name}: {member}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    require_native()
    work, output = a.work.resolve(), a.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    recipes = json.loads((ROOT / 'dependencies/windows-arm64-sources.json').read_text())
    lock = ROOT / 'dependencies/windows-arm64.lock'
    env = os.environ.copy()
    env.update(CMAKE_BUILD_PARALLEL_LEVEL='2', MAX_JOBS='2', USE_CUDA='0', USE_ROCM='0',
               FORCE_CUDA='0', BUILD_CUDA_CTC_DECODER='0', USE_OPENMP='0', DISTUTILS_USE_SDK='1')
    run([sys.executable, '-m', 'pip', 'install', 'pip==25.3', 'setuptools==80.9.0',
         'wheel==0.45.1', 'packaging==24.1', 'build==1.3.0', 'cmake==3.31.8',
         'ninja==1.13.0', 'delvewheel==1.11.2', 'numpy==2.2.6', 'cython==3.1.2', 'pybind11==2.13.6'])
    requirements = [l.strip() for l in lock.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    torch = next(r for r in requirements if r.startswith('torch @'))
    run([sys.executable, '-m', 'pip', 'install', torch])

    # Native image/audio libraries used by source builds; their DLLs are repaired into wheels.
    vcpkg = work / 'vcpkg'
    checkout(recipes['vcpkg'], vcpkg)
    run(['cmd', '/c', str(vcpkg / 'bootstrap-vcpkg.bat'), '-disableMetrics'], cwd=vcpkg, env=env)
    run([vcpkg / 'vcpkg.exe', 'install', 'libjpeg-turbo:arm64-windows', 'libpng:arm64-windows',
         'libwebp:arm64-windows', 'libsndfile:arm64-windows'], cwd=vcpkg, env=env)
    prefix = vcpkg / 'installed/arm64-windows'
    env['PATH'] = str(prefix / 'bin') + os.pathsep + env['PATH']
    env['INCLUDE'] = str(prefix / 'include') + os.pathsep + env.get('INCLUDE', '')
    env['LIB'] = str(prefix / 'lib') + os.pathsep + env.get('LIB', '')
    env['TORCHVISION_INCLUDE'] = str(prefix / 'include')
    env['TORCHVISION_LIBRARY'] = str(prefix / 'lib')
    bundled = output / 'bundled'
    bundled.mkdir(exist_ok=True)
    wheelhouse = output / 'wheelhouse'
    wheelhouse.mkdir(exist_ok=True)

    for name in ('vtk', 'torchvision', 'torchaudio'):
        source = work / name
        checkout(recipes[name], source)
        target = work / f'{name}-wheels'
        target.mkdir(exist_ok=True)
        build_env = dict(env, BUILD_VERSION=recipes[name]['version'])
        if name == 'vtk':
            build = work / 'vtk-build'
            run(['cmake', '-S', source, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
                 '-DVTK_WHEEL_BUILD=ON', '-DVTK_WRAP_PYTHON=ON', '-DVTK_BUILD_TESTING=OFF',
                 '-DVTK_VERSION_SUFFIX=', '-DVTK_GROUP_ENABLE_Qt=NO', '-DVTK_USE_TK=OFF',
                 f'-DPython3_EXECUTABLE={sys.executable}', f'-DPython_EXECUTABLE={sys.executable}'], env=build_env)
            run(['cmake', '--build', build, '--parallel', '2'], env=build_env)
            run([sys.executable, 'setup.py', 'bdist_wheel', '--dist-dir', target], cwd=build, env=build_env)
        else:
            run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                 '--wheel-dir', target, source], env=build_env)
        wheels = list(target.glob('*.whl'))
        if len(wheels) != 1:
            raise ValueError(f'expected one {name} wheel, got {wheels}')
        run([sys.executable, '-m', 'delvewheel', 'repair', '--add-path', prefix / 'bin',
             '--wheel-dir', bundled, wheels[0]], env=env)
        built = list(bundled.glob(name + '-*.whl'))
        if len(built) != 1:
            raise ValueError(f'expected one repaired {name} wheel')
        run([sys.executable, '-m', 'pip', 'install', '--no-deps', built[0]], env=env)

    # Discover missing wheels using native pip tags. Never substitute win_amd64 files.
    from packaging.requirements import Requirement
    source_names = set(recipes) - {'vcpkg'}
    for requirement in requirements:
        parsed = Requirement(requirement)
        if parsed.name in source_names:
            continue
        result = subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
                                 '--no-deps', '--dest', str(wheelhouse), requirement], env=env)
        if result.returncode:
            temp = work / 'package-wheels' / parsed.name
            temp.mkdir(parents=True, exist_ok=True)
            run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--wheel-dir', temp, requirement], env=env)
            for wheel in temp.glob('*.whl'):
                run([sys.executable, '-m', 'delvewheel', 'repair', '--add-path', prefix / 'bin',
                     '--wheel-dir', bundled, wheel], env=env)
    for wheel in bundled.glob('*.whl'):
        shutil.copy2(wheel, wheelhouse / wheel.name)
    for wheel in wheelhouse.glob('*.whl'):
        verify_wheel(wheel)
    # Convert source/direct references into pins for an offline, clean consumer install.
    from packaging.utils import canonicalize_name, parse_wheel_filename
    versions = {}
    for wheel in wheelhouse.glob('*.whl'):
        name, version, _, _ = parse_wheel_filename(wheel.name)
        key = canonicalize_name(name)
        if key in versions and versions[key] != str(version):
            raise ValueError(f'ambiguous wheel versions: {key}')
        versions[key] = str(version)
    offline_lock = output / 'requirements.txt'
    offline_lock.write_text(''.join(f'{name}=={version}\n' for name, version in sorted(versions.items())))
    # pip must resolve ALL locked requirements from the native wheelhouse, not just import a subset.
    runtime_lock = output / 'runtime.lock'
    runtime_lock.write_text('\n'.join(str(Requirement(r).name) + '==' + versions[canonicalize_name(Requirement(r).name)] for r in requirements) + '\n')
    clean = work / 'consumer'
    run([sys.executable, '-m', 'venv', clean])
    python = clean / 'Scripts/python.exe'
    run([python, '-m', 'pip', 'install', '--no-index', '--only-binary=:all:', '--find-links', wheelhouse, '-r', runtime_lock])
    run([python, '-m', 'pip', 'check'])
    run([python, ROOT / 'scripts/check_runtime.py', '--target', 'windows-arm64'])
    run([python, ROOT / 'scripts/check_windows_arm64_extensions.py'])
    manifest = dict(python=platform.python_version(), architecture=sysconfig.get_platform(), sources=recipes,
                    lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest(),
                    wheels={f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(wheelhouse.glob('*.whl'))})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('All native wheels built, audited and installed in a clean environment.')


if __name__ == '__main__':
    main()
