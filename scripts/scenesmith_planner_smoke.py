"""Real local Qwen planner acceptance for native scene backend."""

import json
import os
from pathlib import Path
import sys

import trimesh

from backend.scenesmith import generate_scene, asset_catalog, plan_with_local_llm
from ssui.base import Prompt
from ss_executor.loader import SSLoader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions/3D-Model"))
output = ROOT / ".build/scenesmith-planner-smoke"
assets = output / "assets"
assets.mkdir(parents=True, exist_ok=True)
trimesh.creation.box(extents=(2, 1, 1)).export(assets / "table.glb")
trimesh.creation.box(extents=(0.5, 0.5, 1)).export(assets / "chair.glb")
(assets / "table.json").write_text(json.dumps({"tags": ["桌子"]}, ensure_ascii=False), encoding="utf-8")
(assets / "chair.json").write_text(json.dumps({"tags": ["椅子"]}, ensure_ascii=False), encoding="utf-8")
python = Path(os.environ.get("SSUI_SCENESMITH_TEST_PYTHON", ROOT / ".build/cuda-arm64-venv/Scripts/python.exe"))
model = Path(os.environ.get("SSUI_SCENESMITH_TEST_MODEL", ROOT / ".build/arm64-models/qwen"))
prompt = "用 table 和 chair 摆一个小场景，椅子放在桌子的左边。"
spec = plan_with_local_llm(prompt, asset_catalog(assets), output, python, model)
glb = generate_scene(prompt, assets, output, spec)
loaded = trimesh.load(glb, force="scene")
spec_path = output / "planner-spec.json"
spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
os.environ["SSUI_SCENE_ASSETS"] = str(assets)
os.environ["SSUI_SCENE_SPEC"] = str(spec_path)
loader = SSLoader()
loader.load(str(ROOT / "examples/advance/workflow-scenesmith.py"))
loader.Execute()
loader.GetConfig("scenesmith_scene")
loader.config.set_prepared(False)
workflow = next(fn for fn, _, _ in loader.callables if fn.__name__ == "scenesmith_scene")
workflow_result = workflow(Prompt(prompt))
workflow_scene = trimesh.load(workflow_result.path, force="scene")
report = {"spec": spec, "mesh_count": len(loaded.geometry), "glb": str(glb),
          "workflow_glb": workflow_result.path, "workflow_mesh_count": len(workflow_scene.geometry)}
(output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
if len(loaded.geometry) < 2 or len(workflow_scene.geometry) != len(loaded.geometry):
    raise RuntimeError("Planner did not create both table and chair")
positions = {item["asset"]: item["position"] for item in json.loads((output / "scene.json").read_text(encoding="utf-8"))["objects"]}
if not positions["chair"][0] < positions["table"][0]:
    raise RuntimeError("Planner violated left-of relation")
print(json.dumps({"mesh_count": len(loaded.geometry), "report": str(output / "report.json")}, ensure_ascii=False))
