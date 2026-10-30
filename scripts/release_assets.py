"""Collect and verify the six immutable desktop release bundles (stdlib only)."""
import argparse
import hashlib
import json
import platform
import re
import shutil
import struct
from pathlib import Path

TARGETS = {f'{os}-{arch}' for os in ('windows', 'macos', 'linux') for arch in ('x86_64', 'arm64')}


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def binary_arch(path):
    data = path.read_bytes()
    if data[:2] == b'MZ':
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        if data[offset:offset+4] != b'PE\0\0':
            raise ValueError('invalid PE signature')
        machine = struct.unpack_from('<H', data, offset+4)[0]
        return {0x8664: 'x86_64', 0xaa64: 'arm64'}[machine]
    if data[:4] == b'\x7fELF' and data[4] == 2:
        machine = struct.unpack_from('<H' if data[5] == 1 else '>H', data, 18)[0]
        return {62: 'x86_64', 183: 'arm64'}[machine]
    if data[:4] == b'\xcf\xfa\xed\xfe':
        return {0x1000007: 'x86_64', 0x100000c: 'arm64'}[struct.unpack_from('<I', data, 4)[0]]
    raise ValueError(f'unsupported executable format: {path}')


def collect(root, output, target, tag, sha, binary):
    expected = target.rsplit('-', 1)[1]
    host = {'AMD64': 'x86_64', 'aarch64': 'arm64', 'ARM64': 'arm64'}.get(platform.machine(), platform.machine())
    if host != expected or binary_arch(binary) != expected:
        raise ValueError('host or executable architecture does not match release target')
    pattern = {'windows': 'nsis/*.exe', 'macos': 'dmg/*.dmg', 'linux': 'deb/*.deb'}[target.split('-')[0]]
    files = sorted(root.glob(pattern))
    if len(files) != 1:
        raise ValueError(f'expected exactly one installer for {target}, found {len(files)}')
    output.mkdir(parents=True, exist_ok=True)
    file = files[0]
    dest = output / f'ssui-{tag}-{target}{file.suffix}'
    shutil.copyfile(file, dest)
    record = dict(target=target, tag=tag, sha=sha, name=dest.name, sha256=digest(dest))
    (output / f'{target}.json').write_text(json.dumps(record, indent=2)+'\n')


def verify(directory, tag, sha):
    records = [json.loads(p.read_text()) for p in directory.glob('*.json') if p.name != 'release-manifest.json']
    if len(records) != 6 or {r['target'] for r in records} != TARGETS:
        raise ValueError('release requires exactly six unique desktop targets')
    for r in records:
        name = r['name']
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('invalid asset name')
        extension = {'windows': '.exe', 'macos': '.dmg', 'linux': '.deb'}[r['target'].split('-')[0]]
        if name != f"ssui-{tag}-{r['target']}{extension}":
            raise ValueError('asset name does not match its release target')
        if r['tag'] != tag or r['sha'] != sha:
            raise ValueError('mixed version or source commits')
        if digest(directory / name) != r['sha256']:
            raise ValueError(f'checksum mismatch: {name}')
    records = sorted(records, key=lambda r: r['target'])
    manifest = directory / 'release-manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != dict(tag=tag, sha=sha, assets=records):
        raise ValueError('published manifest does not match target records')
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['collect', 'verify'])
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--tag', required=True)
    p.add_argument('--sha', required=True)
    p.add_argument('--target', choices=sorted(TARGETS))
    p.add_argument('--bundle', type=Path)
    p.add_argument('--binary', type=Path)
    a = p.parse_args()
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', a.tag) or not re.fullmatch(r'[0-9a-f]{40}', a.sha):
        p.error('expected a semantic version tag and full commit SHA')
    if a.command == 'collect':
        collect(a.bundle, a.directory, a.target, a.tag, a.sha, a.binary)
    else:
        records = verify(a.directory, a.tag, a.sha)
        (a.directory / 'release-manifest.json').write_text(json.dumps(dict(tag=a.tag, sha=a.sha, assets=records), indent=2)+'\n')
        (a.directory / 'SHA256SUMS').write_text(''.join(f"{r['sha256']}  {r['name']}\n" for r in records))


if __name__ == '__main__':
    main()
