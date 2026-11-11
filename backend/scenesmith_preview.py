"""Small native CPU preview renderer for static SceneSmith GLB geometry."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import trimesh


def render_native_preview(glb: str | Path, output: str | Path,
                          size: tuple[int, int] = (640, 480)) -> Path:
    """Render shaded geometry without a GPU, display server, or Blender process."""
    source = Path(glb).expanduser().resolve()
    scene = trimesh.load(source, force="scene")
    if not isinstance(scene, trimesh.Scene) or not scene.geometry:
        raise ValueError("GLB scene has no geometry")
    if not 64 <= size[0] <= 4096 or not 64 <= size[1] <= 4096:
        raise ValueError("Preview dimensions must be 64 to 4096 pixels")
    meshes = []
    for node in scene.graph.nodes_geometry:
        if node.startswith(("room.wall.front", "room.wall.right")):
            continue  # Cut away camera-facing walls so room contents remain visible.
        matrix, geometry_name = scene.graph.get(node)
        geometry = scene.geometry[geometry_name]
        if not isinstance(geometry, trimesh.Trimesh) or not len(geometry.faces):
            continue
        vertices = trimesh.transform_points(geometry.vertices, matrix)
        meshes.append((vertices, geometry))
    if not meshes:
        raise ValueError("GLB scene has no visible triangle meshes")
    all_vertices = np.concatenate([vertices for vertices, _ in meshes])
    center = (all_vertices.min(axis=0) + all_vertices.max(axis=0)) / 2
    forward = np.array([-1.0, 1.2, -0.85], dtype=float)
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    projection = np.stack([right, up, forward], axis=1)
    projected_all = (all_vertices - center) @ projection
    horizontal = max(float(np.ptp(projected_all[:, 0])), 0.1)
    vertical = max(float(np.ptp(projected_all[:, 1])), 0.1)
    pixels_per_unit = min(size[0] * 0.82 / horizontal, size[1] * 0.82 / vertical)
    image = Image.new("RGB", size, (35, 39, 47))
    draw = ImageDraw.Draw(image)
    triangles = []
    light = np.array([0.3, -0.5, 0.82])
    light /= np.linalg.norm(light)
    for vertices, mesh in meshes:
        projected = (vertices - center) @ projection
        points = np.column_stack((size[0] / 2 + projected[:, 0] * pixels_per_unit,
                                  size[1] / 2 - projected[:, 1] * pixels_per_unit))
        visual = mesh.visual
        colors = (visual.face_colors if hasattr(visual, "face_colors") else
                  visual.to_color().face_colors if hasattr(visual, "to_color") else
                  np.tile(np.array([[180, 185, 192, 255]], dtype=np.uint8), (len(mesh.faces), 1)))
        for index, face in enumerate(mesh.faces):
            corners = vertices[face]
            normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
            length = np.linalg.norm(normal)
            if length < 1e-12:
                continue
            brightness = 0.4 + 0.6 * abs(float(np.dot(normal / length, light)))
            rgb = tuple(int(channel * brightness) for channel in colors[index, :3])
            triangles.append((float(projected[face, 2].mean()), points[face], rgb))
    for _, points, color in sorted(triangles, key=lambda entry: entry[0], reverse=True):
        draw.polygon([tuple(point) for point in points], fill=color)
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return destination
