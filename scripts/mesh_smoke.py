"""Pinned TripoSR weights -> SSUI workflow -> colored GLB -> reload validation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'extensions/3D-Model'), str(ROOT / 'extensions/3D-Model/vendor')]
REVISION = '5b521936b01fbe1890f6f9baed0254ab6351c04a'
DINO_REVISION = 'f205d5d8e640a89a2b8ef0369670dfc37cc07fc2'
SHA256 = '429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=ROOT / 'tests/fixtures/3d/chair.png')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/3d-mac')
    parser.add_argument('--resolution', type=int, default=64)
    parser.add_argument('--device', choices=['auto', 'mps', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--local-files-only', action='store_true')
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    if not 32 <= args.resolution <= 256:
        parser.error('resolution must be between 32 and 256')
    from huggingface_hub import hf_hub_download
    root = ROOT / 'models/triposr'
    for filename in ('config.yaml', 'model.ckpt'):
        hf_hub_download('stabilityai/TripoSR', filename, revision=REVISION, local_dir=root, local_files_only=args.local_files_only)
    hf_hub_download('facebook/dino-vitb16', 'config.json', revision=DINO_REVISION,
                    local_dir=root / 'dino', local_files_only=args.local_files_only)
    digest = hashlib.sha256()
    with (root / 'model.ckpt').open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != SHA256:
        raise RuntimeError('TripoSR checkpoint checksum mismatch')
    print('TripoSR SHA256 verified', flush=True)
    if args.download_only:
        return
    import numpy as np
    import torch
    import trimesh
    from PIL import Image as PILImage
    from ssui.base import Image
    from backend.util.devices import TorchDevice
    from ss_executor.loader import SSLoader
    TorchDevice.config.device = args.device
    torch.set_num_threads(4)
    started = time.monotonic()
    loader = SSLoader()
    loader.load(str(ROOT / 'examples/advance/workflow-3d-mac.py'))
    loader.Execute()
    loader.GetConfig('img2mesh_mac')
    loader.config.set_prepared(False)
    loader.config('Generate Mesh')['resolution'] = args.resolution
    loader.config('Generate Mesh')['foreground_ratio'] = 0.85
    fn = next(fn for fn, _, _ in loader.callables if fn.__name__ == 'img2mesh_mac')
    mesh = fn(Image(PILImage.open(args.image)))._model
    generated = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / 'mesh.glb'
    mesh.export(path)
    reloaded = trimesh.load(path, force='mesh', process=False)
    if len(reloaded.faces) != len(mesh.faces) or not np.isfinite(reloaded.vertices).all():
        raise RuntimeError('GLB geometry round-trip failed')
    if np.any(mesh.extents <= 0) or reloaded.visual.kind != 'vertex':
        raise RuntimeError('Degenerate mesh or missing vertex colors')
    # Render the exported geometry on CPU, without CUDA/OpenGL requirements.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(12, 4))
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    radius = mesh.extents.max() * 0.55
    colors = mesh.visual.vertex_colors[mesh.faces].mean(axis=1) / 255
    for i, azimuth in enumerate((30, 150, 270)):
        ax = fig.add_subplot(1, 3, i + 1, projection='3d')
        ax.add_collection3d(Poly3DCollection(mesh.vertices[mesh.faces], facecolors=colors, linewidths=0))
        ax.set_xlim(center[0]-radius, center[0]+radius)
        ax.set_ylim(center[1]-radius, center[1]+radius)
        ax.set_zlim(center[2]-radius, center[2]+radius)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=20, azim=azimuth)
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(args.output / 'preview.png', dpi=120)
    plt.close(fig)
    report = {'model': 'stabilityai/TripoSR', 'revision': REVISION, 'sha256': SHA256,
              'dino_revision': DINO_REVISION, 'device': str(TorchDevice.choose_torch_device()),
              'torch': torch.__version__, 'resolution': args.resolution,
              'vertices': len(mesh.vertices), 'faces': len(mesh.faces),
              'watertight': bool(mesh.is_watertight), 'bounds': mesh.bounds.tolist(),
              'generation_seconds': generated-started, 'workflow': 'img2mesh_mac', 'glb': str(path.resolve())}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
