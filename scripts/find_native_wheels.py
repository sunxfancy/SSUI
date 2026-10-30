"""Reuse successful same-recipe builds from this repository, never fork artifacts."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True).strip()


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    recipe = 'scripts/build_macos_intel_wheels.py'
    expected = subprocess.check_output(['git', 'hash-object', recipe], text=True).strip()
    runs = json.loads(gh('api', f'repos/{repo}/actions/workflows/macos-intel-wheels.yml/runs?status=success&per_page=20'))['workflow_runs']
    reused = False
    for run in runs:
        if run.get('head_repository', {}).get('full_name') != repo or run['event'] not in ('push', 'workflow_dispatch', 'release'):
            continue
        try:
            blob = gh('api', f'repos/{repo}/contents/{recipe}?ref={run["head_sha"]}', '--jq', '.sha')
            if blob != expected:
                continue
            output = Path('native-wheels')
            if output.exists():
                shutil.rmtree(output)
            gh('run', 'download', str(run['id']), '--name', 'macos-intel-wheels', '--dir', str(output))
            subprocess.run(['node', 'dependencies/native_wheels.cjs', str(output)], check=True)
            print('Reused verified native wheels from run', run['id'])
            reused = True
            break
        except subprocess.CalledProcessError:
            continue
    if not reused and Path('native-wheels').exists():
        shutil.rmtree('native-wheels')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as file:
        file.write(f'reused={str(reused).lower()}\n')


if __name__ == '__main__':
    main()
