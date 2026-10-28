"""Run real image-to-3D models through SSUI HTTP, scheduler and GPU executor."""
import argparse
import hashlib
import io
import json
import time
from pathlib import Path

import requests
import trimesh
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://localhost:7422")
    parser.add_argument("--engine", choices=["pixal3d", "trellis2", "trellis"], default="pixal3d")
    parser.add_argument("--model", required=True, help="Local model snapshot with pipeline.json")
    parser.add_argument("--no-remesh", action="store_true", help="Export the decoded surface without remeshing")
    parser.add_argument("--export-mode", choices=["vertex_colors", "pbr_texture", "gaussian_texture"])
    parser.add_argument("--image", required=True, help="An actual object image, not a blank test image")
    parser.add_argument("--output", required=True, help="Directory for GLB and validation report")
    args = parser.parse_args()
    supported_exports = {"pixal3d": (), "trellis": ("vertex_colors", "gaussian_texture"),
                         "trellis2": ("vertex_colors", "pbr_texture")}
    if args.export_mode and args.export_mode not in supported_exports[args.engine]:
        parser.error(f"Unsupported export mode for {args.engine}: {args.export_mode}")
    if args.no_remesh and args.engine != "trellis2":
        parser.error("--no-remesh is only supported by TRELLIS.2")
    model = Path(args.model).resolve()
    image = Path(args.image).resolve()
    if not (model / "pipeline.json").is_file() or not image.is_file():
        parser.error("--model must contain pipeline.json and --image must exist")

    def api(method, route, **kwargs):
        response = requests.request(method, args.server.rstrip("/") + route, timeout=7200, **kwargs)
        response.raise_for_status()
        value = response.json()
        if isinstance(value, dict) and "error" in value:
            raise RuntimeError(value["error"])
        return value

    device = api("GET", "/api/device")
    # /api/device returns the GPU's display name, rather than "cuda:0".
    if device == "cpu":
        raise RuntimeError(f"Expected a GPU service, got {device}")
    engines = {
        "pixal3d": ("pixal3d", "img2mesh_pixal3d", "Pixal3D.Pixal3DModel", "Generate Pixal3D Model"),
        "trellis2": ("trellis2", "img2mesh_trellis2", "Trellis2.Trellis2Model", "Generate TRELLIS.2 Model"),
        "trellis": ("trellis", "img2mesh_trellis", "Trellis.TrellisModel", "Generate TRELLIS Model"),
    }
    example, function, model_type, node = engines[args.engine]
    script = str(ROOT / f"examples/advance/workflow-{example}.py")
    functions = api("GET", "/api/script", params={"script_path": script})["functions"]
    if function not in functions:
        raise RuntimeError(f"Workflow discovery failed: {functions}")
    query = {"script_path": script, "callable": function}
    api("POST", "/api/prepare", params=query)
    started = time.monotonic()
    results = api("POST", "/api/execute", params=query, json={
        "params": {
            "model": {"function": f"ssui_3dmodel.{model_type}.load", "params": {"model_path": str(model), **({"low_vram": True} if args.engine != "trellis" else {})}},
            "image": {"function": "ssui_3dmodel.Pixal3D.LoadPixal3DImage", "params": {"path": str(image)}},
        },
        "details": {node: {"auto_camera": False, "fov_degrees": 30, "resolution": 1024, "seed": 42,
                           **({"remesh": False} if args.no_remesh else {}),
                           **({"export_mode": args.export_mode} if args.export_mode else {})}},
    })
    if len(results) != 1 or results[0].get("type") != "mesh":
        raise RuntimeError(f"Expected one mesh result, got {results}")
    response = requests.get(args.server.rstrip("/") + "/file", params={"path": results[0]["path"]}, timeout=120)
    response.raise_for_status()
    data = response.content
    scene = trimesh.load(io.BytesIO(data), file_type="glb", force="scene")
    vertices = sum(len(geometry.vertices) for geometry in scene.geometry.values())
    faces = sum(len(geometry.faces) for geometry in scene.geometry.values())
    if vertices < 3 or faces < 1 or data[:4] != b"glTF":
        raise RuntimeError("Output is not a non-empty GLB mesh")
    for geometry in scene.geometry.values():
        if not np.isfinite(geometry.vertices).all():
            raise RuntimeError("Output contains non-finite mesh vertices")
        if geometry.faces.min() < 0 or geometry.faces.max() >= len(geometry.vertices):
            raise RuntimeError("Output contains invalid triangle indices")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "mesh.glb").write_bytes(data)
    report = {"status": "passed", "engine": args.engine, "device": device, "version": api("GET", "/api/version"),
              "seconds": round(time.monotonic() - started, 3), "vertices": vertices, "faces": faces,
              "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
              "input_sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
