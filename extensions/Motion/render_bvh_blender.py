"""Render a Kimodo BVH as a polished skeleton preview in Blender."""

import argparse
import math
import os
import subprocess
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--name", default="kimodo_motion")
    parser.add_argument("--ffmpeg")
    return parser.parse_args(argv)


def material(name, color, metallic=0.0, roughness=0.4, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if emission:
        emission_input = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
        if emission_input:
            emission_input.default_value = (*color, 1.0)
        shader.inputs["Emission Strength"].default_value = emission
    return mat


def shared_meshes():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
    sphere = bpy.context.object
    sphere_mesh = sphere.data.copy()
    bpy.data.objects.remove(sphere, do_unlink=True)

    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=1.0, depth=2.0)
    cylinder = bpy.context.object
    cylinder_mesh = cylinder.data.copy()
    bpy.data.objects.remove(cylinder, do_unlink=True)
    return sphere_mesh, cylinder_mesh


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_area_light(name, location, energy, size, color, target):
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light_data.color = color
    light = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(light)
    light.location = location
    look_at(light, target)


def create_trail(points, trail_material):
    curve = bpy.data.curves.new("RootTrail", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = 0.012
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coordinate in zip(spline.points, points):
        point.co = (*coordinate, 1.0)
    obj = bpy.data.objects.new("Root Trail", curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(trail_material)


def main():
    args = parse_args()
    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.preferences.addon_enable(module="io_anim_bvh")
    result = bpy.ops.import_anim.bvh(
        filepath=input_path,
        target="ARMATURE",
        global_scale=0.01,
        frame_start=1,
        use_fps_scale=False,
        update_scene_fps=True,
        update_scene_duration=True,
        rotate_mode="QUATERNION",
        axis_forward="-Z",
        axis_up="Y",
    )
    if "FINISHED" not in result:
        raise RuntimeError(f"BVH import failed: {result}")

    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    armature.hide_render = True
    scene = bpy.context.scene
    action = armature.animation_data.action if armature.animation_data else None
    if action:
        scene.frame_start = max(1, math.floor(action.frame_range[0]))
        scene.frame_end = max(scene.frame_start, math.ceil(action.frame_range[1]))
    else:
        scene.frame_start = 1
    scene.render.fps = 30

    frames = range(scene.frame_start, scene.frame_end + 1)
    bone_names = [bone.name for bone in armature.pose.bones if bone.bone.length > 1e-5]
    samples = {}
    all_points = []
    root_points = []
    for frame in frames:
        scene.frame_set(frame)
        frame_samples = {}
        for name in bone_names:
            bone = armature.pose.bones[name]
            head = armature.matrix_world @ bone.head
            tail = armature.matrix_world @ bone.tail
            frame_samples[name] = (head.copy(), tail.copy())
            all_points.extend((head, tail))
        samples[frame] = frame_samples
        root_bone = armature.pose.bones.get("Hips") or armature.pose.bones[0]
        root = armature.matrix_world @ root_bone.head
        root_points.append(Vector((root.x, root.y, min(p.z for p in all_points) + 0.018)))

    mins = Vector((min(p.x for p in all_points), min(p.y for p in all_points), min(p.z for p in all_points)))
    maxs = Vector((max(p.x for p in all_points), max(p.y for p in all_points), max(p.z for p in all_points)))
    center = (mins + maxs) * 0.5
    ground_z = mins.z - 0.025

    bone_material = material("Kimodo Cyan", (0.025, 0.48, 0.78), metallic=0.45, roughness=0.22, emission=0.15)
    joint_material = material("Kimodo Gold", (1.0, 0.29, 0.055), metallic=0.25, roughness=0.25, emission=0.1)
    detail_material = material("Kimodo Detail", (0.10, 0.75, 0.95), metallic=0.2, roughness=0.3)
    trail_material = material("Motion Trail", (0.12, 0.9, 0.95), roughness=0.25, emission=2.5)
    floor_material = material("Floor", (0.025, 0.035, 0.065), metallic=0.05, roughness=0.7)
    sphere_mesh, cylinder_mesh = shared_meshes()

    detail_tokens = ("Finger", "Thumb", "Index", "Middle", "Ring", "Pinky", "Eye", "Jaw", "Toe")
    visuals = {}
    for name in bone_names:
        is_detail = any(token in name for token in detail_tokens)
        joint = bpy.data.objects.new(f"Joint_{name}", sphere_mesh)
        segment = bpy.data.objects.new(f"Bone_{name}", cylinder_mesh)
        bpy.context.collection.objects.link(joint)
        bpy.context.collection.objects.link(segment)
        joint.data.materials.clear()
        segment.data.materials.clear()
        joint.data.materials.append(detail_material if is_detail else joint_material)
        segment.data.materials.append(detail_material if is_detail else bone_material)
        joint.rotation_mode = "QUATERNION"
        segment.rotation_mode = "QUATERNION"
        visuals[name] = (joint, segment, is_detail)

    for frame in frames:
        for name, (head, tail) in samples[frame].items():
            joint, segment, is_detail = visuals[name]
            direction = tail - head
            length = max(direction.length, 0.001)
            joint.location = head
            radius = 0.013 if is_detail else 0.027
            joint.scale = (radius, radius, radius)
            segment.location = (head + tail) * 0.5
            segment.rotation_quaternion = direction.to_track_quat("Z", "Y")
            segment_radius = 0.0065 if is_detail else 0.015
            segment.scale = (segment_radius, segment_radius, length * 0.5)
            for obj in (joint, segment):
                obj.keyframe_insert("location", frame=frame)
                obj.keyframe_insert("rotation_quaternion", frame=frame)
                obj.keyframe_insert("scale", frame=frame)

    create_trail(root_points, trail_material)

    floor_size = max(7.0, maxs.x - mins.x + 4.0, maxs.y - mins.y + 4.0)
    bpy.ops.mesh.primitive_plane_add(size=floor_size, location=(center.x, center.y, ground_z))
    floor = bpy.context.object
    floor.name = "Ground"
    floor.data.materials.append(floor_material)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.01, 0.025, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.18

    height = maxs.z - mins.z
    span = max(maxs.x - mins.x, maxs.y - mins.y, height)
    target = Vector((center.x, center.y, ground_z + height * 0.52))
    distance = max(4.2, span * 2.6)
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = target + Vector((distance * 0.72, -distance, distance * 0.42))
    camera.data.lens = 54
    look_at(camera, target)
    scene.camera = camera

    add_area_light("Key", target + Vector((-2.8, -3.5, 4.5)), 950, 4.0, (0.55, 0.76, 1.0), target)
    add_area_light("Fill", target + Vector((3.5, -0.5, 2.3)), 650, 3.0, (1.0, 0.32, 0.12), target)
    add_area_light("Rim", target + Vector((0.5, 3.0, 4.0)), 1100, 3.0, (0.15, 0.55, 1.0), target)

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass

    preview_frame = (scene.frame_start + scene.frame_end) // 2
    scene.frame_set(preview_frame)
    scene.render.filepath = os.path.join(output_dir, f"{args.name}_preview.png")
    bpy.ops.render.render(write_still=True)

    frames_dir = os.path.join(output_dir, f"{args.name}_frames")
    os.makedirs(frames_dir, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.join(frames_dir, "frame_")
    bpy.ops.render.render(animation=True)

    blend_path = os.path.join(output_dir, f"{args.name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    video_path = os.path.join(output_dir, f"{args.name}.mp4")
    if args.ffmpeg:
        subprocess.run(
            [
                os.path.abspath(args.ffmpeg),
                "-y",
                "-framerate",
                str(scene.render.fps),
                "-start_number",
                str(scene.frame_start),
                "-i",
                os.path.join(frames_dir, "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-frames:v",
                str(scene.frame_end - scene.frame_start + 1),
                video_path,
            ],
            check=True,
        )

    print(f"PREVIEW={os.path.join(output_dir, f'{args.name}_preview.png')}")
    print(f"FRAMES={frames_dir}")
    if args.ffmpeg:
        print(f"VIDEO={video_path}")
    print(f"BLEND={blend_path}")


if __name__ == "__main__":
    main()
