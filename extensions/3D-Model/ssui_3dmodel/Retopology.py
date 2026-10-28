"""Local P3-SAM segmentation and standalone QuadriFlow workflow nodes."""
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import uuid

import trimesh

from ssui import Mesh
from ssui.annotation import param
from ssui.config import SSUIConfig
from ssui.controller import Slider
from .quad_quality import repair_polygons, inspect_boundaries, validate_glb


def _run(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=3600)
    if result.returncode:
        raise RuntimeError(f"3D processing failed ({result.returncode}):\n{result.stderr[-6000:]}\n{result.stdout[-6000:]}")
    return result


def _linux_path(value):
    value = str(value)
    path = PureWindowsPath(value)
    if path.drive and len(path.drive) == 2 and path.drive[1] == ":":
        return f"/mnt/{path.drive[0].lower()}/" + "/".join(path.parts[1:])
    return value


def _wsl(command, distro, cwd=None):
    args = ["wsl.exe", "--distribution", distro]
    if cwd:
        args.extend(["--cd", _linux_path(cwd)])
    return [*args, "--", *[_linux_path(value) for value in command]]


def _job():
    root = Path(os.environ.get("SSUI_3D_OUTPUT", "output")).resolve() / f"retopology_{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def _result(path, artifacts):
    result = Mesh.load(str(path))
    result.artifacts = {name: str(value) for name, value in artifacts.items()}
    return result


def segment_parts(mesh: Mesh) -> Mesh:
    """Run upstream AutoMask in its own CUDA environment; never fake segmentation."""
    repo = Path(os.environ.get("SSUI_P3SAM_ROOT", "")).expanduser().resolve()
    demo = repo / "demo"
    python = os.environ.get("SSUI_P3SAM_PYTHON")
    distro = os.environ.get("SSUI_P3SAM_WSL_DISTRO")
    if not (demo / "auto_mask.py").is_file() or not python:
        raise RuntimeError("Configure SSUI_P3SAM_ROOT (P3-SAM directory) and SSUI_P3SAM_PYTHON (its Python executable). See doc/Retopology.md.")
    if mesh._model is None:
        raise ValueError("Import a model before segmentation")
    root = _job()
    source = root / "source.glb"
    mesh._model.export(str(source))
    worker = Path(__file__).with_name("p3sam_worker.py")
    command = [python, str(worker), str(source), str(root), os.environ.get("SSUI_P3SAM_CHECKPOINT", "")]
    if distro:
        # Pass only runtime settings, not the host environment or credentials.
        settings = [f"{key}={os.environ[key]}" for key in ("SSUI_P3SAM_DEVICE", "SSUI_P3SAM_POINT_NUM", "SSUI_P3SAM_PROMPT_NUM", "SSUI_P3SAM_PROMPT_BATCH", "OMP_NUM_THREADS") if key in os.environ]
        process = _run(_wsl(["env", *settings, *command], distro, demo))
    else:
        process = _run(command, cwd=demo)
    if process is not None:
        (root / "p3sam.log").write_text(process.stdout + "\n" + process.stderr, encoding="utf-8")
    target = root / "segmented.glb"
    if not target.is_file():
        raise RuntimeError(f"P3-SAM produced no segmented mesh; see {root}")
    return _result(target, {"segmented.glb": target, "segmentation.json": root / "segmentation.json"})


def _read_polygons(path):
    """Read OBJ polygons without allowing trimesh to triangulate the master mesh."""
    vertices, faces = [], []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        fields = line.split("#", 1)[0].split()
        if not fields:
            continue
        if fields[0] == "v":
            vertex = [float(value) for value in fields[1:4]]
            if len(vertex) != 3 or not all(math.isfinite(value) for value in vertex):
                raise ValueError("QuadriFlow output contains invalid vertices")
            vertices.append(vertex)
        elif fields[0] == "f":
            indices = [int(value.split("/")[0]) for value in fields[1:]]
            if any(value == 0 for value in indices):
                raise ValueError("OBJ indices cannot be zero")
            face = [value - 1 if value > 0 else len(vertices) + value for value in indices]
            if len(face) not in (3, 4) or len(set(face)) != len(face):
                raise ValueError("QuadriFlow output contains invalid triangle/quad faces")
            faces.append(face)
    if not vertices or not faces or any(i < 0 or i >= len(vertices) for face in faces for i in face):
        raise ValueError("QuadriFlow output is empty or contains invalid face indices")
    return vertices, faces


def _scene_parts(model):
    if isinstance(model, trimesh.Trimesh):
        return [("part_0", model.copy())] if len(model.faces) else []
    parts = []
    for index, node in enumerate(model.graph.nodes_geometry):
        transform, geometry = model.graph[node]
        part = model.geometry[geometry]
        if isinstance(part, trimesh.Trimesh) and len(part.faces):
            part = part.copy()
            part.apply_transform(transform)
            name = re.sub(r"[^\w.-]", "_", str(node)) or f"part_{index}"
            parts.append((f"{index}_{name}", part))
    return parts


