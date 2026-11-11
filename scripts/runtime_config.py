"""Release defaults from the canonical OS/architecture/backend registry."""
import json
from pathlib import Path


def runtime_for(target_id):
    registry = json.loads((Path(__file__).resolve().parents[1] / 'dependencies/runtime-targets.json').read_text())
    os_name, arch = target_id.rsplit('-', 1)
    arch = 'x64' if arch == 'x86_64' else arch
    backend = ('mps' if arch == 'arm64' else 'cpu') if os_name == 'macos' else ('cpu' if arch == 'arm64' else 'cuda')
    profile = next(p for p in registry['profiles'] if (p['os'], p['arch'], p['backend']) == (os_name, arch, backend))
    python = registry['python'] | profile.get('python', {})
    return dict(pythonVersion=python['version'], pythonRelease=python['release'],
                pythonTarget=registry['triples'][os_name][arch], lockFile=profile['dependencyTarget']+'.lock')
