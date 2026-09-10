"""WorldClaw-compatible open-world scene construction for SSUI.

Tencent's WorldClaw release currently describes an agentic pipeline rather than
shipping a model checkpoint or inference API.  This module implements its stable
boundary -- a structured world specification composed into editable terrain and
object instances -- and optionally accepts specifications from an HTTP planner.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
import trimesh

from ssui.annotation import param
from ssui.base import Mesh, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Select, Slider


TERRAIN_KINDS = ("plains", "hills", "mountains", "desert", "snow", "water")


@dataclass(frozen=True)
class WorldClawModel:
    """Configuration for a WorldClaw-compatible scene planner.

    ``planner_url`` is optional.  When present it receives ``{"prompt": ...,
    "seed": ...}`` and must return a WorldClaw world-spec JSON object.  Without
    it SSUI uses the deterministic built-in planner, which is useful offline and
    for reproducible game-scene blockouts.
    """

    planner_url: str | None = None
    api_key: str | None = None

    @staticmethod
    def load(
        planner_url: str | None = None,
        api_key: str | None = None,
    ) -> "WorldClawModel":
        return WorldClawModel(
            planner_url=planner_url or os.environ.get("SSUI_WORLDCLAW_PLANNER_URL"),
            api_key=api_key or os.environ.get("SSUI_WORLDCLAW_API_KEY"),
        )


def _remote_spec(model: WorldClawModel, prompt: str, seed: int) -> dict[str, Any]:
    body = json.dumps({"prompt": prompt, "seed": seed}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if model.api_key:
        headers["Authorization"] = f"Bearer {model.api_key}"
    request = urllib.request.Request(model.planner_url, body, headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            value = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"WorldClaw planner request failed: {exc}") from exc
    if isinstance(value, dict) and isinstance(value.get("spec"), dict):
        value = value["spec"]
    if not isinstance(value, dict):
        raise ValueError("WorldClaw planner must return a JSON object or {'spec': object}.")
    return value


def _offline_spec(prompt: str, seed: int, world_size: float) -> dict[str, Any]:
    text = prompt.lower()
    detected = []
    aliases = {
        "mountains": ("mountain", "山", "峡谷", "canyon"),
        "desert": ("desert", "沙漠", "dune"),
        "snow": ("snow", "雪", "冰"),
        "water": ("river", "lake", "ocean", "water", "河", "湖", "海"),
        "hills": ("hill", "丘陵", "高地"),
    }
    for kind, words in aliases.items():
        if any(word in text for word in words):
            detected.append(kind)
    if not detected:
        detected = ["plains", "hills"]
    if "plains" not in detected:
        detected.insert(0, "plains")

    asset_kinds = []
    for name, words in {
        "tree": ("tree", "forest", "树", "森林"),
        "house": ("village", "town", "house", "村", "镇", "房"),
        "rock": ("rock", "cliff", "stone", "岩", "石"),
    }.items():
        if any(word in text for word in words):
            asset_kinds.append(name)
    if not asset_kinds:
        asset_kinds = ["tree", "rock"]

    return {
        "version": "worldclaw-compatible/1",
        "name": "SSUI WorldClaw Scene",
        "prompt": prompt,
        "seed": seed,
        "world_size": world_size,
        "regions": [{"id": f"region-{i}", "kind": kind} for i, kind in enumerate(detected)],
        "assets": [{"id": name, "kind": name, "count": 10 if name == "tree" else 5}
                   for name in asset_kinds],
    }


def _repair_spec(raw: dict[str, Any], prompt: str, seed: int, world_size: float) -> dict[str, Any]:
    regions = raw.get("regions")
    if not isinstance(regions, list) or not regions:
        regions = [{"id": "region-0", "kind": "plains"}]
    repaired_regions = []
    for index, region in enumerate(regions[:8]):
        region = region if isinstance(region, dict) else {}
        kind = str(region.get("kind", "plains")).lower()
        repaired_regions.append({
            "id": str(region.get("id") or f"region-{index}"),
            "kind": kind if kind in TERRAIN_KINDS else "plains",
        })

    assets = raw.get("assets", raw.get("asset_prototypes", []))
    repaired_assets = []
    if isinstance(assets, list):
        for index, asset in enumerate(assets[:32]):
            asset = asset if isinstance(asset, dict) else {}
            kind = str(asset.get("kind", asset.get("category", "rock"))).lower()
            if kind not in ("tree", "house", "rock"):
                kind = "rock"
            repaired_assets.append({
                "id": str(asset.get("id") or f"{kind}-{index}"),
                "kind": kind,
                "count": max(1, min(100, int(asset.get("count", 4)))),
            })
    return {
        "version": "worldclaw-compatible/1",
        "name": str(raw.get("name") or "SSUI WorldClaw Scene"),
        "prompt": prompt,
        "seed": seed,
        "world_size": world_size,
        "regions": repaired_regions,
        "assets": repaired_assets,
    }


def _height(kind: str, x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    phase = rng.uniform(-np.pi, np.pi, 4)
    noise = (
        np.sin(x * 0.10 + phase[0]) * np.cos(y * 0.09 + phase[1])
        + 0.45 * np.sin(x * 0.23 + phase[2]) * np.cos(y * 0.19 + phase[3])
    )
    if kind == "mountains":
        return np.abs(noise) * 8.0
    if kind == "hills":
        return noise * 2.5
    if kind == "desert":
        return np.sin(x * 0.28 + np.sin(y * 0.08)) * 1.2
    if kind == "snow":
        return np.abs(noise) * 5.0 + 1.0
    if kind == "water":
        return np.full_like(x, -0.35)
    return noise * 0.55


def _terrain(spec: dict[str, Any], resolution: int) -> tuple[trimesh.Trimesh, Any]:
    size = float(spec["world_size"])
    axis = np.linspace(-size / 2, size / 2, resolution)
    x, y = np.meshgrid(axis, axis)
    regions = spec["regions"]
    stripe = np.minimum((x + size / 2) / size * len(regions), len(regions) - 1).astype(int)
    z = np.zeros_like(x)
    rng = np.random.default_rng(int(spec["seed"]))
    for index, region in enumerate(regions):
        heights = _height(region["kind"], x, y, rng)
        z[stripe == index] = heights[stripe == index]
    # Blend hard semantic boundaries into a stable, traversable height field.
    for _ in range(3):
        z[1:-1, 1:-1] = (
            z[1:-1, 1:-1] * 4 + z[:-2, 1:-1] + z[2:, 1:-1]
            + z[1:-1, :-2] + z[1:-1, 2:]
        ) / 8
    vertices = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    faces = []
    for row in range(resolution - 1):
        for col in range(resolution - 1):
            a = row * resolution + col
            faces.extend(((a, a + 1, a + resolution), (a + 1, a + resolution + 1, a + resolution)))
    mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    return mesh, lambda px, py: float(z[
        np.clip(np.searchsorted(axis, py), 0, resolution - 1),
        np.clip(np.searchsorted(axis, px), 0, resolution - 1),
    ])


def _prototype(kind: str) -> trimesh.Trimesh:
    if kind == "tree":
        trunk = trimesh.creation.cylinder(radius=0.18, height=1.8)
        trunk.apply_translation((0, 0, 0.9))
        crown = trimesh.creation.cone(radius=0.85, height=2.2)
        crown.apply_translation((0, 0, 2.4))
        return trimesh.util.concatenate((trunk, crown))
    if kind == "house":
        body = trimesh.creation.box((2.4, 2.0, 1.8))
        body.apply_translation((0, 0, 0.9))
        roof = trimesh.creation.cone(radius=1.8, height=1.1, sections=4)
        roof.apply_translation((0, 0, 2.35))
        return trimesh.util.concatenate((body, roof))
    return trimesh.creation.icosphere(subdivisions=1, radius=0.65)


def build_worldclaw_scene(spec: dict[str, Any], resolution: int = 64) -> trimesh.Scene:
    """Compose a validated WorldClaw specification into an editable scene."""
    scene = trimesh.Scene()
    terrain, sample_height = _terrain(spec, resolution)
    scene.add_geometry(terrain, geom_name="terrain", node_name="terrain")
    rng = np.random.default_rng(int(spec["seed"]))
    size = float(spec["world_size"])
    for asset in spec["assets"]:
        prototype = _prototype(asset["kind"])
        for index in range(asset["count"]):
            x, y = rng.uniform(-size * 0.46, size * 0.46, 2)
            z = sample_height(x, y)
            scale = rng.uniform(0.75, 1.25)
            transform = trimesh.transformations.scale_and_translate(
                scale=[scale, scale, scale], translate=[x, y, z]
            )
            name = f"asset.{asset['id']}.{index:03d}"
            scene.add_geometry(prototype.copy(), geom_name=name, node_name=name, transform=transform)
    scene.metadata["worldclaw_spec"] = spec
    return scene


@param("seed", Random(), default=42)
@param("world_size", Slider(32, 512, 1), default=128)
@param("terrain_resolution", Select(32, 64, 128, 256), default=64)
def GenWorldClawScene(
    config: SSUIConfig,
    model: WorldClawModel,
    prompt: Prompt,
) -> Mesh:
    """Generate an editable, GLB-exportable game-world blockout from text."""
    if config.is_prepare():
        return Mesh()
    seed = int(config["seed"])
    size = float(config["world_size"])
    text = prompt.text if isinstance(prompt, Prompt) else str(prompt)
    raw = _remote_spec(model, text, seed) if model.planner_url else _offline_spec(text, seed, size)
    spec = _repair_spec(raw, text, seed, size)
    return Mesh(build_worldclaw_scene(spec, int(config["terrain_resolution"])))
