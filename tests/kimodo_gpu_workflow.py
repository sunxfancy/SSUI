"""Exercise actual Kimodo generation through SSUI HTTP and validate motion artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://localhost:7422')
    parser.add_argument('--output', required=True)
    parser.add_argument('--prompt', default='A person walks forward and waves their right hand.')
    parser.add_argument('--duration', type=float, default=4)
    parser.add_argument('--steps', type=int, default=50)
    args = parser.parse_args()
    script = str(Path(__file__).resolve().parents[1] / 'examples/advance/workflow-motion.py')
    def api(method, route, **kwargs):
        response = requests.request(method, args.server.rstrip('/') + route, timeout=1800, **kwargs)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and 'error' in result:
            raise RuntimeError(result['error'])
        return result
    query = {'script_path': script, 'callable': 'txt2motion_kimodo'}
    functions = api('GET', '/api/script', params={'script_path': script})['functions']
    if query['callable'] not in functions:
        raise RuntimeError('Motion workflow was not discovered')
    api('POST', '/api/prepare', params=query)
    started = time.monotonic()
    results = api('POST', '/api/execute', params=query, json={
        'params': {'prompt': {'function': 'ssui.base.Prompt.create', 'params': {'text': args.prompt}}},
        'details': {'Kimodo Text To Motion': {'model': 'Kimodo-SOMA-RP-v1.1', 'duration': args.duration,
            'diffusion_steps': args.steps, 'seed': 42, 'text_encoder_device': 'cuda', 'export_bvh': True}}})
    if len(results) != 1 or results[0].get('type') != 'motion_clip':
        raise RuntimeError(f'Expected a motion clip: {results}')
    result = results[0]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for key, filename in [('path', 'motion.json'), ('npz_path', 'motion.npz'), ('bvh_path', 'motion.bvh')]:
        response = requests.get(args.server.rstrip('/') + '/file', params={'path': result[key]}, timeout=120)
        response.raise_for_status()
        data = response.content
        (output / filename).write_bytes(data)
        hashes[filename] = hashlib.sha256(data).hexdigest()
    manifest = json.loads((output / 'motion.json').read_text(encoding='utf-8'))
    metadata = manifest['metadata']
    if not metadata['inference_device'].startswith('cuda'):
        raise RuntimeError(f'Actual denoiser did not run on GPU: {metadata}')
    with np.load(output / 'motion.npz', allow_pickle=False) as data:
        positions = data['posed_joints']
        rotations = data['local_rot_mats']
        root = data['root_positions']
    if positions.ndim != 3 or positions.shape[1:] != (77, 3) or len(positions) < 2 or not np.isfinite(positions).all():
        raise RuntimeError('Invalid motion geometry')
    np.testing.assert_allclose(positions, np.asarray(manifest['positions']), atol=1e-6)
    np.testing.assert_allclose(rotations @ np.swapaxes(rotations, -1, -2), np.broadcast_to(np.eye(3), rotations.shape), atol=2e-3)
    np.testing.assert_allclose(np.linalg.det(rotations), 1, atol=2e-3)
    if not np.isfinite(rotations).all() or np.max(np.abs(np.diff(positions, axis=0))) < 1e-5:
        raise RuntimeError('Motion is static or non-finite')
    bvh = (output / 'motion.bvh').read_text(encoding='utf-8')
    if f'Frames: {len(positions)}' not in bvh or 'MOTION' not in bvh:
        raise RuntimeError('BVH frame count does not match generated motion')
    frame_time = float(next(line.split(':', 1)[1] for line in bvh.splitlines() if line.startswith('Frame Time:')))
    if not np.isclose(frame_time, 1 / manifest['fps'], atol=1e-6):
        raise RuntimeError('BVH frame rate does not match generated motion')
    report = {'status': 'passed', 'seconds': round(time.monotonic() - started, 3), 'prompt': args.prompt,
        'frames': len(positions), 'joints': positions.shape[1], 'fps': manifest['fps'],
        'duration': len(positions) / manifest['fps'], 'steps': args.steps,
        'root_displacement_m': float(np.linalg.norm(root[-1] - root[0])),
        'inference_device': metadata['inference_device'], 'torch': metadata['torch'], 'cuda': metadata['cuda'],
        'postprocessed': metadata['postprocessed'], 'sha256': hashes}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
