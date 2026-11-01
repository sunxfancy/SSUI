"""Isolated official auto-rigging runtimes; native GLB skins stay intact."""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from ssui.annotation import param
from ssui.base import Mesh
from ssui.config import SSUIConfig
from ssui.controller import Random, Select, Slider

ROOT = Path(__file__).resolve().parents[3]
MODELS = ("unirig", "mia", "riganything")


def validate_rigged_glb(path):
    """Reject static meshes and incomplete/invalid skin exports."""
    with open(path, "rb") as stream:
        header = stream.read(20)
        if len(header) != 20:
            raise ValueError("Rigging output is not a GLB")
        magic, version, total, length, kind = struct.unpack("<4sIIII", header)
        if magic != b"glTF" or version != 2 or kind != 0x4E4F534A or total != Path(path).stat().st_size:
            raise ValueError("Rigging output has an invalid GLB header")
        if length > total - 20:
            raise ValueError("Rigging output has a truncated JSON chunk")
        doc = json.loads(stream.read(length))
    skins, nodes = doc.get("skins", []), doc.get("nodes", [])
    meshes = doc.get("meshes", [])
    for node in nodes:
        skin, mesh = node.get("skin"), node.get("mesh")
        if not isinstance(skin, int) or not isinstance(mesh, int):
            continue
        if not (0 <= skin < len(skins) and 0 <= mesh < len(meshes)):
            continue
        joints = skins[skin].get("joints", [])
        if not joints or any(not isinstance(j, int) or j < 0 or j >= len(nodes) for j in joints):
            continue
        primitives = meshes[mesh].get("primitives", [])
        if primitives and all(
            "JOINTS_0" in p.get("attributes", {}) and "WEIGHTS_0" in p.get("attributes", {})
            for p in primitives
        ):
            return doc
    raise ValueError("Rigging output contains no skinned mesh with joints and weights")


class AutoRigModel:
    def __init__(self, name, repo_dir=None, python=None):
        if name not in MODELS:
            raise ValueError(f"Unknown rigging model: {name}")
        self.name = name
        prefix = "SSUI_" + name.upper()
        self.repo_dir = Path(repo_dir or os.environ.get(prefix + "_REPO") or ROOT / "models/rigging" / name).resolve()
        default_python = ROOT / ".venv/rigging" / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.python = str(python or os.environ.get(prefix + "_PYTHON") or default_python)

    @classmethod
    def load_local(cls, name, repo_dir=None, python=None):
        # No imports, downloads or GPU allocation during workflow preparation.
        return cls(name, repo_dir, python)

    def rig(self, mesh, seed=42, target_faces=8192):
        if not isinstance(mesh, Mesh) or (mesh._model is None and not mesh.path):
            raise ValueError("An input mesh is required")
        if mesh.path and Path(mesh.path).suffix.lower() != ".glb":
            raise ValueError("Path-backed meshes must be GLB files; use Mesh.load for other formats")
        if not 1000 <= int(target_faces) <= 100000:
            raise ValueError("target_faces must be between 1000 and 100000")
        if not self.repo_dir.is_dir() or not Path(self.python).is_file():
            raise RuntimeError(f"Missing {self.name} runtime. Run yarn install:rigging {self.name}; "
                               f"see extensions/3D-Model/RIGGING.md")
        output = ROOT / "output/rigging"
        output.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=self.name + "_", dir=output))
        source, result = work / "input.glb", work / "rigged.glb"
        if mesh.path:
            import shutil
            shutil.copyfile(mesh.path, source)
        else:
            mesh._model.export(str(source))
        command = [self.python, str(Path(__file__).with_name("_autorig_runner.py")),
                   "--model", self.name, "--repo", str(self.repo_dir),
                   "--input", str(source), "--output", str(result),
                   "--seed", str(int(seed)), "--target-faces", str(int(target_faces))]
        log = work / "inference.log"
        temporary = work / "tmp"
        temporary.mkdir()
        env = os.environ.copy()
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8:replace",
                   TEMP=str(temporary), TMP=str(temporary))
        env.setdefault("WANDB_MODE", "disabled")
        env.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
        with log.open("w", encoding="utf-8") as stream:
            completed = subprocess.run(command, cwd=self.repo_dir, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if completed.returncode:
            tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"{self.name} rigging failed; log: {log}\n{tail}")
        if not result.is_file():
            raise RuntimeError(f"{self.name} produced no rigged GLB; log: {log}")
        validate_rigged_glb(result)
        return Mesh(path=str(result))


@param("model", Select(*MODELS), default="unirig")
@param("seed", Random(), default=42)
@param("target_faces", Slider(1000, 100000, 1), default=8192)
def AutoRigMesh(config: SSUIConfig, mesh: Mesh) -> Mesh:
    """Generate bones and skin weights with a selected official runtime."""
    if config.is_prepare():
        return Mesh()
    return AutoRigModel.load_local(config["model"]).rig(
        mesh, config["seed"], config["target_faces"])
