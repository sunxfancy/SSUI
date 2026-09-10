import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from ssui import Prompt
from ssui.config import SSUIConfig


def _remove_3d_stubs():
    saved = {}
    package = sys.modules.get("ssui_3dmodel")
    if package is not None and getattr(package, "__file__", None) is None:
        for name in list(sys.modules):
            if name == "ssui_3dmodel" or name.startswith("ssui_3dmodel."):
                saved[name] = sys.modules.pop(name)
    return saved


class WorldClawTest(unittest.TestCase):
    def setUp(self):
        self.saved = _remove_3d_stubs()

    def tearDown(self):
        if self.saved:
            for name in list(sys.modules):
                if name == "ssui_3dmodel" or name.startswith("ssui_3dmodel."):
                    sys.modules.pop(name, None)
            sys.modules.update(self.saved)

    def test_offline_scene_is_deterministic_and_editable(self):
        from ssui_3dmodel.WorldClaw import GenWorldClawScene, WorldClawModel

        config = SSUIConfig()
        config.set_prepared(False)
        node = config("Generate WorldClaw Scene")
        node["seed"] = 7
        node["world_size"] = 64
        node["terrain_resolution"] = 32
        prompt = Prompt("雪山河谷中的村庄和森林")
        first = GenWorldClawScene(node, WorldClawModel.load(), prompt)._model
        second = GenWorldClawScene(node, WorldClawModel.load(), prompt)._model

        self.assertIn("terrain", first.graph.nodes_geometry)
        self.assertTrue(any(name.startswith("asset.house") for name in first.graph.nodes_geometry))
        self.assertEqual(first.metadata["worldclaw_spec"], second.metadata["worldclaw_spec"])
        self.assertEqual(len(first.geometry), len(second.geometry))
        self.assertGreater(len(first.export(file_type="glb")), 100)

    def test_prepare_registers_controls_without_planning(self):
        from ssui_3dmodel.WorldClaw import GenWorldClawScene, WorldClawModel

        config = SSUIConfig()
        config.set_prepared(True)
        result = GenWorldClawScene(config("World"), WorldClawModel("https://invalid"), Prompt("x"))
        self.assertIsNone(result._model)
        self.assertEqual(set(config._config["World"]), {"seed", "world_size", "terrain_resolution"})

    def test_remote_planner_accepts_wrapped_spec(self):
        from ssui_3dmodel.WorldClaw import _remote_spec, WorldClawModel

        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"spec": {"regions": []}}
        ).encode()
        with patch("urllib.request.urlopen", return_value=response):
            self.assertEqual(
                _remote_spec(WorldClawModel("https://planner", "secret"), "world", 3),
                {"regions": []},
            )


if __name__ == "__main__":
    unittest.main()
