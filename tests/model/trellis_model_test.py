import os
import unittest
from pathlib import Path

from PIL import Image as PILImage

from tests.utils import download_if_needed, should_run_model_tests, model_output_dir


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestTrellisModel(unittest.TestCase):
    def test_trellis(self):
        import numpy as np
        import trimesh
        from ssui.base import Image
        from ssui.config import SSUIConfig
        from ssui_3dmodel.Trellis import TrellisModel, GenModel

        model_dir = download_if_needed("trellis")
        model = TrellisModel.load(
            str(model_dir),
            dinov2_repository=os.environ.get('SSUI_DINOV2_REPO'),
            dinov2_weights=os.environ.get('SSUI_DINOV2_WEIGHTS'),
        )
        with PILImage.open(Path(__file__).resolve().parents[1] / "typical_building_building.png") as source:
            image = Image(source.copy())
        config = SSUIConfig()
        config("Generate 3D")['sparse_structure_steps'] = 12
        config("Generate 3D")['slat_steps'] = 12
        mesh = GenModel(config("Generate 3D"), model, image)
        with model_output_dir("trellis") as tmp:
            path = os.path.join(tmp, "sample.glb")
            mesh._model.export(path)
            reloaded = trimesh.load(path, force="mesh")
            self.assertGreater(len(reloaded.vertices), 0)
            self.assertGreater(len(reloaded.faces), 0)
            self.assertTrue(np.isfinite(reloaded.vertices).all())