def quad_remesh(mesh: Mesh, target_faces=5000) -> Mesh:
    if isinstance(target_faces, bool) or int(target_faces) != target_faces or not 100 <= target_faces <= 200000:
        raise ValueError("Target face count must be an integer between 100 and 200000")
    configured = os.environ.get("SSUI_QUADRIFLOW_EXECUTABLE")
    distro = os.environ.get("SSUI_QUADRIFLOW_WSL_DISTRO")
    executable = configured if distro else (str(Path(configured).expanduser()) if configured else shutil.which("quadriflow"))
    if not executable or (not distro and not Path(executable).is_file()):
        raise RuntimeError("Set SSUI_QUADRIFLOW_EXECUTABLE to the standalone QuadriFlow executable or add quadriflow to PATH. See doc/Retopology.md.")
    if mesh._model is None:
        raise ValueError("Import or segment a model before remeshing")
    root = _job()
    parts = _scene_parts(mesh._model)
    if not parts:
        raise ValueError("No mesh faces found")
    total = sum(len(part.faces) for _, part in parts)
    scene, reports, preview = trimesh.Scene(), [], []
    files = {name: root / name for name in ("retopology.glb", "retopology.obj", "report.json", "preview.json")}
    with files["retopology.obj"].open("w", encoding="utf-8", newline="\n") as master:
        master.write("# SSUI QuadriFlow polygon master; quads preserved\n")
        offset = 0
        for index, (name, part) in enumerate(parts):
            source, target = root / f"input_{index}.obj", root / f"quad_{index}.obj"
            part.export(str(source))
            requested = max(4, round(int(target_faces) * len(part.faces) / total))
            command = [executable, "-i", str(source), "-o", str(target), "-f", str(requested),
                       "-sharp", "-boundary", "-seed", "42"]
            _run(_wsl(command, distro) if distro else command)
            if not target.is_file():
                raise RuntimeError(f"QuadriFlow produced no mesh for {name}; inspect {root}")
            vertices, faces = _read_polygons(target)
            raw_faces = len(faces)
            vertices, faces, triangles, cleanup = repair_polygons(vertices, faces)
            boundary = inspect_boundaries(vertices, faces, part)
            quads = sum(len(face) == 4 for face in faces)
            if not quads:
                raise RuntimeError(f"QuadriFlow produced no quads for {name}")
            master.write(f"o {name}\n")
            for vertex in vertices:
                master.write("v " + " ".join(format(v, ".17g") for v in vertex) + "\n")
            for face in faces:
                master.write("f " + " ".join(str(i + offset + 1) for i in face) + "\n")
            offset += len(vertices)
            # Triangulate a separate copy for GLB; never round-trip the OBJ master.
            display = trimesh.Trimesh(vertices=vertices, faces=triangles, process=False)
            display.visual.face_colors = [(index * 73 + 80) % 220 + 20, (index * 113 + 40) % 220 + 20,
                                          (index * 47 + 100) % 220 + 20, 255]
            scene.add_geometry(display, node_name=name, geom_name=name)
            preview.append({"name": name, "vertices": vertices, "faces": faces})
            reports.append({"name": name, "input_faces": len(part.faces), "requested_faces": requested,
                            "raw_faces": raw_faces, "faces": len(faces), "quads": quads,
                            "cleanup": cleanup, "boundary": boundary})
    scene.export(str(files["retopology.glb"]))
    exported_degenerate = validate_glb(files["retopology.glb"])
    files["preview.json"].write_text(json.dumps(preview), encoding="utf-8")
    quality = {"parts": len(reports), "quads": sum(part["quads"] for part in reports),
        "removed_zero_area_faces": sum(part["cleanup"]["removed_zero_area_faces"] for part in reports),
        "regularized_faces": sum(part["cleanup"]["regularized_faces"] for part in reports),
        "degenerate_export_triangles": exported_degenerate,
        "boundary_edges": sum(part["boundary"]["output_boundary_edges"] for part in reports),
        "boundary_edges_away_from_input": sum(part["boundary"]["boundary_edges_away_from_input"] for part in reports),
        "nonmanifold_edges": sum(part["boundary"]["nonmanifold_edges"] for part in reports)}
    files["report.json"].write_text(json.dumps({"backend": "QuadriFlow standalone", "parts": reports,
        "quality": quality,
        "note": "OBJ preserves quads; GLB uses nondegenerate diagonals. Input cuts are retained, not capped. UVs/textures are not baked."}, indent=2), encoding="utf-8")
    result = _result(files["retopology.glb"], files)
    result.preview_path = str(files["preview.json"])
    result.quality = quality
    return result


def SegmentParts(config: SSUIConfig, mesh: Mesh) -> Mesh:
    return Mesh() if config.is_prepare() else segment_parts(mesh)


@param("target_faces", Slider(100, 200000, 100), default=5000)
def QuadRemesh(config: SSUIConfig, mesh: Mesh) -> Mesh:
    return Mesh() if config.is_prepare() else quad_remesh(mesh, config["target_faces"])
