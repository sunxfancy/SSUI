"""Host-side runtime settings and portable subprocess logging."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def runtime_settings(engine):
    # Optional machine-local deployment settings. Environment variables win.
    path = ROOT / '.build/motion-runtimes.json'
    if path.is_file():
        return json.loads(path.read_text(encoding='utf-8')).get(engine, {})
    return {}


def runtime_environment(engine):
    return {**runtime_settings(engine).get('env', {}), **os.environ, 'PYTHONIOENCODING': 'utf-8'}


def runtime_python(engine):
    key = engine.upper().replace('-', '_')
    configured = os.environ.get(f'SSUI_{key}_PYTHON') or runtime_settings(engine).get('python')
    if configured:
        return str(configured)
    return str(ROOT / '.venv' / engine / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))


def print_runtime_line(line):
    encoding = sys.stdout.encoding or 'utf-8'
    print(line.encode(encoding, errors='replace').decode(encoding), end='')
