"""Verify that a native GLB's skin deforms geometry when a weighted bone moves."""
import argparse
import json
from pathlib import Path

import bpy
import numpy as np


def verify(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not meshes or not armatures:
        raise ValueError("Missing mesh or armature")
    armature = armatures[0]
    weights = {}
    for mesh in meshes:
        names = {group.index: group.name for group in mesh.vertex_groups}
        for vertex in mesh.data.vertices:
            for group in vertex.groups:
                if group.weight > 0 and names[group.group] in armature.pose.bones:
                    name = names[group.group]
                    weights[name] = weights.get(name, 0) + group.weight
    choices = [bone for bone in armature.pose.bones if bone.parent and weights.get(bone.name, 0) > 0]
    if not choices:
        raise ValueError("No non-root bone influences mesh vertices")
    bone = max(choices, key=lambda b: weights[b.name])

    def vertices():
        depsgraph = bpy.context.evaluated_depsgraph_get()
        result = []
        for mesh in meshes:
            evaluated = mesh.evaluated_get(depsgraph)
            geometry = evaluated.to_mesh()
            result.extend(tuple(evaluated.matrix_world @ vertex.co) for vertex in geometry.vertices)
            evaluated.to_mesh_clear()
        return np.asarray(result)

    before = vertices()
    bone.rotation_mode = "XYZ"
    bone.rotation_euler.z += 0.35
    bpy.context.view_layer.update()
    after = vertices()
    displacement = np.linalg.norm(after - before, axis=1)
    if not np.isfinite(displacement).all() or displacement.max() <= 1e-6:
        raise ValueError("Bone rotation did not deform the mesh")
    return dict(bone=bone.name, vertices=len(displacement),
                changed_vertices=int((displacement > 1e-6).sum()),
                max_displacement=float(displacement.max()), skin_deformation="passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    args = parser.parse_args()
    result = verify(args.mesh)
    args.mesh.with_suffix(".deformation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
