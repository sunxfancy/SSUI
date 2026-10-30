"""Executed with the P3-SAM environment and demo working directory."""
import json
import os
from pathlib import Path
import sys

import numpy as np
import trimesh


def split_parts(mesh, labels):
    labels = np.asarray(labels)
    if labels.shape != (len(mesh.faces),) or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("P3-SAM returned invalid per-face labels")
    scene = trimesh.Scene()
    counts = {}
    for index, label in enumerate(np.unique(labels)):
        # Preserve negative/unassigned regions rather than silently deleting them.
        name = f"part_{int(label)}" if label >= 0 else f"unassigned_{abs(int(label))}"
        part = mesh.submesh([np.flatnonzero(labels == label)], append=True)
        color = [(index * 73 + 80) % 220 + 20, (index * 113 + 40) % 220 + 20, (index * 47 + 100) % 220 + 20, 255]
        part.visual = trimesh.visual.ColorVisuals(mesh=part, face_colors=color)
        scene.add_geometry(part, node_name=name, geom_name=name)
        counts[name] = len(part.faces)
    if not counts:
        raise ValueError("P3-SAM returned no parts")
    return scene, counts


if __name__ == "__main__":
    if os.environ.get("SSUI_P3SAM_BACKEND") == "rocm":
        from p3sam_rocm import configure_rocm
        configure_rocm()
    elif os.environ.get("SSUI_P3SAM_DEVICE") == "cpu":
        from p3sam_cpu import configure_cpu
        configure_cpu()
    sys.path.insert(0, str(Path.cwd()))
    from auto_mask import AutoMask, set_seed
    source, output, checkpoint = sys.argv[1:4]
    mesh = trimesh.load(source, force="mesh")
    model = AutoMask(checkpoint or None,
        point_num=int(os.environ.get("SSUI_P3SAM_POINT_NUM", "100000")),
        prompt_num=int(os.environ.get("SSUI_P3SAM_PROMPT_NUM", "400")))
    set_seed(42)
    # Use returned mesh: upstream cleaning can change both vertices and face order.
    _, labels, processed = model.predict_aabb(mesh, is_parallel=False, seed=42,
        prompt_bs=int(os.environ.get("SSUI_P3SAM_PROMPT_BATCH", "32")))
    scene, counts = split_parts(processed, labels)
    scene.export(str(Path(output) / "segmented.glb"))
    runtime = {}
    if os.environ.get("SSUI_P3SAM_BACKEND") == "rocm":
        import torch
        runtime = {"backend": "native-rocm-flexgemm", "torch": torch.__version__,
            "hip": torch.version.hip, "device_name": torch.cuda.get_device_name(0),
            "peak_gpu_bytes": torch.cuda.max_memory_allocated()}
    (Path(output) / "segmentation.json").write_text(json.dumps({"backend": "P3-SAM", "parts": counts,
        "device": os.environ.get("SSUI_P3SAM_DEVICE", "cuda"), "seed": 42,
        "point_num": model.point_num, "prompt_num": model.prompt_num,
        "prompt_batch": int(os.environ.get("SSUI_P3SAM_PROMPT_BATCH", "32")), "runtime": runtime}, indent=2), encoding="utf-8")
