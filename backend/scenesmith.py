"""Native asset layout backend inspired by SceneSmith's scene-spec boundary.

The upstream agent and Drake physics solver are not included here.
"""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import numpy as np
import trimesh

from backend.scene_physics import RELATIONS, resolve_translation, separate_static_aabb, transformed_bounds
from backend.scenesmith_preview import render_native_preview

STAGES = ("floor_plan", "furniture", "wall_mounted", "ceiling_mounted", "manipuland")


def _object_stage(item: dict[str, Any]) -> str:
    relation = item.get("relation", "floor")
    inferred = ("wall_mounted" if isinstance(relation, str) and relation.startswith("wall_") else
                "ceiling_mounted" if relation == "ceiling" else
                "manipuland" if relation == "on" else "furniture")
    stage = item.get("stage", inferred)
    if stage not in STAGES[1:]:
        raise ValueError(f"Invalid object stage: {stage}")
    return stage


def asset_catalog(directory: str | Path) -> dict[str, Path]:
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"3D asset directory does not exist: {root}")
    catalog = {path.relative_to(root).with_suffix("").as_posix(): path
               for path in sorted(root.rglob("*.glb")) if path.is_file()}
    if not catalog:
        raise ValueError(f"No GLB assets found in {root}")
    return catalog


def asset_descriptors(catalog: dict[str, Path]) -> list[dict[str, Any]]:
    """Read optional adjacent JSON metadata without importing model runtimes."""
    descriptors = []
    for key, path in catalog.items():
        descriptor = {"id": key, "name": path.stem}
        sidecar = path.with_suffix(".json")
        if sidecar.is_file():
            if sidecar.stat().st_size > 65536:
                raise ValueError(f"Asset metadata is too large: {sidecar}")
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError(f"Asset metadata must be an object: {sidecar}")
            for field in ("description", "category"):
                if field in metadata:
                    value = metadata[field]
                    if not isinstance(value, str) or len(value) > 500:
                        raise ValueError(f"Invalid {field} in {sidecar}")
                    descriptor[field] = value
            if "tags" in metadata:
                tags = metadata["tags"]
                if not isinstance(tags, list) or len(tags) > 32 or any(
                    not isinstance(tag, str) or len(tag) > 80 for tag in tags
                ):
                    raise ValueError(f"Invalid tags in {sidecar}")
                descriptor["tags"] = tags
        descriptors.append(descriptor)
    return descriptors


def offline_plan(prompt: str, catalog: dict[str, Path]) -> dict[str, Any]:
    """Baseline: named assets in a deterministic row, pending a planner model."""
    text = prompt.lower()
    selected = []
    for item in asset_descriptors(catalog):
        aliases = [item["id"], item["name"], item.get("category", ""), *item.get("tags", [])]
        if any(alias and alias.lower() in text for alias in aliases):
            selected.append(item["id"])
    if not selected:
        raise ValueError("Prompt did not name an asset; use an asset ID or provide a scene spec")
    return {"schema": "ssui.scene-layout/1", "objects": [
        {"id": f"object-{index:03d}", "asset": key,
         "position": [float(index * 3), 0.0, 0.0], "rotation_deg": 0.0, "scale": 1.0}
        for index, key in enumerate(selected)]}


