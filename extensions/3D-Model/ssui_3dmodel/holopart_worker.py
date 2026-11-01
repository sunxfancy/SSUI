"""Run actual HoloPart weights on a native Windows HIP GPU; no CPU fallback."""
import argparse
import json
import sys
import time
from pathlib import Path


def run(args):
    import numpy as np
    import torch
    import trimesh
    if sys.platform != 'win32' or not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError('HoloPart requires native Windows ROCm PyTorch')
    sys.path.insert(0, str(args.root))
    from scripts.inference_holopart import prepare_data, run_holopart
    from holopart.pipelines.pipeline_holopart import HoloPartPipeline
    start = time.monotonic()
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.reset_peak_memory_stats()
    scene = trimesh.load(args.source, force='scene', process=False)
    # Bake scene transforms before normalizing the full shape as one object.
    parts = list(scene.dump())
    if not parts or any(not len(p.faces) or not np.isfinite(p.vertices).all() for p in parts):
        raise ValueError('Completion requires finite, nonempty segmented meshes')
    bounds = scene.bounds
    center = bounds.mean(axis=0)
    scale = float((bounds[1] - bounds[0]).max() / 1.8)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid input scale')
    normalized = trimesh.Scene()
    names = []
    for index, part in enumerate(parts):
        name = f'part_{index:03d}'
        names.append(name)
        part.vertices = (part.vertices - center) / scale
        normalized.add_geometry(part, node_name=name, geom_name=name)
    normalized.export(str(args.output / 'normalized.glb'))
    print('Loading HoloPart weights', flush=True)
    pipe = HoloPartPipeline.from_pretrained(str(args.weights), local_files_only=True).to('cuda', torch.float16)
    batch = prepare_data(str(args.output / 'normalized.glb'), device='cuda')
    print(f'Completing {len(parts)} parts on {torch.cuda.get_device_name()}', flush=True)
    completed = run_holopart(pipe, batch, batch_size=1, seed=args.seed,
        num_inference_steps=args.steps, flash_octree_depth=args.depth, device='cuda')
    if len(completed.geometry) != len(parts):
        raise RuntimeError('HoloPart lost parts')
    report_parts = []
    for index, geometry in enumerate(completed.geometry.values()):
        if not len(geometry.faces) or not np.isfinite(geometry.vertices).all():
            raise RuntimeError(f'Invalid completed part {index}')
        geometry.vertices = geometry.vertices * scale + center
        report_parts.append({'name': names[index], 'faces': len(geometry.faces),
            'watertight': bool(geometry.is_watertight), 'components': len(geometry.split(only_watertight=False))})
    completed.export(str(args.output / 'completed.glb'))
    from holopart_geometry import prepare
    preparation = prepare(args.output)
    torch.cuda.synchronize()
    import diso, torch_cluster
    report = {'input_parts': len(parts), 'output_parts': len(completed.geometry),
        'steps': args.steps, 'seed': args.seed, 'octree_depth': args.depth,
        'normalization': {'center': center.tolist(), 'scale': scale}, 'parts': report_parts,
        'seconds': time.monotonic() - start, 'preparation': preparation,
        'runtime': {'backend': 'native-rocm', 'torch': torch.__version__, 'hip': torch.version.hip,
            'device_name': torch.cuda.get_device_name(), 'peak_gpu_bytes': torch.cuda.max_memory_allocated(),
            'diso': diso.__file__, 'torch_cluster': torch_cluster.__file__}}
    (args.output / 'completion.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'weights', 'source', 'output'):
        parser.add_argument(key, type=Path)
    parser.add_argument('--steps', type=int, default=50)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--depth', type=int, default=8)
    run(parser.parse_args())
