"""Render the local SceneSmith planner scene in native Blender."""

import json
from pathlib import Path

from PIL import Image

from backend.scenesmith_blender import render_scene_preview


root = Path(__file__).resolve().parents[1]
scene = root / ".build/scenesmith-planner-smoke/scene.glb"
if not scene.is_file():
    raise FileNotFoundError(f"Run yarn test:scenesmith:planner first: {scene}")
output = root / ".build/scenesmith-blender-smoke"
preview, blend = render_scene_preview(scene, output)
with Image.open(preview) as image:
    image.verify()
with Image.open(preview) as image:
    if image.size != (640, 480):
        raise RuntimeError(f"Unexpected preview dimensions: {image.size}")
if blend.stat().st_size < 1024:
    raise RuntimeError("Blender scene output is incomplete")
print(json.dumps({"preview": str(preview), "blend": str(blend),
                  "preview_bytes": preview.stat().st_size,
                  "blend_bytes": blend.stat().st_size}))
