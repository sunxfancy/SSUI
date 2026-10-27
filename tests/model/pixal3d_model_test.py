import os
import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image as PILImage

from tests.utils import should_run_model_tests


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
        from ssui_3dmodel.runtime import require_glb_runtime

        # Check native plugins before the multi-GB snapshot download.
        require_glb_runtime()
        # Load only the checkpoints referenced by the single-image pipeline;
        # downloading the whole snapshot also fetches unused multi-view weights.
        model = Pixal3DModel.load(low_vram=True)
        config = SSUIConfig()
        config.set_prepared(False)
        node_config = config("Generate Pixal3D Model")
        node_config["auto_camera"] = False
        node_config["fov_degrees"] = 30
        node_config["resolution"] = 1024

        mesh = GenPixal3DModel(
            node_config,
            model,
            Image(PILImage.open(Path(__file__).parents[1] / "typical_building_building.png")),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pixal3d.glb")
            mesh._model.export(path, extension_webp=True)
            self.assertGreater(os.path.getsize(path), 0)
