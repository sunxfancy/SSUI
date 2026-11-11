"""Executed inside Blender's bundled Python; no bpy dependency in SSUI backend."""

from pathlib import Path
import sys

import bpy
from mathutils import Vector


def main():
    source, preview, blend = map(Path, sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("Imported scene has no mesh")
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector([min(point[axis] for point in points) for axis in range(3)])
    high = Vector([max(point[axis] for point in points) for axis in range(3)])
    center = (low + high) / 2
    extent = max(high.x - low.x, high.y - low.y, high.z - low.z, 1.0)
    bpy.ops.object.camera_add(location=(center.x + extent * 1.6,
                                        center.y - extent * 2.2,
                                        center.z + extent * 1.5))
    camera = bpy.context.object
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = extent * 2.4
    bpy.context.scene.camera = camera
    for location, power in (((center.x, center.y, center.z + extent * 2), 1500),
                            ((center.x - extent, center.y, center.z + extent), 700)):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = extent * 2
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(preview)
    scene.world.color = (0.12, 0.12, 0.12)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.render.render(write_still=True)
    print(f"SCENESMITH_RENDERED {preview} {blend}")


if __name__ == "__main__":
    main()
