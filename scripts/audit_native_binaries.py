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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if sysconfig.get_platform() != 'win-arm64':
        raise RuntimeError('must run in native Windows ARM64 Python')
    root = Path(sysconfig.get_paths()['platlib'])
    records = []
    for file in sorted(root.rglob('*')):
        if file.suffix.lower() not in ('.dll', '.pyd'):
            continue
        data = file.read_bytes()
        machine = pe_machine(data)
        if machine != 0xaa64:
            raise ValueError(f'non-native DLL/PYD: {file.relative_to(root)} machine={machine:#x}')
        records.append(dict(path=str(file.relative_to(root)), machine=hex(machine), sha256=hashlib.sha256(data).hexdigest()))
    if not records:
        raise RuntimeError('no native libraries found')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(records, indent=2)+'\n')
    print(f'Verified {len(records)} native ARM64 DLL/PYD files')


if __name__ == '__main__':
    main()
