"""Compare installed native CUDA rigging operators against PyTorch references."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import importlib.metadata
import platform

ROOT = Path(__file__).resolve().parents[1]


def check(names):
    import torch
    import torch.nn.functional as F
    assert torch.cuda.is_available()
    checks = {}
    if "pyg" in names:
        import torch_cluster
        import torch_scatter
        x = torch.tensor([[0., 0, 0], [1., 0, 0], [2., 0, 0], [3., 0, 0]], device="cuda")
        torch.testing.assert_close(torch_cluster.fps(x, ratio=.5, random_start=False), torch.tensor([0, 3], device="cuda"))
        data = torch.arange(18., device="cuda").reshape(6, 3)
        ptr = torch.tensor([0, 2, 6], device="cuda")
        for reduce in ("sum", "min", "max"):
            actual = torch_scatter.segment_csr(data, ptr, reduce=reduce)
            reference = torch.stack([getattr(part, reduce)(dim=0).values if reduce != "sum" else part.sum(0) for part in (data[:2], data[2:])])
            torch.testing.assert_close(actual, reference)
        checks["pyg_fps_and_segment_csr"] = "passed"
    if "pytorch3d" in names:
        from pytorch3d.ops import knn_points
        from pytorch3d.transforms import Translate
        x, y = torch.randn(1, 16, 3, device="cuda"), torch.randn(1, 20, 3, device="cuda")
        result = knn_points(x, y, K=1)
        distances, indices = torch.cdist(x, y).square().min(dim=-1)
        torch.testing.assert_close(result.dists[..., 0], distances, rtol=2e-4, atol=2e-5)
        torch.testing.assert_close(result.idx[..., 0], indices)
        torch.testing.assert_close(Translate(1, 2, 3, device="cuda").transform_points(x), x + torch.tensor([1, 2, 3], device="cuda"))
        checks["pytorch3d_native_knn_and_transforms"] = "passed"
    if "flash-attn" in names:
        from flash_attn import flash_attn_qkvpacked_func
        qkv = torch.randn(2, 16, 3, 2, 32, device="cuda", dtype=torch.float16)
        q, k, v = qkv.unbind(2)
        expected = F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)).transpose(1, 2)
        torch.testing.assert_close(flash_attn_qkvpacked_func(qkv), expected, rtol=4e-3, atol=4e-3)
        checks["flash_attention_native_forward"] = "passed"
    if "spconv" in names:
        import spconv.pytorch as spconv
        coordinates = torch.tensor([[0, 1, 1, 1], [0, 1, 1, 2], [0, 2, 2, 2]], device="cuda", dtype=torch.int32)
        features = torch.arange(3., device="cuda")[:, None]
        layer = spconv.SubMConv3d(1, 1, 3, bias=False).cuda()
        layer.weight.data.fill_(1)
        output = layer(spconv.SparseConvTensor(features, coordinates, [4, 4, 4], 1)).features
        dense = torch.zeros(1, 1, 4, 4, 4)
        for coord, feat in zip(coordinates.cpu(), features.cpu()):
            dense[0, 0, coord[1], coord[2], coord[3]] = feat[0]
        expected_dense = F.conv3d(dense, torch.ones(1, 1, 3, 3, 3), padding=1)
        expected = torch.stack([expected_dense[0, 0, c[1], c[2], c[3]] for c in coordinates.cpu()]).reshape(-1, 1).cuda()
        torch.testing.assert_close(output, expected)
        checks["spconv_native_sparse_convolution"] = "passed"
    if "pyrender" in names:
        import numpy as np
        import pyrender
        scene = pyrender.Scene()
        scene.add(pyrender.Mesh(primitives=[pyrender.Primitive(
            positions=np.array([[-.5, -.5, 0], [.5, -.5, 0], [0, .5, 0]], dtype=np.float32),
            indices=np.array([0, 1, 2], dtype=np.uint32), mode=pyrender.GLTF.TRIANGLES)]))
        pose = np.eye(4)
        pose[2, 3] = 2
        scene.add(pyrender.OrthographicCamera(xmag=1, ymag=1, znear=.05, zfar=4), pose=pose)
        renderer = pyrender.OffscreenRenderer(32, 32)
        try:
            depth = renderer.render(scene, flags=pyrender.RenderFlags.DEPTH_ONLY)
            raw_depth = float(depth[16, 16])
            assert raw_depth > 0, "No rendered triangle depth"
            # pyrender 0.1.45 linearizes orthographic depth as perspective.
            # UniRig explicitly reverses that conversion before voxelization.
            recovered = .05 + 4 - (.05 * 4) / raw_depth
            assert abs(recovered - 2) < 1e-3, "Incorrect UniRig orthographic depth"
        finally:
            renderer.delete()
        checks["pyrender_native_offscreen_depth"] = "passed"
    packages = {}
    for name in ("torch-cluster", "torch-scatter", "pytorch3d", "flash-attn", "cumm", "spconv", "bpy", "transformers", "gradio", "pyrender", "freetype-py", "pyglet"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return dict(torch=torch.__version__, cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(),
                python=sys.version.split()[0], architecture=platform.machine(), packages=packages, checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/rigging/unirig/Scripts/python.exe")
    parser.add_argument("--ops", nargs="+", choices=("pyg", "pytorch3d", "flash-attn", "spconv", "pyrender"), default=["pyg", "pytorch3d", "flash-attn", "spconv", "pyrender"])
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / ".build/rigging-cuda/operator-report.json")
    args = parser.parse_args()
    if not args.worker:
        subprocess.run([str(args.python), str(Path(__file__).resolve()), "--worker", "--ops", *args.ops, "--report", str(args.report)], check=True)
        return
    result = check(args.ops)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
