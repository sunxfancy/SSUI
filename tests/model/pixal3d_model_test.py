import os
import tempfile
import unittest

import torch
from PIL import Image as PILImage

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
@unittest.skipUnless(
    torch.cuda.is_available() and (torch.version.cuda or torch.version.hip),
    "Pixal3D 原生算子需要 CUDA 或 ROCm",
)
class TestPixal3DModel(unittest.TestCase):
    def test_pixal3d_generates_glb(self):
        from ssui.base import Image
        from ssui.config import SSUIConfig
        from ssui_3dmodel.Pixal3D import GenPixal3DModel, Pixal3DModel

        model_path = download_if_needed("pixal3d")
        model = Pixal3DModel.load(str(model_path), low_vram=True)
        config = SSUIConfig()
        config.set_prepared(False)
        node_config = config("Generate Pixal3D Model")
        node_config["auto_camera"] = False
        node_config["fov_degrees"] = 30
        node_config["resolution"] = 1024

        mesh = GenPixal3DModel(
            node_config,
            model,
            Image(PILImage.new("RGB", (512, 512), "white")),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pixal3d.glb")
            mesh._model.export(path, extension_webp=True)
            self.assertGreater(os.path.getsize(path), 0)
