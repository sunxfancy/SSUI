"""Import an SSUI BVH into Blender, render a source-vs-rig overlay, and measure it.

Usage:
  blender --background --python reconstruct_and_compare.py -- \
    --bvh motion.bvh --retarget motion.retarget.json --output-dir blender-result --render
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


BONES = (
    ("Hips", "Spine"), ("Spine", "Chest"), ("Chest", "Neck"), ("Neck", "Head"),
    ("Chest", "LeftShoulder"), ("LeftShoulder", "LeftArm"), ("LeftArm", "LeftForeArm"), ("LeftForeArm", "LeftHand"),
    ("Chest", "RightShoulder"), ("RightShoulder", "RightArm"), ("RightArm", "RightForeArm"), ("RightForeArm", "RightHand"),
    ("Hips", "LeftUpLeg"), ("LeftUpLeg", "LeftLeg"), ("LeftLeg", "LeftFoot"), ("LeftFoot", "LeftToe"),
    ("Hips", "RightUpLeg"), ("RightUpLeg", "RightLeg"), ("RightLeg", "RightFoot"), ("RightFoot", "RightToe"),
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bvh", required=True)
    parser.add_argument("--retarget", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def material(name, color, emission=0.25):
    value = bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1.0)
    value.use_nodes = True
    principled = value.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (*color, 1.0)
    principled.inputs["Roughness"].default_value = 0.38
    if "Emission Color" in principled.inputs:
        principled.inputs["Emission Color"].default_value = (*color, 1.0)
        principled.inputs["Emission Strength"].default_value = emission
    return value


def standard_to_blender(value):
    # BVH X-right/Y-up/Z-forward -> Blender X-right/Y-depth/Z-up.
    return Vector((value[0], -value[2], value[1]))


def make_sphere(name, mat, radius=0.018):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def make_bone(name, mat, radius=0.007):
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius, depth=1.0)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.data.materials.append(mat)
    return obj


def place_bone(obj, start, end, frame):
    delta = end - start
    length = max(delta.length, 1e-6)
    obj.location = (start + end) * 0.5
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    obj.scale = (1, 1, length)
    obj.keyframe_insert("location", frame=frame)
    obj.keyframe_insert("rotation_quaternion", frame=frame)
    obj.keyframe_insert("scale", frame=frame)


def animate_skeleton(frames, mat, prefix):
    names = sorted({name for frame in frames for name in frame})
    joints = {name: make_sphere(f"{prefix}_{name}", mat) for name in names}
    bones = {(a, b): make_bone(f"{prefix}_{a}_{b}", mat) for a, b in BONES if a in joints and b in joints}
    for frame_index, data in enumerate(frames, 1):
        positions = {name: standard_to_blender(value) for name, value in data.items()}
        for name, obj in joints.items():
            if name not in positions:
                obj.hide_render = True
                obj.keyframe_insert("hide_render", frame=frame_index)
                continue
            obj.hide_render = False
            obj.location = positions[name]
            obj.keyframe_insert("hide_render", frame=frame_index)
            obj.keyframe_insert("location", frame=frame_index)
        for pair, obj in bones.items():
            if pair[0] in positions and pair[1] in positions:
                place_bone(obj, positions[pair[0]], positions[pair[1]], frame_index)
    return joints


def add_camera(display_frames):
    all_points = [standard_to_blender(value) for frame in display_frames for value in frame.values()]
    low = Vector((min(p.x for p in all_points), min(p.y for p in all_points), min(p.z for p in all_points)))
    high = Vector((max(p.x for p in all_points), max(p.y for p in all_points), max(p.z for p in all_points)))
    center = (low + high) * 0.5
    extent = max(high.x - low.x, high.z - low.z, 0.5)
    bpy.ops.object.camera_add(location=(center.x, center.y - extent * 3.0, center.z))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent * 1.35
    camera.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.camera = camera


def shifted(frames, amount):
    return [
        {name: [value[0] + amount, value[1], value[2]] for name, value in frame.items()}
        for frame in frames
    ]


def compare_in_blender(scene, armature, targets):
    errors = {}
    samples = []
    for frame_index, target in enumerate(targets, 1):
        scene.frame_set(frame_index)
        for name, value in target.items():
            if name not in armature.pose.bones:
                continue
            expected = standard_to_blender(value)
            actual = armature.matrix_world @ armature.pose.bones[name].head
            error = (actual - expected).length
            errors.setdefault(name, []).append(error)
            samples.append(error)
    return {
        "schema": "ssui.motion.blender-comparison/v1",
        "blender_version": bpy.app.version_string,
        "frames": len(targets),
        "samples": len(samples),
        "rmse": math.sqrt(sum(value * value for value in samples) / len(samples)) if samples else 0.0,
        "max_error": max(samples, default=0.0),
        "per_joint_mean": {name: sum(values) / len(values) for name, values in errors.items()},
        "units": "Blender units",
    }


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(Path(args.retarget).read_text(encoding="utf-8"))
    targets = data["target"]
    reconstructed = data["reconstructed"]
    clear_scene()
    bpy.ops.import_anim.bvh(
        filepath=str(Path(args.bvh).resolve()), axis_forward="-Z", axis_up="Y",
        global_scale=1.0, frame_start=1, use_fps_scale=False, update_scene_fps=True,
        rotate_mode="NATIVE",
    )
    armature = bpy.context.object
    armature.name = "SSUI_Retargeted_Rig"
    armature.show_in_front = True
    target_mat = material("Source pose · amber", (1.0, 0.46, 0.08), 0.5)
    rig_mat = material("BVH reconstruction · cyan", (0.06, 0.82, 0.88), 0.7)
    all_x = [value[0] for frame in targets for value in frame.values()]
    comparison_gap = max(max(all_x) - min(all_x), 0.5) * 1.25
    source_display = shifted(targets, -comparison_gap * 0.5)
    rig_display = shifted(reconstructed, comparison_gap * 0.5)
    animate_skeleton(source_display, target_mat, "Source")
    animate_skeleton(rig_display, rig_mat, "BVH")
    add_camera(source_display + rig_display)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = len(targets)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 960
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(frames_dir / "pose-comparison-")
    scene.world.color = (0.008, 0.015, 0.02)

    report = compare_in_blender(scene, armature, targets)
    (output_dir / "blender-comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "pose-comparison.blend"))
    if args.render:
        bpy.ops.render.render(animation=True)
    print("SSUI_BLENDER_REPORT=" + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
