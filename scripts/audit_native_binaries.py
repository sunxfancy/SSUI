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
        alternative = relative in PORTAUDIO_ALTERNATIVES
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
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(dict(libraries=records, failures=failures,
        portaudio=loaded.name), indent=2)+'\n')
    if failures:
        raise ValueError('non-native DLL/PYD: ' + '; '.join(failures))
    print(f'Verified {len(records)} DLL/PYD files; unused PortAudio alternatives recorded separately')


if __name__ == '__main__':
    main()
