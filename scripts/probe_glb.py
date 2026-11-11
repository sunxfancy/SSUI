"""Exercise real ROCm remeshing, UV unwrapping and volume-to-texture GLB export."""
import argparse
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions/3D-Model"))
import numpy as np
import torch
import trimesh
import o_voxel
from ssui_3dmodel.export import to_glb, sample_volume

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("test-artifacts/rocm-export.glb"))
args = parser.parse_args()
# Compare sparse interpolation with dense PyTorch, including missing voxels,
# out-of-bounds samples, two batches and the query chunk boundary.
torch.manual_seed(42)
small = torch.cartesian_prod(torch.arange(2), *[torch.arange(4)] * 3).cuda().int()
small = small[torch.arange(len(small), device="cuda") % 3 != 0]
features = torch.rand((len(small), 3), device="cuda")
queries = torch.rand((2, 65539, 3), device="cuda") * 6 - 1
dense = torch.zeros((2, 3, 4, 4, 4), device="cuda")
b, x, y, z = small.long().unbind(1)
dense[b, :, x, y, z] = features
occupancy = torch.zeros((2, 1, 4, 4, 4), device="cuda")
occupancy[b, 0, x, y, z] = 1
expected = torch.nn.functional.grid_sample(
    dense, (queries[..., [2, 1, 0]] / 2 - 1).reshape(2, 1, 1, -1, 3),
    align_corners=False,
).reshape(2, 3, -1).transpose(1, 2)
# FlexGEMM renormalizes over existing neighbors rather than zero-padding
# their contribution; sample occupancy to obtain the reference denominator.
denominator = torch.nn.functional.grid_sample(
    occupancy, (queries[..., [2, 1, 0]] / 2 - 1).reshape(2, 1, 1, -1, 3),
    align_corners=False,
).reshape(2, 1, -1).transpose(1, 2)
expected = expected / denominator.clamp_min(1e-12)
actual = sample_volume(features, small, dense.shape, queries)
torch.testing.assert_close(actual, expected, atol=1e-6, rtol=1e-5)
print("PASS: sparse HIP sampling matches dense PyTorch across chunk boundaries")
shape = trimesh.creation.icosphere(subdivisions=2, radius=0.3)
grid = 32
coords = torch.cartesian_prod(*[torch.arange(grid, device="cuda")] * 3).int()
attrs = torch.zeros((len(coords), 6), device="cuda")
attrs[:, :3] = coords.float() / (grid - 1)
attrs[:, 4:] = 0.8
mesh = to_glb(
    vertices=torch.tensor(np.asarray(shape.vertices), dtype=torch.float32, device="cuda"),
    faces=torch.tensor(np.asarray(shape.faces), dtype=torch.int32, device="cuda"),
    attr_volume=attrs, coords=coords,
    attr_layout={"base_color": slice(0, 3), "metallic": slice(3, 4),
                 "roughness": slice(4, 5), "alpha": slice(5, 6)},
    aabb=[[-0.5] * 3, [0.5] * 3], grid_size=grid,
    decimation_target=1000, texture_size=256, remesh=True,
    remesh_band=1, remesh_project=0, verbose=True,
)
args.output.parent.mkdir(parents=True, exist_ok=True)
mesh.export(str(args.output), extension_webp=True)
scene = trimesh.load(str(args.output), force="scene")
assert scene.geometry
for geometry in scene.geometry.values():
    assert len(geometry.faces) > 0 and np.isfinite(geometry.vertices).all()
    assert geometry.visual.uv is not None
    texture = np.asarray(geometry.visual.material.baseColorTexture)
    assert texture.shape[:2] == (256, 256) and texture[..., :3].max() > texture[..., :3].min()
print(f"PASS: remesh, UV, textured GLB round trip: {args.output.resolve()}")
