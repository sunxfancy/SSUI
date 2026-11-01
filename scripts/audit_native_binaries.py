"""Verify installed extension/runtime libraries are native ARM64 PE binaries."""
import argparse
import hashlib
import json
import struct
import sysconfig
from pathlib import Path


def pe_machine(data):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('invalid PE header')
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if len(data) < offset+6 or data[offset:offset+4] != b'PE\0\0':
        raise ValueError('invalid PE signature')
    return struct.unpack_from('<H', data, offset+4)[0]


# sounddevice's ARM64 wheel also ships unused x86/x64 PortAudio alternatives.
# Its loader chooses libportaudioarm64*.dll on this platform; verify that below.
PORTAUDIO_ALTERNATIVES = {
    f'_sounddevice_data/portaudio-binaries/libportaudio{bits}{asio}.dll'
    for bits in ('32bit', '64bit') for asio in ('', '-asio')
}

# The universal debugpy wheel retains CPython 3.9 accelerators and foreign-process
# injection helpers. CPython 3.12 ARM64 uses pydevd's Python implementation, not
# these files. Exercise its actual debug server and audit loaded extensions too.
DEBUGPY_ALTERNATIVES = {
    'debugpy/_vendored/pydevd/_pydevd_bundle/pydevd_cython.cp39-win_amd64.pyd',
    'debugpy/_vendored/pydevd/_pydevd_frame_eval/pydevd_frame_evaluator.cp39-win_amd64.pyd',
    *(f'debugpy/_vendored/pydevd/pydevd_attach_to_process/{name}_{arch}.dll'
      for name in ('attach', 'run_code_on_dllmain') for arch in ('amd64', 'x86')),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if sysconfig.get_platform() != 'win-arm64':
        raise RuntimeError('must run in native Windows ARM64 Python')
    root = Path(sysconfig.get_paths()['platlib'])
    records, failures = [], []
    for file in sorted(root.rglob('*')):
        if file.suffix.lower() not in ('.dll', '.pyd'):
            continue
        data = file.read_bytes()
        relative = file.relative_to(root).as_posix()
        machine = pe_machine(data)
        alternative = relative in PORTAUDIO_ALTERNATIVES | DEBUGPY_ALTERNATIVES
        if machine != 0xaa64 and not alternative:
            failures.append(f'{relative} machine={machine:#x}')
        records.append(dict(path=relative, machine=hex(machine),
                            unusedPlatformAlternative=alternative,
                            sha256=hashlib.sha256(data).hexdigest()))
    if not records:
        raise RuntimeError('no native libraries found')
    import sounddevice
    loaded = Path(sounddevice._libname)
    if pe_machine(loaded.read_bytes()) != 0xaa64:
        failures.append('sounddevice loaded non-native PortAudio: ' + str(loaded))
    import debugpy
    import sys
    debugpy.listen(('127.0.0.1', 0))
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename and filename.endswith('.pyd') and pe_machine(Path(filename).read_bytes()) != 0xaa64:
            failures.append('loaded non-native extension: ' + filename)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(dict(libraries=records, failures=failures,
        portaudio=loaded.name), indent=2)+'\n')
    if failures:
        raise ValueError('non-native DLL/PYD: ' + '; '.join(failures))
    print(f'Verified {len(records)} DLL/PYD files; unused foreign-platform alternatives recorded separately')


if __name__ == '__main__':
    main()
