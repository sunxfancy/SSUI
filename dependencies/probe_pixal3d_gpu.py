"""Exercise Pixal3D's GPU operators without downloading model weights."""
import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import torch


def cuda_tensor():
    if not torch.cuda.is_available():
        raise RuntimeError("A working CUDA/ROCm PyTorch environment is required")
    x = torch.eye(16, device="cuda")
    torch.testing.assert_close(x @ x, x)


def flex_gemm():
    from flex_gemm.ops.grid_sample import grid_sample_3d

    feats = torch.tensor([[2.0, 3.0]], device="cuda")
    coords = torch.tensor([[0, 0, 0, 0]], dtype=torch.int32, device="cuda")
    grid = torch.zeros((1, 1, 3), device="cuda")
    result = grid_sample_3d(feats, coords, torch.Size([1, 2, 2, 2, 2]), grid, mode="nearest")
    torch.testing.assert_close(result, feats.reshape(1, 1, 2))


def cumesh():
    from cumesh import CuMesh

    vertices = torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]], device="cuda")
    faces = torch.tensor([[0, 1, 2]], device="cuda", dtype=torch.int32)
    mesh = CuMesh()
    mesh.init(vertices, faces)
    if mesh.num_vertices != 3 or mesh.num_faces != 1:
        raise RuntimeError("CuMesh lost triangle geometry")


def sparse_convolution():
    from flex_gemm.ops.spconv import sparse_submanifold_conv3d
    from flex_gemm.kernels.triton.spconv import config

    # Compare full FP32 arithmetic; default TF32 intentionally trades precision.
    config.allow_tf32 = False
    torch.manual_seed(7)
    coords = torch.cartesian_prod(torch.arange(1), torch.arange(4), torch.arange(4), torch.arange(4))
    coords = coords.to(device="cuda", dtype=torch.int32).contiguous()
    feats = torch.randn((64, 8), device="cuda")
    weight = torch.randn((8, 3, 3, 3, 8), device="cuda")
    dense = feats.reshape(1, 4, 4, 4, 8).permute(0, 4, 1, 2, 3).contiguous()
    expected = torch.nn.functional.conv3d(dense.cpu().double(), weight.permute(0, 4, 1, 2, 3).cpu().double(), padding=1)
    expected = expected.permute(0, 2, 3, 4, 1).reshape(64, 8).to(feats)
    # Check both initial autotuning and reuse against a dense reference.
    outputs = []
    for _ in range(2):
        result, _ = sparse_submanifold_conv3d(feats, coords, torch.Size([1, 8, 4, 4, 4]), weight)
        torch.testing.assert_close(result, expected, rtol=2e-3, atol=2e-3)
        outputs.append(result)
    torch.testing.assert_close(outputs[0], outputs[1], rtol=0, atol=0)


def nvdiffrast():
    import nvdiffrast.torch as dr

    vertices = torch.tensor([[[-.8, -.8, 0., 1.], [.8, -.8, 0., 1.], [0., .8, 0., 1.]]], device="cuda")
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int32, device="cuda")
    raster, _ = dr.rasterize(dr.RasterizeCudaContext(), vertices, faces, resolution=[16, 16])
    if not bool((raster[..., 3] > 0).any()):
        raise RuntimeError("CUDA rasterizer produced no triangle pixels")


def natten():
    from natten import na2d

    q = torch.zeros((1, 9, 9, 2, 32), device="cuda", dtype=torch.float16)
    v = torch.ones_like(q)
    result = na2d(q, q, v, kernel_size=(3, 3), backend="cutlass-fna")
    torch.testing.assert_close(result, v)


def o_voxel():
    from o_voxel.serialize import encode_seq, decode_seq

    coords = torch.tensor([[0, 0, 0], [1, 2, 3], [7, 5, 2]], device="cuda", dtype=torch.int32)
    torch.testing.assert_close(decode_seq(encode_seq(coords)), coords)


def opencv():
    import cv2
    import numpy as np

    image = np.full((8, 8, 3), 127, dtype=np.uint8)
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[3, 3] = 255
    result = cv2.inpaint(image, mask, 1, cv2.INPAINT_TELEA)
    if result.shape != image.shape:
        raise RuntimeError("OpenCV texture inpainting returned invalid dimensions")


def masked_preprocess():
    from PIL import Image, ImageDraw

    vendor = Path(__file__).resolve().parents[1] / "extensions/3D-Model/vendor"
    sys.path.insert(0, str(vendor))
    from pixal3d.pipelines import Pixal3DImageTo3DPipeline

    pipeline = Pixal3DImageTo3DPipeline()
    pipeline.rembg_model = None
    # This deliberately invalid name proves masked input does not load segmentation.
    pipeline._rembg_config = {"name": "MustNotLoad", "args": {}}
    image = Image.new("RGBA", (64, 64))
    ImageDraw.Draw(image).rectangle((16, 16, 48, 48), fill=(180, 90, 30, 255))
    result = pipeline.preprocess_image(image)
    if result.mode != "RGB" or max(result.size) < 1 or pipeline.rembg_model is not None:
        raise RuntimeError("Masked preprocessing lost foreground or loaded segmentation")
    try:
        pipeline.preprocess_image(Image.new("RGBA", (32, 32)))
    except ValueError as exc:
        if "no visible foreground" not in str(exc):
            raise
    else:
        raise RuntimeError("Empty foreground was accepted")


CHECKS = {fn.__name__: fn for fn in (cuda_tensor, flex_gemm, sparse_convolution, cumesh, nvdiffrast, natten, o_voxel, opencv, masked_preprocess)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", choices=CHECKS, action="append")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = {"python": platform.python_version(), "machine": platform.machine(),
              "torch": torch.__version__, "cuda": torch.version.cuda, "hip": torch.version.hip,
              "checks": {}, "packages": {}}
    if torch.cuda.is_available():
        report.update(gpu=torch.cuda.get_device_name(0), capability=list(torch.cuda.get_device_capability(0)))
    for name in ("torch", "torchvision", "flex-gemm", "cumesh", "nvdiffrast", "natten", "o-voxel", "triton-windows", "opencv-python-headless"):
        try:
            report["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    for name in args.check or CHECKS:
        try:
            CHECKS[name]()
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            report["checks"][name] = {"status": "passed"}
        except Exception as exc:
            report["checks"][name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        print(f"{name}: {report['checks'][name]}", flush=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if all(value["status"] == "passed" for value in report["checks"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
