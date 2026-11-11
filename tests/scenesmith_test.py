"""Native scene layout backend with real GLB round trips."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import trimesh
from PIL import Image

from backend.scenesmith import asset_catalog, asset_descriptors, build_scene, enforce_text_relations, generate_scene, offline_plan
from backend.scene_physics import penetration_depth, transformed_bounds
from backend.scenesmith_preview import render_native_preview
from ssui.base import Mesh, Prompt
from ssui.config import SSUIConfig
from tests.utils import add_extension_paths

add_extension_paths()
from ssui_3dmodel.SceneSmith import GenSceneSmithScene, SceneSmithModel


class SceneSmithTest(unittest.TestCase):
    def test_prepare_and_loader(self):
        config = SSUIConfig()("SceneSmith")
        config.set_prepared()
        self.assertIsInstance(GenSceneSmithScene(config, SceneSmithModel.load_local(), Prompt("room")), Mesh)
        from ss_executor.loader import SSLoader
        loader = SSLoader()
        loader.load(str(Path(__file__).resolve().parents[1] / "examples/advance/workflow-scenesmith.py"))
        loader.Execute()
        loader.GetConfig("scenesmith_scene")

    def test_native_scene_with_existing_assets(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            base = Path(folder)
            assets = base / "assets"
            assets.mkdir()
            trimesh.creation.box(extents=(2, 2, 2)).export(assets / "chair.glb")
            trimesh.creation.icosphere(radius=0.5).export(assets / "lamp.glb")
            spec = {"schema": "ssui.scene-layout/1", "objects": [
                {"id": "chair-a", "asset": "chair", "position": [1, 2, 0], "rotation_deg": 90},
                {"id": "lamp-a", "asset": "lamp", "position": [3, 2, 1]}]}
            output = generate_scene("chair and lamp", assets, base / "out", spec)
            loaded = trimesh.load(output, force="scene")
            self.assertEqual(len(loaded.geometry), 2)
            self.assertTrue(any("chair-a" in name for name in loaded.graph.nodes_geometry))
            manifest = json.loads((base / "out/scene.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in manifest["objects"]], ["chair-a", "lamp-a"])
            preview = render_native_preview(output, base / "out/preview.png")
            with Image.open(preview) as image:
                self.assertEqual(image.size, (640, 480))
                self.assertGreater(len(image.getcolors(640 * 480)), 1)
            with patch("ssui_3dmodel.SceneSmith.ROOT", base):
                result = SceneSmithModel.load_local(assets).generate("place chair and lamp")
            self.assertTrue(Path(result.path).is_file())

    def test_invalid_spec_and_assets(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box().export(assets / "box.glb")
            catalog = asset_catalog(assets)
            with self.assertRaisesRegex(ValueError, "Unknown asset"):
                build_scene({"schema": "ssui.scene-layout/1", "objects": [{"asset": "missing"}]}, catalog)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build_scene({"schema": "ssui.scene-layout/1", "objects": [
                    {"id": "same", "asset": "box"}, {"id": "same", "asset": "box"}]}, catalog)
            with self.assertRaisesRegex(ValueError, "finite"):
                build_scene({"schema": "ssui.scene-layout/1", "objects": [
                    {"asset": "box", "position": [float("nan"), 0, 0]}]}, catalog)

    def test_asset_metadata_for_retrieval(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box().export(assets / "seat.glb")
            (assets / "seat.json").write_text(json.dumps({"description": "Wooden dining chair",
                                                          "category": "furniture", "tags": ["椅子", "chair"]}),
                                               encoding="utf-8")
            catalog = asset_catalog(assets)
            self.assertEqual(asset_descriptors(catalog)[0]["tags"], ["椅子", "chair"])
            self.assertEqual(offline_plan("摆一把椅子", catalog)["objects"][0]["asset"], "seat")

    def test_explicit_text_relation_overrides_wrong_model_coordinates(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            for name, tag in (("table", "桌子"), ("chair", "椅子")):
                trimesh.creation.box().export(assets / f"{name}.glb")
                (assets / f"{name}.json").write_text(json.dumps({"tags": [tag]}, ensure_ascii=False), encoding="utf-8")
            spec = {"schema": "ssui.scene-layout/1", "objects": [
                {"id": "chair-1", "asset": "chair", "position": [2, 0, 0]},
                {"id": "table-1", "asset": "table", "position": [0, 0, 0]}]}
            corrected = enforce_text_relations("椅子放在桌子的左边", spec, asset_catalog(assets))
            self.assertEqual([item["id"] for item in corrected["objects"]], ["table-1", "chair-1"])
            _, manifest = build_scene(corrected, asset_catalog(assets))
            positions = {item["asset"]: item["position"] for item in manifest["objects"]}
            self.assertLess(positions["chair"][0], positions["table"][0])
            english = {"schema": "ssui.scene-layout/1", "objects": [
                {"id": "chair-1", "asset": "chair", "position": [2, 0, 0]},
                {"id": "table-1", "asset": "table", "position": [0, 0, 0]}]}
            enforce_text_relations("chair to the left of table", english, asset_catalog(assets))
            self.assertEqual(english["objects"][1]["relation"], "left_of")

    def test_multiple_text_relations_and_cycle(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            for name in ("table", "chair", "cup"):
                trimesh.creation.box().export(assets / f"{name}.glb")
            catalog = asset_catalog(assets)
            spec = {"schema": "ssui.scene-layout/1", "objects": [
                {"id": name, "asset": name, "position": [0, 0, 0]}
                for name in ("cup", "chair", "table")]}
            enforce_text_relations("cup on top of table; chair to the left of table", spec, catalog)
            self.assertEqual(spec["objects"][0]["id"], "table")
            self.assertEqual({item["id"]: item.get("relation") for item in spec["objects"]},
                             {"table": None, "cup": "on", "chair": "left_of"})
            _, manifest = build_scene(spec, catalog)
            placed = {item["id"]: item["position"] for item in manifest["objects"]}
            self.assertGreater(placed["cup"][2], placed["table"][2])
            self.assertLess(placed["chair"][0], placed["table"][0])
            cycle = {"schema": "ssui.scene-layout/1", "objects": [
                {"id": name, "asset": name} for name in ("table", "chair")]}
            with self.assertRaisesRegex(ValueError, "Cyclic"):
                enforce_text_relations("table to the left of chair; chair to the left of table",
                                       cycle, catalog)

    def test_native_support_and_collision_geometry(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box(extents=(2, 2, 2)).export(assets / "table.glb")
            trimesh.creation.box(extents=(0.4, 0.4, 0.4)).export(assets / "cup.glb")
            catalog = asset_catalog(assets)
            scene, manifest = build_scene({"schema": "ssui.scene-layout/1", "objects": [
                {"id": "table", "asset": "table", "relation": "floor"},
                {"id": "cup", "asset": "cup", "relation": "on", "relative_to": "table"}]}, catalog)
            self.assertEqual(len(scene.geometry), 2)
            self.assertAlmostEqual(manifest["objects"][0]["position"][2], 1.0)
            self.assertAlmostEqual(manifest["objects"][1]["position"][2], 2.25)
            bounds = {}
            for node in scene.graph.nodes_geometry:
                matrix, geometry = scene.graph.get(node)
                bounds[node.split(".")[0]] = transformed_bounds(scene.geometry[geometry].bounds, matrix)
            self.assertLess(penetration_depth(bounds["table"], bounds["cup"])[2], 0)

    def test_overlapping_furniture_is_separated(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box(extents=(2, 2, 2)).export(assets / "box.glb")
            scene, manifest = build_scene({"schema": "ssui.scene-layout/1", "objects": [
                {"id": "a", "asset": "box", "position": [0, 0, 1]},
                {"id": "b", "asset": "box", "position": [0.5, 0, 1]}]}, asset_catalog(assets))
            self.assertEqual(len(scene.geometry), 2)
            self.assertNotEqual(manifest["objects"][1]["collision_correction"], [0, 0, 0])

    def test_collision_correction_stays_inside_room_and_support(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box(extents=(1, 1, 1)).export(assets / "box.glb")
            trimesh.creation.box(extents=(2, 2, 1)).export(assets / "table.glb")
            catalog = asset_catalog(assets)
            _, manifest = build_scene({"schema": "ssui.scene-layout/1",
                                       "room": {"size": [3, 3, 3]}, "objects": [
                {"id": "a", "asset": "box", "position": [-0.8, 0, 0.5]},
                {"id": "b", "asset": "box", "position": [-0.8, 0, 0.5]}]}, catalog)
            self.assertLessEqual(abs(manifest["objects"][1]["position"][0]), 1.0)
            with self.assertRaisesRegex(ValueError, "room or support bounds"):
                build_scene({"schema": "ssui.scene-layout/1", "room": {"size": [3, 3, 3]},
                             "objects": [{"asset": "box", "position": [2, 0, 0.5]}]}, catalog)
            with self.assertRaisesRegex(ValueError, "room or support bounds"):
                build_scene({"schema": "ssui.scene-layout/1", "objects": [
                    {"id": "table", "asset": "box"},
                    {"id": "large", "asset": "table", "relation": "on", "relative_to": "table"}]}, catalog)

    def test_room_floor_and_walls_are_separate_nodes(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box().export(assets / "chair.glb")
            scene, manifest = build_scene({"schema": "ssui.scene-layout/1",
                                           "room": {"size": [8, 6, 3]},
                                           "objects": [{"asset": "chair"}]}, asset_catalog(assets))
            self.assertEqual(manifest["room"]["size"], [8.0, 6.0, 3.0])
            self.assertEqual(len(scene.geometry), 6)
            self.assertIn("room.floor", scene.graph.nodes_geometry)
            floor_plan, _ = build_scene({"schema": "ssui.scene-layout/1",
                                         "room": {"size": [8, 6, 3]}, "objects": []}, asset_catalog(assets))
            self.assertEqual(len(floor_plan.geometry), 5)

    def test_wall_and_ceiling_constraints(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box(extents=(0.5, 0.2, 0.5)).export(assets / "lamp.glb")
            scene, manifest = build_scene({"schema": "ssui.scene-layout/1",
                                           "room": {"size": [8, 6, 3]},
                                           "objects": [
                                               {"id": "sconce", "asset": "lamp", "relation": "wall_left"},
                                               {"id": "light", "asset": "lamp", "relation": "ceiling"}
                                           ]}, asset_catalog(assets))
            self.assertEqual(len(scene.geometry), 7)
            self.assertEqual([x["stage"] for x in manifest["objects"]],
                             ["wall_mounted", "ceiling_mounted"])
            self.assertLess(manifest["objects"][0]["position"][0], -3)
            self.assertGreater(manifest["objects"][1]["position"][2], 2)

    def test_floor_plan_door_and_window_openings(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            assets = Path(folder)
            trimesh.creation.box().export(assets / "box.glb")
            scene, manifest = build_scene({"schema": "ssui.scene-layout/1",
                                           "room": {"size": [8, 6, 3], "openings": [
                                               {"wall": "front", "kind": "door", "width": 1, "height": 2},
                                               {"wall": "left", "kind": "window", "width": 1,
                                                "bottom": 1, "height": 1}]},
                                           "objects": []}, asset_catalog(assets))
            self.assertEqual(len(manifest["room"]["openings"]), 2)
            self.assertIn("room.wall.front.top", scene.graph.nodes_geometry)
            self.assertIn("room.wall.left.bottom", scene.graph.nodes_geometry)
            self.assertNotIn("room.wall.front.full", scene.graph.nodes_geometry)

    def test_stage_snapshots_and_resume(self):
        root = Path(__file__).resolve().parents[1] / ".build"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            base = Path(folder)
            assets = base / "assets"
            assets.mkdir()
            trimesh.creation.box(extents=(1, 1, 1)).export(assets / "chair.glb")
            trimesh.creation.box(extents=(0.3, 0.3, 0.3)).export(assets / "picture.glb")
            first = {"schema": "ssui.scene-layout/1", "room": {"size": [6, 6, 3]},
                     "objects": [{"id": "chair-1", "asset": "chair", "relation": "floor"}]}
            generate_scene("chair", assets, base / "first", first, stop_stage="furniture")
            floor_state = base / "first/stages/floor_plan/scene.json"
            furniture_state = base / "first/stages/furniture/scene.json"
            self.assertEqual(len(json.loads(floor_state.read_text(encoding="utf-8"))["objects"]), 0)
            self.assertEqual(len(json.loads(furniture_state.read_text(encoding="utf-8"))["objects"]), 1)
            self.assertTrue((base / "first/stages/floor_plan/preview.png").is_file())
            self.assertTrue((base / "first/stages/furniture/preview.png").is_file())
            self.assertFalse((base / "first/stages/wall_mounted").exists())
            addition = {"schema": "ssui.scene-layout/1", "objects": [
                {"id": "picture-1", "asset": "picture", "relation": "wall_back"}]}
            generate_scene("picture on back wall", assets, base / "second", addition,
                           stop_stage="wall_mounted", resume_from=furniture_state)
            result = json.loads((base / "second/scene.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in result["objects"]], ["chair-1", "picture-1"])
            self.assertEqual(result["objects"][1]["stage"], "wall_mounted")
            self.assertTrue((base / "second/stages/wall_mounted/scene.glb").is_file())
            with self.assertRaisesRegex(ValueError, "duplicate IDs"):
                generate_scene("chair again", assets, base / "duplicate", first,
                               resume_from=furniture_state)
            with self.assertRaisesRegex(ValueError, "Invalid stop stage"):
                generate_scene("chair", assets, base / "invalid", first, stop_stage="unknown")
            trimesh.creation.icosphere().export(assets / "chair.glb")
            with self.assertRaisesRegex(ValueError, "Asset changed"):
                generate_scene("resume", assets, base / "changed", addition,
                               resume_from=furniture_state)


if __name__ == "__main__":
    unittest.main()
