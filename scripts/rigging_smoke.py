"""Run real auto-rigging on a local mesh and validate a native skinned GLB."""
import argparse
import json
from pathlib import Path
import sys
import time
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extensions/3D-Model"))
from ssui.base import Mesh
from ssui_3dmodel.AutoRig import AutoRigModel, validate_rigged_glb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("unirig", "mia", "riganything"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-faces", type=int, default=8192)
    parser.add_argument("--verify-deformation", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"Input does not exist: {args.input}")
    start = time.monotonic()
    mesh = Mesh(path=str(args.input.resolve())) if args.input.suffix.lower() == ".glb" else Mesh.load(str(args.input))
    model = AutoRigModel.load_local(args.model)
    result = model.rig(mesh, args.seed, args.target_faces)
    doc = validate_rigged_glb(result.path)
    report = {"model": args.model, "input": str(args.input.resolve()), "output": result.path,
              "elapsed_seconds": time.monotonic() - start, "skins": len(doc["skins"]),
              "joints": [len(skin["joints"]) for skin in doc["skins"]]}
    if args.verify_deformation:
        verify = ROOT / "extensions/3D-Model/ssui_3dmodel/_verify_rig.py"
        subprocess.run([model.python, str(verify), result.path], check=True)
        report["deformation"] = json.loads(Path(result.path).with_suffix(".deformation.json").read_text(encoding="utf-8"))
    path = Path(result.path).with_suffix(".report.json")
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
