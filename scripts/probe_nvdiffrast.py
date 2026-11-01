"""Native rasterization/interpolation/texture/gradient validation on the active GPU."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--module-path", type=Path)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
if args.module_path:
    sys.path.insert(0, str(args.module_path.resolve()))

import torch
import nvdiffrast.torch as dr

report = {"torch": torch.__version__, "hip": torch.version.hip,
          "device": torch.cuda.get_device_name(0), "module": dr.__file__, "checks": []}
ctx = dr.RasterizeCudaContext()
for size in (16, 64, 256):
    pos = torch.tensor([[[-0.75, -0.75, 0, 1], [0.75, -0.75, 0, 1],
                         [0, 0.75, 0, 1]]], device="cuda", dtype=torch.float32, requires_grad=True)
    tri = torch.tensor([[0, 1, 2]], device="cuda", dtype=torch.int32)
    rast, db = dr.rasterize(ctx, pos, tri, resolution=[size, size])
    covered = rast[..., 3] > 0
    count = covered.sum().item()
    # Triangle area is 28.125% of the viewport; permit edge-rule rounding.
    assert abs(count - size * size * 0.28125) <= 2 * size, (size, count)
    attr = torch.tensor([[[1., 0, 0], [0, 1., 0], [0, 0, 1.]]], device="cuda", requires_grad=True)
    color, _ = dr.interpolate(attr, rast, tri)
    torch.testing.assert_close(color[covered].sum(-1), torch.ones(count, device="cuda"))
    assert torch.isfinite(db).all()
    aa = dr.antialias(color, rast, pos, tri)
    loss = aa.square().sum()
    loss.backward()
    assert torch.isfinite(pos.grad).all() and pos.grad.abs().sum() > 0
    assert torch.isfinite(attr.grad).all() and attr.grad.abs().sum() > 0
    report["checks"].append({"resolution": size, "covered": count, "gradient_finite": True})

tex = torch.ones((1, 4, 4, 3), device="cuda", requires_grad=True)
uv = torch.full((1, 8, 8, 2), 0.5, device="cuda")
sample = dr.texture(tex, uv, filter_mode="linear")
torch.testing.assert_close(sample, torch.ones_like(sample))
sample.sum().backward()
assert torch.isfinite(tex.grad).all() and tex.grad.abs().sum() > 0
torch.cuda.synchronize()
report["texture"] = True
report["passed"] = True
print(json.dumps(report, indent=2))
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
