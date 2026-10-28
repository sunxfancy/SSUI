"""Run a real SSUI motion workflow and validate its downloadable artifacts."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    'ardy': ('workflow-motion-ardy.py', 'txt2motion_ardy', 'ARDY Text To Motion'),
    'msflow': ('workflow-motion-msflow.py', 'txt2motion_msflow', 'MotionSpaceFlow Text To Motion'),
    'hy-motion': ('workflow-motion-hy.py', 'txt2motion_hy', 'HY-Motion Text To Motion'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', choices=WORKFLOWS)
    parser.add_argument('--prompt', default='A person walks forward and waves their right hand.')
    parser.add_argument('--duration', type=float, default=4)
    parser.add_argument('--device', choices=['cuda', 'cpu', 'auto'], default='cuda')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(ROOT), str(ROOT / 'extensions/Motion')]
    import numpy as np
    from ss_executor.loader import SSLoader
    from ss_executor.__main__ import convert_task_return
    from ssui import MotionClip, Prompt
    filename, callable_name, config_name = WORKFLOWS[args.engine]
    script = ROOT / 'examples/advance' / filename
    loader = SSLoader(use_sandbox=True)
    loader.load(str(script))
    loader.Execute()
    loader.GetConfig(callable_name)
    loader.config.set_prepared(False)
    config = loader.config(config_name)
    for key, value in {'duration': args.duration, 'seed': 42, 'device': args.device}.items():
        config[key] = value
    fn = next(fn for fn, _, _ in loader.callables if fn.__name__ == callable_name)
    started = time.monotonic()
    clip = fn(Prompt(args.prompt))
    elapsed = time.monotonic() - started
    assert isinstance(clip, MotionClip)
    payload = convert_task_return(clip, str(script))
    manifest = json.loads(Path(clip.path).read_text(encoding='utf-8'))
    with np.load(clip.npz_path, allow_pickle=False) as data:
        positions = data['posed_joints']
        rotation_error = None
        if 'local_rot_mats' in data:
            rotations = data['local_rot_mats']
            assert np.isfinite(rotations).all()
            rotation_error = float(np.max(np.abs(rotations @ np.swapaxes(rotations, -1, -2) - np.eye(3))))
            assert rotation_error < 0.01
    assert np.isfinite(positions).all()
    assert positions.shape == (round(args.duration * clip.fps), len(manifest['parents']), 3)
    assert len(manifest['joint_names']) == positions.shape[1]
    assert manifest['parents'].count(-1) == 1
    for index in range(len(manifest['parents'])):
        seen = set()
        while index != -1:
            assert 0 <= index < positions.shape[1] and index not in seen
            seen.add(index)
            index = manifest['parents'][index]
    np.testing.assert_allclose(positions, manifest['positions'], atol=1e-6)
    movement = float(np.max(np.linalg.norm(positions - positions[:1], axis=-1)))
    assert movement > 0.01, 'Motion is static'
    actual_device = manifest['metadata']['inference_device']
    if args.device == 'cuda':
        assert actual_device.startswith('cuda')
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for original, name in ((clip.path, 'motion.motion.json'), (clip.npz_path, 'motion.npz')):
        shutil.copy2(original, destination / name)
    report = {'engine': args.engine, 'workflow': callable_name, 'prompt': args.prompt,
              'seconds': elapsed, 'fps': clip.fps, 'frames': clip.frames, 'joints': positions.shape[1],
              'inference_device': actual_device, 'max_displacement_m': movement,
              'rotation_orthogonality_max_error': rotation_error, 'payload': payload,
              'scope': 'Real weights through SSUI loader and executor serialization; no HTTP/UI or semantic-quality assertion'}
    (destination / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