def enforce_text_relations(prompt: str, spec: dict[str, Any],
                           catalog: dict[str, Path]) -> dict[str, Any]:
    """Turn explicit pairwise language constraints into ordered scene relations."""
    objects = spec.get("objects")
    if not isinstance(objects, list):
        return spec
    aliases = {}
    for descriptor in asset_descriptors(catalog):
        for alias in [descriptor["id"], descriptor["name"], *descriptor.get("tags", [])]:
            if alias and len(alias) >= 2:
                aliases[alias.lower()] = descriptor["id"]
    choices = sorted(aliases, key=len, reverse=True)
    text = prompt.lower()
    constraints = []
    for subject in choices:
        for target in choices:
            if aliases[subject] == aliases[target]:
                continue
            pattern = (re.escape(subject) + r"\s*(?:放在|摆在|位于|在)?\s*" +
                       re.escape(target) + r"\s*(?:的)?\s*(左边|右边|前面|后面|上面)")
            match = re.search(pattern, text)
            english = None
            if not match:
                english = re.search(
                    re.escape(subject) + r"\s+(?:is\s+)?(?:to\s+the\s+)?"
                    r"(left of|right of|in front of|behind|on top of)\s+" + re.escape(target), text)
            if not match and not english:
                continue
            subject_item = next((item for item in objects if isinstance(item, dict) and item.get("asset") == aliases[subject]), None)
            target_item = next((item for item in objects if isinstance(item, dict) and item.get("asset") == aliases[target]), None)
            if subject_item is None or target_item is None or subject_item is target_item:
                continue
            relation = ({"左边": "left_of", "右边": "right_of", "前面": "front_of",
                         "后面": "behind", "上面": "on"}[match.group(1)] if match else
                        {"left of": "left_of", "right of": "right_of", "in front of": "front_of",
                         "behind": "behind", "on top of": "on"}[english.group(1)])
            if not target_item.get("id"):
                target_item["id"] = f"object-{objects.index(target_item):03d}"
            existing = next((entry for entry in constraints if entry[0] is subject_item), None)
            if existing is not None:
                if existing[1] is target_item and subject_item["relation"] == relation:
                    break
                raise ValueError(f"Conflicting placement relations for {subject_item['asset']}")
            subject_item["relation"] = relation
            subject_item["relative_to"] = target_item.get("id")
            subject_item.pop("position", None)
            constraints.append((subject_item, target_item))
            break
    if constraints:
        ordered = []
        pending = list(objects)
        while pending:
            ready = next((item for item in pending if all(
                subject is not item or target in ordered
                for subject, target in constraints)), None)
            if ready is None:
                raise ValueError("Cyclic placement relations in prompt")
            ordered.append(ready)
            pending.remove(ready)
        objects[:] = ordered
    return spec


