"""Run a real image-to-GLB workflow and retain the exported artifact."""
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extensions/3D-Model"))
sys.path.insert(0, str(ROOT / "extensions/3D-Model/vendor"))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, default=Path("test-artifacts/pixal3d.glb"))
    parser.add_argument("--model", default="TencentARC/Pixal3D")
    parser.add_argument("--fov-degrees", type=float, default=30)
    parser.add_argument("--auto-camera", action="store_true")
    parser.add_argument("--diagnostics", type=Path, help="Retain decoded geometry before remeshing")
    args = parser.parse_args()
    from PIL import Image as PILImage
    from ssui.base import Image
    from ssui.config import SSUIConfig
    from ssui_3dmodel.Pixal3D import Pixal3DModel, GenPixal3DModel
    import trimesh

    source = PILImage.open(args.image)
    source.load()
    started = time.monotonic()
    print("Loading Pixal3D weights", flush=True)
    model = Pixal3DModel.load(args.model, low_vram=True)
    if args.diagnostics:
        args.diagnostics.mkdir(parents=True, exist_ok=True)
        from pixal3d.representations import Mesh as RawMesh
        original_fill_holes = RawMesh.fill_holes
        def capture_fill_holes(raw, *a, **kw):
            import torch
            vertices = raw.vertices.cpu().numpy()
            faces = raw.faces.cpu().numpy()
            print(f"Before fill_holes: {len(vertices)} vertices, {len(faces)} faces, bounds={vertices.min(0)}..{vertices.max(0)}", flush=True)
            trimesh.Trimesh(vertices, faces, process=False).export(args.diagnostics / "before-fill.ply")
            original_fill_holes(raw, *a, **kw)
            print(f"After fill_holes: bounds={raw.vertices.min(0).values}..{raw.vertices.max(0).values}", flush=True)
        RawMesh.fill_holes = capture_fill_holes
        pipeline = model.pipeline
        original_run = pipeline.run
        def capture_run(*a, **kw):
            import json
            import numpy as np
            print(f"Camera: {kw.get('camera_params')}", flush=True)
            result = original_run(*a, **kw)
            generated = result[0][0]
            import torch
            torch.save({
                'vertices': generated.vertices.cpu(), 'faces': generated.faces.cpu(),
                'attrs': generated.attrs.cpu(), 'coords': generated.coords.cpu(),
                'grid_size': result[1][2],
            }, args.diagnostics / 'decoded.pt')
            vertices = generated.vertices.cpu().numpy()
            faces = generated.faces.cpu().numpy()
            trimesh.Trimesh(vertices, faces, process=False).export(args.diagnostics / "decoded.ply")
            np.save(args.diagnostics / "shape-coords.npy", result[1][0].coords.cpu().numpy())
            (args.diagnostics / "run.json").write_text(json.dumps({
                "camera": kw.get('camera_params'), "seed": kw.get('seed'),
                "vertices": len(vertices), "faces": len(faces),
            }, indent=2))
            return result
        pipeline.run = capture_run
    config = SSUIConfig()
    config.set_prepared(False)
    node = config("Generate Pixal3D Model")
    node["auto_camera"] = args.auto_camera
    node["fov_degrees"] = args.fov_degrees
    node["resolution"] = 1024
    print("Generating mesh and textures", flush=True)
    mesh = GenPixal3DModel(node, model, Image(source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mesh._model.export(str(args.output), extension_webp=True)
    scene = trimesh.load(str(args.output), force="scene")
    assert scene.geometry and all(len(g.faces) for g in scene.geometry.values())
    print(f"GLB round trip passed: {args.output.resolve()} ({args.output.stat().st_size} bytes); "
          f"elapsed {time.monotonic() - started:.1f}s", flush=True)

if __name__ == "__main__":
    main()
