"""Weight-free checks for the native operations used by Pixal3D."""

import torch
import sys


def check_large_mesh_copy():
    """Small meshes miss Windows HIP's >2^20-row copy truncation."""
    import cumesh
    count = 1048577
    vertices = torch.arange(count * 3, dtype=torch.float32, device='cuda').reshape(-1, 3)
    faces = (torch.arange(count * 3, dtype=torch.int32, device='cuda') % count).reshape(-1, 3)
    mesh = cumesh.CuMesh()
    mesh.init(vertices, faces)
    actual_vertices, actual_faces = mesh.read()
    if not torch.equal(vertices, actual_vertices) or not torch.equal(faces, actual_faces):
        raise RuntimeError('CuMesh corrupts large meshes; install the bounded-copy ROCm build and run yarn probe:cumesh.')


def check_rasterizer():
    """Importing nvdiffrast alone does not load or exercise its native plugin."""
    import nvdiffrast.torch as dr

    context = dr.RasterizeCudaContext()
    vertices = torch.tensor(
        [[[-0.5, -0.5, 0, 1], [0.5, -0.5, 0, 1], [0, 0.5, 0, 1]]],
        dtype=torch.float32, device="cuda",
    )
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int32, device="cuda")
    raster, _ = dr.rasterize(context, vertices, faces, resolution=[16, 16])
    if not (raster[..., 3] > 0).any().item():
        raise RuntimeError("Rasterizer produced no triangle coverage.")


def require_glb_runtime():
    """Fail before downloading/loading weights if textured export cannot work."""
    try:
        import o_voxel.postprocess  # noqa: F401
        import cumesh  # noqa: F401
        check_rasterizer()
        if sys.platform == 'win32' and torch.version.hip:
            check_large_mesh_copy()
    except Exception as exc:
        backend = "ROCm" if torch.version.hip else "CUDA"
        raise RuntimeError(
            f"Pixal3D textured GLB export is unavailable on this {backend} runtime. "
            "Install matching o_voxel, CuMesh and nvdiffrast native builds; "
            "an importable Python package is not sufficient. Run yarn probe:3d "
            f"for diagnostics. No model weights have been loaded. Details: {exc}"
        ) from exc
