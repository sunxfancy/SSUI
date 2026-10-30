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
    endpoint = f'repos/{repo}/actions/workflows/macos-intel-wheels.yml/runs'
    active = json.loads(gh('api', endpoint+'?status=in_progress&per_page=20'))['workflow_runs']
    for run in active:
        if run['id'] >= int(os.environ['GITHUB_RUN_ID']) or (run.get('head_repository') or {}).get('full_name') != repo:
            continue
        blob = gh('api', f'repos/{repo}/contents/{recipe}?ref={run["head_sha"]}', '--jq', '.sha')
        if blob == expected:
            print('Waiting for the already running native build', run['id'], flush=True)
            subprocess.run(['gh', 'run', 'watch', str(run['id']), '--interval', '60'])
            break
    artifacts = json.loads(gh('api', f'repos/{repo}/actions/artifacts?name=macos-intel-wheels&per_page=100'))['artifacts']
    reused = False
    workflows = {'.github/workflows/macos-intel-wheels.yml',
                 '.github/workflows/windows-arm64-wheels.yml', '.github/workflows/release.yml'}
    for artifact in artifacts:
        if artifact['expired']:
            continue
        run = json.loads(gh('api', f'repos/{repo}/actions/runs/{artifact["workflow_run"]["id"]}'))
        if (run['conclusion'] != 'success' or run['path'] not in workflows or
                (run.get('head_repository') or {}).get('full_name') != repo):
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
