"""Run a real imported model through the SSUI retopology nodes and serializer."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extensions/3D-Model"))

from ssui import Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.Retopology import SegmentParts, QuadRemesh, _read_polygons
from ss_executor.__main__ import convert_task_return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--faces", type=int, default=2000)
    args = parser.parse_args()
    root = Path(os.environ.get("SSUI_3D_OUTPUT", ROOT / "output/retopology-validation")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["SSUI_3D_OUTPUT"] = str(root)
    source = Mesh.load(str(args.input.resolve()))
    script = str(ROOT / "examples/basic/workflow-retopology.py")
    payloads = {"input": convert_task_return(source, script)}
    (root / "preview-payloads.json").write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    start = time.monotonic()
    config = SSUIConfig()
    print("Running real P3-SAM segmentation", flush=True)
    parts = SegmentParts(config("segment"), source)
    segmented_at = time.monotonic()
    payloads["segmented"] = convert_task_return(parts, script)
    (root / "preview-payloads.json").write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    print("Running standalone QuadriFlow on", len(parts._model.geometry), "parts", flush=True)
    config("remesh")["target_faces"] = args.faces
    result = QuadRemesh(config("remesh"), parts)
    payloads["retopology"] = convert_task_return(result, script)
    vertices, polygons = _read_polygons(result.artifacts["retopology.obj"])
    report = json.loads(Path(result.artifacts["report.json"]).read_text())
    assert sum(p["faces"] for p in report["parts"]) == len(polygons)
    assert sum(len(face) == 4 for face in polygons) > 0
    assert all(Path(file).is_file() for file in result.artifacts.values())
    validation = {"input": str(args.input.resolve()), "device": os.environ.get("SSUI_P3SAM_DEVICE", "cuda"),
        "point_num": os.environ.get("SSUI_P3SAM_POINT_NUM", "100000"),
        "prompt_num": os.environ.get("SSUI_P3SAM_PROMPT_NUM", "400"),
        "input_faces": sum(len(m.faces) for m in source._model.geometry.values()),
        "segmented_parts": len(parts._model.geometry), "output_vertices": len(vertices),
        "output_polygons": len(polygons), "quads": sum(len(face) == 4 for face in polygons),
        "segmentation_seconds": segmented_at - start, "total_seconds": time.monotonic() - start,
        "artifacts": result.artifacts}
    (root / "preview-payloads.json").write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    (root / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2), flush=True)


if __name__ == "__main__":
    main()
