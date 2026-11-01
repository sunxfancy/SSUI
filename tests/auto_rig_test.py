"""Auto-rigging contracts without downloading weights or importing model code."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from ssui.base import Mesh
from ssui.config import SSUIConfig
from tests.utils import add_extension_paths

add_extension_paths()
from ssui_3dmodel.AutoRig import AutoRigMesh, AutoRigModel, validate_rigged_glb


def glb(path, skin=True):
    # Minimal structural fixture, not a model-quality or renderer test.
    doc = {"asset": {"version": "2.0"}, "nodes": [{"mesh": 0, "skin": 0}, {}],
           "skins": [{"joints": [1]}],
           "meshes": [{"primitives": [{"attributes": {"JOINTS_0": 0, "WEIGHTS_0": 1}}]}]}
    if not skin:
        doc["meshes"][0]["primitives"][0]["attributes"].pop("WEIGHTS_0")
    data = json.dumps(doc).encode()
    data += b" " * (-len(data) % 4)
    path.write_bytes(struct.pack("<4sIIII", b"glTF", 2, len(data) + 20, len(data), 0x4E4F534A) + data)


class AutoRigTest(unittest.TestCase):
    def test_prepare_does_not_launch_or_load_models(self):
        config = SSUIConfig()("Rig")
        config.set_prepared()
        with patch("subprocess.run", side_effect=AssertionError("Must not execute")):
            self.assertIsInstance(AutoRigMesh(config, Mesh()), Mesh)
        self.assertEqual(config._config["Rig"]["model"]["args"].options, ("unirig", "mia", "riganything"))

    def test_workflow_prepare(self):
        from ss_executor.loader import SSLoader
        loader = SSLoader()
        loader.load(str(Path(__file__).resolve().parents[1] / "examples/advance/workflow-auto-rig.py"))
        loader.Execute()
        loader.GetConfig("auto_rig")

    def test_static_and_truncated_glb_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.glb"
            glb(path)
            self.assertEqual(len(validate_rigged_glb(path)["skins"]), 1)
            glb(path, skin=False)
            with self.assertRaisesRegex(ValueError, "skinned mesh"):
                validate_rigged_glb(path)
            path.write_bytes(b"glTF")
            with self.assertRaises(ValueError):
                validate_rigged_glb(path)

    def test_executor_preserves_native_skin_bytes(self):
        from ss_executor.__main__ import convert_task_return
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "rig.glb"
            glb(source)
            with patch("ss_executor.__main__.search_project_root", return_value=folder):
                payload = convert_task_return(Mesh(path=str(source)), str(root / "workflow.py"))
            self.assertEqual(payload["type"], "mesh")
            self.assertEqual(Path(payload["path"]).read_bytes(), source.read_bytes())
            validate_rigged_glb(payload["path"])

    def test_runtime_errors_are_actionable(self):
        with self.assertRaisesRegex(ValueError, "Unknown rigging model"):
            AutoRigModel("unknown")
        with self.assertRaisesRegex(ValueError, "input mesh"):
            AutoRigModel("mia").rig(Mesh())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.glb"
            glb(path)
            model = AutoRigModel("unirig", repo_dir=folder, python=str(Path(folder) / "missing.exe"))
            with self.assertRaisesRegex(RuntimeError, "install:rigging unirig"):
                model.rig(Mesh(path=str(path)))

    def test_ordinary_mesh_export_still_works(self):
        import trimesh
        from ss_executor.__main__ import convert_task_return
        with tempfile.TemporaryDirectory() as folder:
            with patch("ss_executor.__main__.search_project_root", return_value=folder):
                result = convert_task_return(Mesh(trimesh.creation.box()), str(Path(folder) / "workflow.py"))
            geometry = trimesh.load(result["path"], force="mesh")
            self.assertEqual(len(geometry.faces), 12)

    def test_successful_handoff_validates_and_keeps_native_glb(self):
        import sys
        import trimesh
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            def inference(command, **kwargs):
                self.assertEqual(command[0], sys.executable)
                self.assertEqual(command[command.index("--model") + 1], "riganything")
                self.assertTrue(Path(command[command.index("--input") + 1]).is_file())
                glb(Path(command[command.index("--output") + 1]))
                return SimpleNamespace(returncode=0)
            model = AutoRigModel("riganything", repo_dir=folder, python=sys.executable)
            with patch("ssui_3dmodel.AutoRig.ROOT", Path(folder)), patch("subprocess.run", side_effect=inference):
                result = model.rig(Mesh(trimesh.creation.box()))
            validate_rigged_glb(result.path)
            self.assertIsNone(result._model)

    def test_subprocess_failure_and_no_output_are_not_success(self):
        import sys
        import trimesh
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            model = AutoRigModel("mia", repo_dir=folder, python=sys.executable)
            with patch("ssui_3dmodel.AutoRig.ROOT", Path(folder)):
                with patch("subprocess.run", return_value=SimpleNamespace(returncode=7)):
                    with self.assertRaisesRegex(RuntimeError, "rigging failed"):
                        model.rig(Mesh(trimesh.creation.box()))
                with patch("subprocess.run", return_value=SimpleNamespace(returncode=0)):
                    with self.assertRaisesRegex(RuntimeError, "no rigged GLB"):
                        model.rig(Mesh(trimesh.creation.box()))


if __name__ == "__main__":
    unittest.main()
