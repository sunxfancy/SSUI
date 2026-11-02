"""Numerical smoke for the actual source-built HoloPart HIP extensions."""
import json
from pathlib import Path
import torch
import torch_cluster
import diso

assert torch.version.hip and torch.cuda.is_available()
torch.manual_seed(42)
x = torch.rand(91, 3, device='cuda')
y = torch.rand(137, 3, device='cuda')
actual = torch_cluster.nearest(x, y)
expected = torch.cdist(x, y).argmin(dim=1)
assert torch.equal(actual, expected), 'HIP nearest disagrees with dense GPU distance'
indices = torch_cluster.fps(x, ratio=0.25, random_start=False)
selected = [0]
distance = torch.full((len(x),), float('inf'), device='cuda')
for _ in range(1, len(indices)):
    distance = torch.minimum(distance, ((x-x[selected[-1]])**2).sum(-1))
    selected.append(int(distance.argmax()))
assert indices.tolist() == selected, 'HIP FPS disagrees with reference'
axis = torch.linspace(-1, 1, 33, device='cuda')
grid = torch.stack(torch.meshgrid(axis, axis, axis, indexing='ij'), -1)
sdf = (grid.norm(dim=-1) - 0.6).contiguous()
vertices, faces = diso.DiffDMC(dtype=torch.float32).cuda()(sdf, return_quads=False, normalize=False)
assert vertices.is_cuda and faces.is_cuda and len(faces) > 0
assert torch.isfinite(vertices).all()
radius = ((vertices / 16 - 1).norm(dim=-1) - 0.6).abs().max().item()
assert radius < 0.02, radius
report = {'device': torch.cuda.get_device_name(), 'hip': torch.version.hip,
    'nearest': 'dense GPU reference matched', 'fps': 'greedy reference matched',
    'dmc_sphere_max_radius_error': radius, 'dmc_faces': len(faces),
    'torch_cluster': torch_cluster.__file__, 'diso': diso.__file__}
output = Path('output/holopart-rocm-validation')
output.mkdir(parents=True, exist_ok=True)
(output / 'kernel-validation.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
