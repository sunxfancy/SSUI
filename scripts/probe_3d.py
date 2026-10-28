"""Exercise Pixal3D GPU primitives without downloading model weights."""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extensions/3D-Model"))
sys.path.insert(0, str(ROOT / "extensions/3D-Model/vendor"))
# Keep native build caches in the workspace unless explicitly configured.
os.environ.setdefault("TORCH_EXTENSIONS_DIR", str(ROOT / ".build/torch-extensions"))

import torch


def check_imports():
    from pixal3d.pipelines import Pixal3DImageTo3DPipeline
    from pixal3d.trainers.flow_matching.mixins.image_conditioned_proj import DinoV3ProjFeatureExtractor
    from ssui_3dmodel.Trellis import TrellisModel


def check_attention():
    from pixal3d.modules.attention import scaled_dot_product_attention
    from pixal3d.modules.sparse import VarLenTensor
    from pixal3d.modules.sparse.attention import sparse_scaled_dot_product_attention

    q = torch.randn(1, 8, 2, 16, device="cuda")
    expected = torch.nn.functional.scaled_dot_product_attention(
        q.transpose(1, 2), q.transpose(1, 2), q.transpose(1, 2),
    ).transpose(1, 2)
    torch.testing.assert_close(scaled_dot_product_attention(q, q, q), expected)
    sparse = VarLenTensor(q[0], [slice(0, 8)])
    actual = sparse_scaled_dot_product_attention(sparse, sparse, sparse)
    torch.testing.assert_close(actual.feats, expected[0])


def check_sparse_convolution():
    from pixal3d.modules.sparse import SparseTensor, SparseConv3d

    coords = torch.tensor(
        [[0, x, y, z] for x in range(2) for y in range(2) for z in range(2)],
        dtype=torch.int32, device="cuda",
    )
    feats = torch.randn(8, 16, device="cuda")
    layer = SparseConv3d(16, 16, 3).cuda().eval()
    with torch.no_grad():
        actual = layer(SparseTensor(feats, coords)).feats
        dense = feats.reshape(2, 2, 2, 16).permute(3, 0, 1, 2).unsqueeze(0)
        expected = torch.nn.functional.conv3d(
            dense, layer.weight.permute(0, 4, 1, 2, 3), layer.bias, padding=1,
        )[0].permute(1, 2, 3, 0).reshape(8, 16)
    torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)

    # Force multiple tiny chunks and verify missing-neighbor handling against
    # the same dense convolution, independently of the normal memory budget.
    from pixal3d.modules.sparse.conv.conv_flex_gemm import chunked_explicit_conv
    from flex_gemm.ops.spconv.submanifold_conv3d import SubMConv3dFunction
    with torch.no_grad():
        cache = SubMConv3dFunction._compute_neighbor_cache(coords, torch.Size([1, 16, 2, 2, 2]), (3, 3, 3), (1, 1, 1), False)
        chunked = chunked_explicit_conv(feats, cache["neighbor_map"], layer.weight, layer.bias, max_buffer_bytes=1)
    torch.testing.assert_close(chunked, expected, rtol=1e-4, atol=1e-5)


def check_mesh():
    import cumesh

    mesh = cumesh.CuMesh()
    vertices = torch.tensor([[0, 0, 0], [1, 0, 0], [0, 1, 0]], device="cuda", dtype=torch.float32)
    faces = torch.tensor([[0, 1, 2]], device="cuda", dtype=torch.int32)
    mesh.init(vertices, faces)
    actual_vertices, actual_faces = mesh.read()
    torch.testing.assert_close(actual_vertices, vertices)
    torch.testing.assert_close(actual_faces, faces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from ssui_3dmodel.runtime import check_rasterizer

    report = {
        "torch": torch.__version__, "hip": torch.version.hip,
        "cuda": torch.version.cuda, "gpu": None,
        "scope": "GPU primitives only; no model generation or GLB validation",
        "checks": {},
    }
    if torch.cuda.is_available():
        report["gpu"] = torch.cuda.get_device_name(0)
    checks = {"pipeline_import": check_imports, "attention": check_attention,
              "sparse_convolution": check_sparse_convolution,
              "mesh": check_mesh, "rasterizer": check_rasterizer}
    for name, check in checks.items():
        try:
            check()
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            report["checks"][name] = {"passed": True}
        except Exception as exc:
            report["checks"][name] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        print(f"{name}: {report['checks'][name]}", flush=True)
    report["passed"] = all(item["passed"] for item in report["checks"].values())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
