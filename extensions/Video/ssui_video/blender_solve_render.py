"""Run inside Blender: solve supplied tracks, place a GLB, render RGBA frames."""

import json
import math
import sys
import traceback
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def run(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    root = Path(manifest["output_dir"])
    root.mkdir(parents=True, exist_ok=True)
    clip = bpy.data.movieclips.load(manifest["video_path"])
    width, height = manifest["width"], manifest["height"]
    frames = manifest["frames"]
    tracking = clip.tracking
    tracking.camera.units = "PIXELS"
    tracking.camera.focal_length_pixels = manifest["focal_px"]
    tracking.objects.active.keyframe_a = 1
    tracking.objects.active.keyframe_b = frames
    tracking.settings.refine_intrinsics_focal_length = True
    for index, positions in enumerate(manifest["tracks"]):
        track = tracking.objects.active.tracks.new(name=f"SSUI_{index:03d}", frame=1)
        for frame_number, x, y in positions:
            coordinate = (x / width, 1 - y / height)
            marker = track.markers.find_frame(frame_number)
            if marker is None:
                marker = track.markers.insert_frame(frame_number, co=coordinate)
            marker.co = coordinate
    screen = bpy.context.screen or bpy.data.screens.get("Layout")
    if screen is None:
        raise RuntimeError("Blender has no screen for the camera solve operator")
    area = next((candidate for candidate in screen.areas if candidate.type == "CLIP_EDITOR"), None)
    if area is None:
        area = screen.areas[0]
        area.type = "CLIP_EDITOR"
    area.spaces.active.clip = clip
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frames
    scene.active_clip = clip
    scene.frame_set(1)
    with bpy.context.temp_override(area=area, space_data=area.spaces.active):
        result = bpy.ops.clip.solve_camera()
    reconstruction = tracking.objects.active.reconstruction
    if "FINISHED" not in result or not reconstruction.is_valid:
        raise RuntimeError(f"Blender camera solve failed: {result}")
    error = float(reconstruction.average_error)
    if not math.isfinite(error) or error > manifest["max_solve_error"]:
        raise RuntimeError(f"Blender reprojection error {error:.3f} px exceeds threshold")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    camera_data = bpy.data.cameras.new("Solved Camera")
    camera_data.sensor_width = tracking.camera.sensor_width
    camera_data.lens = tracking.camera.focal_length_pixels / width * camera_data.sensor_width
    camera = bpy.data.objects.new("Solved Camera", camera_data)
    scene.collection.objects.link(camera)
    constraint = camera.constraints.new("CAMERA_SOLVER")
    constraint.use_active_clip = False
    constraint.clip = clip
    scene.camera = camera
    scene.frame_set(1)
    bpy.context.view_layer.update()
    anchor_x, anchor_y = manifest["anchor"]
    bundles = []
    for track in tracking.objects.active.tracks:
        marker = track.markers.find_frame(1)
        if track.has_bundle and marker is not None:
            distance = (marker.co[0] - anchor_x) ** 2 + (marker.co[1] - (1 - anchor_y)) ** 2
            bundles.append((distance, Vector(track.bundle)))
    bundles.sort(key=lambda item: item[0])
    if len(bundles) < 3:
        raise RuntimeError("Camera solved, but fewer than three 3D feature points are available near the anchor")
    point = bundles[0][1]
    normal = (bundles[1][1] - point).cross(bundles[2][1] - point)
    if normal.length < 1e-5:
        normal = camera.matrix_world.to_3x3() @ Vector((0, 1, 0))
    normal.normalize()
    if normal.dot(camera.matrix_world.translation - point) < 0:
        normal.negate()
    direction = Vector(((anchor_x - .5) * width / tracking.camera.focal_length_pixels,
                        (.5 - anchor_y) * height / tracking.camera.focal_length_pixels, -1))
    direction = camera.matrix_world.to_3x3() @ direction
    direction.normalize()
    origin = camera.matrix_world.translation
    denominator = direction.dot(normal)
    if abs(denominator) > 1e-5:
        distance = (point - origin).dot(normal) / denominator
        if distance > 0:
            point = origin + direction * distance
    bpy.ops.import_scene.gltf(filepath=manifest["mesh_path"])
    imported = [obj for obj in bpy.context.selected_objects if obj.type in {"MESH", "ARMATURE", "EMPTY"}]
    if not imported:
        raise RuntimeError("GLB imported no renderable objects")
    root_object = bpy.data.objects.new("SSUI Anchor", None)
    scene.collection.objects.link(root_object)
    for obj in imported:
        if obj.parent is None:
            obj.parent = root_object
    root_object.location = point
    root_object.rotation_euler = Vector((0, 0, 1)).rotation_difference(normal).to_euler()
    scene.frame_set(1)
    bpy.context.view_layer.update()
    mesh_objects = [obj for obj in imported if obj.type == "MESH"]
    points = [obj.matrix_world @ Vector(corner) for obj in mesh_objects for corner in obj.bound_box]
    if not points:
        raise RuntimeError("Imported GLB has no mesh bounds")
    projected = [world_to_camera_view(scene, camera, item) for item in points]
    extent = max(item.y for item in projected) - min(item.y for item in projected)
    if extent <= 1e-6:
        raise RuntimeError("Imported mesh cannot be projected through the solved camera")
    root_object.scale *= manifest["size"] / extent
    camera_positions = []
    for frame_number in range(1, frames + 1):
        scene.frame_set(frame_number)
        camera_positions.append(camera.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.copy())
    translation_span = max((position - camera_positions[0]).length for position in camera_positions)
    scene.frame_set(1)
    world = bpy.data.worlds.new("SSUI World") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Strength"].default_value = .8
    light_data = bpy.data.lights.new("Soft Key", "AREA")
    light = bpy.data.objects.new("Soft Key", light_data)
    scene.collection.objects.link(light)
    light.location = camera.matrix_world @ Vector((-2, 3, -1))
    light_data.energy = 600
    light_data.shape = "DISK"
    light_data.size = 5
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.fps = round(manifest["fps"])
    renders = root / "renders"
    renders.mkdir(exist_ok=True)
    report = {"blender_version": bpy.app.version_string, "solve_error_px": error,
              "focal_px": tracking.camera.focal_length_pixels,
              "camera_frames": len(reconstruction.cameras),
              "camera_translation_span": translation_span,
              "bundle_count": len(bundles), "anchor_world": list(point)}
    (root / "solve.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "scene.blend"))
    for frame_number in range(1, frames + 1):
        scene.frame_set(frame_number)
        scene.render.filepath = str(renders / f"frame_{frame_number:04d}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    try:
        run(sys.argv[sys.argv.index("--") + 1])
    except Exception:
        traceback.print_exc()
        manifest = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
        Path(manifest["output_dir"]).mkdir(parents=True, exist_ok=True)
        Path(manifest["output_dir"], "blender-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
