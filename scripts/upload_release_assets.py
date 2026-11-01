"""Resume candidate uploads without ever replacing an existing asset."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from release_assets import digest


def upload(tag, directory):
    meta = json.loads(subprocess.check_output(['gh', 'release', 'view', tag, '--json', 'isPrerelease,assets'], text=True))
    if not meta['isPrerelease']:
        raise ValueError('cannot upload to a formal release')
    existing = {a['name'] for a in meta['assets']}
    local = {p.name for p in directory.iterdir() if p.is_file()}
    if existing - local:
        raise ValueError(f'unexpected existing assets: {existing - local}')
    with tempfile.TemporaryDirectory() as temp:
        for file in sorted(directory.iterdir()):
            if file.name in existing:
                subprocess.run(['gh', 'release', 'download', tag, '--pattern', file.name, '--dir', temp], check=True)
                if digest(Path(temp) / file.name) != digest(file):
                    raise ValueError(f'asset already exists with different bytes: {file.name}; use a new version')
            else:
                subprocess.run(['gh', 'release', 'upload', tag, str(file)], check=True)


if __name__ == '__main__':
    upload(sys.argv[1], Path(sys.argv[2]))
