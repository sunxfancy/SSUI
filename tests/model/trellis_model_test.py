import os
import tempfile
import unittest

import torch
from PIL import Image as PILImage

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestTrellisModel(unittest.TestCase):
    def test_trellis(self):
        from trellis.pipelines import TrellisImageTo3DPipeline
        from trellis.utils import postprocessing_utils

        download_if_needed("trellis")
        pipeline = TrellisImageTo3DPipeline.from_pretrained("jetx/trellis-image-large")
        if torch.cuda.is_available():
            pipeline.cuda()

        outputs = pipeline.run(PILImage.new("RGB", (256, 256)), seed=1)
        self.assertIn("gaussian", outputs)
        self.assertIn("mesh", outputs)

        with tempfile.TemporaryDirectory() as tmp:
            glb = postprocessing_utils.to_glb(
                outputs["gaussian"][0],
                outputs["mesh"][0],
                simplify=0.95,
                texture_size=256,
            )
            path = os.path.join(tmp, "sample.glb")
            glb.export(path)
            self.assertTrue(os.path.exists(path))