def plan_with_local_llm(prompt: str, catalog: dict[str, Path], output_dir: str | Path,
                        python: str | Path, model_path: str | Path) -> dict[str, Any]:
    """Native subprocess keeps GPU model dependencies out of the CPU backend."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    request_path, response_path, log_path = (output / "planner-request.json",
                                             output / "planner-response.txt", output / "planner.log")
    if not Path(python).is_file() or not Path(model_path).is_dir():
        raise RuntimeError("Local planner Python or model directory is missing")
    request_path.write_text(json.dumps({"prompt": prompt, "assets": asset_descriptors(catalog)}, ensure_ascii=False), encoding="utf-8")
    runner = Path(__file__).with_name("scenesmith_llm_runner.py")
    environment = os.environ.copy()
    temp = output / "tmp"
    temp.mkdir(exist_ok=True)
    environment.update(TEMP=str(temp), TMP=str(temp), TRITON_CACHE_DIR=str(output / "triton"),
                       HF_HOME=str(output / "huggingface"), HF_MODULES_CACHE=str(output / "huggingface/modules"),
                       PYTHONUTF8="1", PYTHONIOENCODING="utf-8:replace")
    command = [str(python), str(runner), "--model", str(model_path), "--request", str(request_path),
               "--output", str(response_path)]
    with log_path.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=output, env=environment, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=900,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode or not response_path.is_file():
        raise RuntimeError(f"Local scene planner failed; log: {log_path}")
    response = response_path.read_text(encoding="utf-8")
    try:
        first, last = response.index("{"), response.rindex("}") + 1
        spec = json.loads(response[first:last])
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Local scene planner did not return valid JSON; response: {response_path}") from exc
    if not isinstance(spec, dict):
        raise ValueError("Local scene planner must return a JSON object")
    return enforce_text_relations(prompt, spec, catalog)


def _vector(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must have three numbers")
    result = np.asarray(value, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    return result


def _add_room(scene: trimesh.Scene, room: dict[str, Any]) -> dict[str, Any]:
    """Create an editable floor and walls with optional rectangular openings."""
    size = _vector(room.get("size", [6, 6, 3]), "room.size")
    if np.any(size < 1) or np.any(size > 100):
        raise ValueError("room.size must be between 1 and 100 meters per axis")
    width, depth, height = size
    thickness = 0.1
    openings = room.get("openings", [])
    if not isinstance(openings, list) or len(openings) > 4:
        raise ValueError("room.openings must be a list of at most four openings")
    by_wall = {}
    for opening in openings:
        if not isinstance(opening, dict) or opening.get("wall") not in ("left", "right", "front", "back"):
            raise ValueError("Opening needs a valid wall")
        wall = opening["wall"]
        if wall in by_wall:
            raise ValueError(f"Only one opening per wall is supported: {wall}")
        span = depth if wall in ("left", "right") else width
        center = float(opening.get("center", 0.0))
        opening_width = float(opening.get("width", 1.0))
        bottom = float(opening.get("bottom", 0.0))
        opening_height = float(opening.get("height", 2.0))
        if (not np.isfinite([center, opening_width, bottom, opening_height]).all()
                or opening_width <= 0 or opening_height <= 0 or bottom < 0
                or abs(center) + opening_width / 2 >= span / 2
                or bottom + opening_height > height):
            raise ValueError(f"Opening exceeds wall bounds: {wall}")
        by_wall[wall] = {"wall": wall, "center": center, "width": opening_width,
                         "bottom": bottom, "height": opening_height,
                         "kind": str(opening.get("kind", "door"))}
    parts = {"room.floor": ((width, depth, thickness), (0, 0, -thickness / 2))}
    for wall in ("left", "right", "front", "back"):
        horizontal_x = wall in ("front", "back")
        span = width if horizontal_x else depth
        fixed = (-depth / 2 if wall == "front" else depth / 2) if horizontal_x else (-width / 2 if wall == "left" else width / 2)

        def add_piece(label: str, low: float, high: float, z_low: float, z_high: float) -> None:
            if high - low < 1e-6 or z_high - z_low < 1e-6:
                return
            center = (low + high) / 2
            z_center = (z_low + z_high) / 2
            extents = ((high - low, thickness, z_high - z_low) if horizontal_x
                       else (thickness, high - low, z_high - z_low))
            location = ((center, fixed, z_center) if horizontal_x else (fixed, center, z_center))
            parts[f"room.wall.{wall}.{label}"] = (extents, location)

        opening = by_wall.get(wall)
        if opening is None:
            add_piece("full", -span / 2, span / 2, 0, height)
        else:
            left = opening["center"] - opening["width"] / 2
            right = opening["center"] + opening["width"] / 2
            add_piece("left", -span / 2, left, 0, height)
            add_piece("right", right, span / 2, 0, height)
            add_piece("bottom", left, right, 0, opening["bottom"])
            add_piece("top", left, right, opening["bottom"] + opening["height"], height)
    for name, (extents, center) in parts.items():
        scene.add_geometry(trimesh.creation.box(extents=extents), node_name=name,
                           geom_name=name, transform=trimesh.transformations.translation_matrix(center))
    return {"size": size.tolist(), "openings": list(by_wall.values())}


def build_scene(spec: dict[str, Any], catalog: dict[str, Path]) -> tuple[trimesh.Scene, dict[str, Any]]:
    """Compose exact transforms, preserving separate object nodes in the GLB."""
    if spec.get("schema") != "ssui.scene-layout/1" or not isinstance(spec.get("objects"), list):
        raise ValueError("Expected ssui.scene-layout/1 with an objects array")
    if len(spec["objects"]) > 256 or (not spec["objects"] and "room" not in spec):
        raise ValueError("Scene must contain a room or 1 to 256 objects")
    scene = trimesh.Scene()
    manifest = {"schema": "ssui.scene-layout/1", "objects": []}
    if "room" in spec:
        if not isinstance(spec["room"], dict):
            raise ValueError("room must be an object")
        manifest["room"] = _add_room(scene, spec["room"])
    room_bounds = None
    if "room" in manifest:
        width, depth, height = manifest["room"]["size"]
        room_bounds = np.array([[-width / 2, -depth / 2, 0],
                                [width / 2, depth / 2, height]])
    seen = set()
    placed_bounds = {}
    asset_hashes = {}
    for index, item in enumerate(spec["objects"]):
        if not isinstance(item, dict):
            raise ValueError(f"objects[{index}] must be an object")
        ident = str(item.get("id") or f"object-{index:03d}")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", ident) or ident in seen:
            raise ValueError(f"Invalid or duplicate object ID: {ident}")
        seen.add(ident)
        key = item.get("asset")
        if key not in catalog:
            raise ValueError(f"Unknown asset ID: {key}")
        if key not in asset_hashes:
            with catalog[key].open("rb") as stream:
                asset_hashes[key] = hashlib.file_digest(stream, "sha256").hexdigest()
        if item.get("source_sha256") and item["source_sha256"] != asset_hashes[key]:
            raise ValueError(f"Asset changed since saved scene state: {key}")
        rotation = float(item.get("rotation_deg", 0.0))
        scale = float(item.get("scale", 1.0))
        if not np.isfinite(rotation) or not np.isfinite(scale) or not 0.01 <= scale <= 100:
            raise ValueError(f"Invalid rotation or scale for {ident}")
        asset = trimesh.load(str(catalog[key]), force="scene")
        if not isinstance(asset, trimesh.Scene) or not asset.geometry:
            raise ValueError(f"Asset has no geometry: {key}")
        base_transform = trimesh.transformations.rotation_matrix(np.radians(rotation), [0, 0, 1])
        base_transform = base_transform @ trimesh.transformations.scale_matrix(scale)
        bounds = transformed_bounds(asset.bounds, base_transform)
        relation = item.get("relation", "floor")
        target = item.get("relative_to")
        if relation not in RELATIONS:
            raise ValueError(f"Unsupported placement relation: {relation}")
        if "position" in item:
            position = _vector(item["position"], "position")
        else:
            wall_or_ceiling = relation.startswith("wall_") or relation == "ceiling"
            if wall_or_ceiling and room_bounds is None:
                raise ValueError(f"{relation} requires a room")
            if target is not None and target not in placed_bounds and target != "room":
                raise ValueError(f"Unknown or not yet placed target: {target}")
            target_bounds = room_bounds if wall_or_ceiling else placed_bounds.get(target)
            position = resolve_translation(bounds, relation, target_bounds,
                                           float(item.get("clearance", 0.05)))
        if relation == "floor" and position[2] + bounds[0, 2] < 0:
            position[2] = -bounds[0, 2]
        transform = trimesh.transformations.translation_matrix(position) @ base_transform
        world_bounds = transformed_bounds(asset.bounds, transform)
        correction = np.zeros(3)
        support_bounds = placed_bounds.get(target) if relation == "on" else None
        if room_bounds is not None or support_bounds is not None or not item.get("allow_overlap", False):
            correction = separate_static_aabb(
                world_bounds, [] if item.get("allow_overlap", False) else list(placed_bounds.values()),
                containment=room_bounds, support=support_bounds)
            position += correction
            transform = trimesh.transformations.translation_matrix(position) @ base_transform
            world_bounds = transformed_bounds(asset.bounds, transform)
        placed_bounds[ident] = world_bounds
        for part, geometry in enumerate(asset.dump()):
            scene.add_geometry(geometry, node_name=f"{ident}.part-{part:03d}",
                               geom_name=f"{ident}.mesh-{part:03d}", transform=transform)
        manifest["objects"].append({"id": ident, "asset": key, "position": position.tolist(),
                                    "source_sha256": asset_hashes[key],
                                    "rotation_deg": rotation, "scale": scale,
                                    "relation": relation, "relative_to": target,
                                    "collision_correction": correction.tolist(),
                                    "stage": _object_stage(item)})
    return scene, manifest


def _stage_spec(spec: dict[str, Any], stage: str) -> dict[str, Any]:
    selected = {"schema": "ssui.scene-layout/1"}
    if "room" in spec:
        selected["room"] = spec["room"]
    cutoff = STAGES.index(stage)
    selected["objects"] = [item for item in spec["objects"]
                           if STAGES.index(_object_stage(item)) <= cutoff]
    return selected


def _resume_spec(spec: dict[str, Any], resume_from: str | Path) -> dict[str, Any]:
    source = Path(resume_from)
    state_path = source / "scene.json" if source.is_dir() else source
    previous = json.loads(state_path.read_text(encoding="utf-8"))
    if previous.get("schema") != "ssui.scene-layout/1" or not isinstance(previous.get("objects"), list):
        raise ValueError("Resume state is not a valid SSUI scene layout")
    ids = {item.get("id") for item in previous["objects"]}
    additions = spec.get("objects", [])
    if any(item.get("id") in ids for item in additions):
        raise ValueError("New scene objects duplicate IDs in resume state")
    merged = {"schema": "ssui.scene-layout/1",
              "objects": [*previous["objects"], *additions]}
    if "room" in spec or "room" in previous:
        merged["room"] = spec.get("room", previous.get("room"))
    return merged


def generate_scene(prompt: str, asset_dir: str | Path, output_dir: str | Path,
                   spec: dict[str, Any] | None = None, *, stop_stage: str = "manipuland",
                   resume_from: str | Path | None = None) -> Path:
    if stop_stage not in STAGES:
        raise ValueError(f"Invalid stop stage: {stop_stage}")
    catalog = asset_catalog(asset_dir)
    layout = spec if spec is not None else offline_plan(prompt, catalog)
    if not isinstance(layout, dict) or layout.get("schema") != "ssui.scene-layout/1" or not isinstance(layout.get("objects"), list):
        raise ValueError("Expected ssui.scene-layout/1 with an objects array")
    if any(not isinstance(item, dict) for item in layout["objects"]):
        raise ValueError("Scene objects must be JSON objects")
    if resume_from is not None:
        layout = _resume_spec(layout, resume_from)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    scene = None
    manifest = None
    previous_ids = None
    previous_stage_dir = None
    for stage in STAGES[:STAGES.index(stop_stage) + 1]:
        stage_spec = _stage_spec(layout, stage)
        if not stage_spec["objects"] and "room" not in stage_spec:
            continue
        stage_dir = output / "stages" / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        current_ids = tuple(item.get("id", index) for index, item in enumerate(stage_spec["objects"]))
        if previous_ids == current_ids and previous_stage_dir is not None:
            shutil.copyfile(previous_stage_dir / "scene.glb", stage_dir / "scene.glb")
            shutil.copyfile(previous_stage_dir / "scene.json", stage_dir / "scene.json")
            shutil.copyfile(previous_stage_dir / "preview.png", stage_dir / "preview.png")
        else:
            scene, manifest = build_scene(stage_spec, catalog)
            scene.export(str(stage_dir / "scene.glb"))
            (stage_dir / "scene.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            render_native_preview(stage_dir / "scene.glb", stage_dir / "preview.png")
        previous_ids = current_ids
        previous_stage_dir = stage_dir
    if scene is None or manifest is None:
        raise ValueError(f"No scene content is available through stage {stop_stage}")
    glb = output / "scene.glb"
    shutil.copyfile(previous_stage_dir / "scene.glb", glb)
    shutil.copyfile(previous_stage_dir / "scene.json", output / "scene.json")
    shutil.copyfile(previous_stage_dir / "preview.png", output / "preview.png")
    return glb
