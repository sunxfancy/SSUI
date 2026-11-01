import os
import unittest
import numpy as np
import trimesh
from tests.utils import download_if_needed, should_run_model_tests, model_output_dir


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestShapEModel(unittest.TestCase):
    def test_text_to_mesh(self):
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_3dmodel.ShapE import ShapEModel, ShapETextToMesh

        model = ShapEModel.load(str(download_if_needed("shap_e")))
        config = SSUIConfig()
        config.set_prepared(False)
        mesh = ShapETextToMesh(config("Generate mesh"), model,
                              Prompt("a wooden chair"))
        self.assertGreater(len(mesh._model.vertices), 0)
        self.assertGreater(len(mesh._model.faces), 0)
        self.assertTrue(np.isfinite(mesh._model.vertices).all())
        with model_output_dir("shap_e") as output:
            path = os.path.join(output, "chair.glb")
            mesh._model.export(path)
            reloaded = trimesh.load(path, force="mesh")
            self.assertGreater(len(reloaded.faces), 0)
