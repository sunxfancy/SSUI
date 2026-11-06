"""Opt-in real MOSS bundle smoke test; never downloads multi-GB weights implicitly."""
import os
from pathlib import Path
import unittest

import torch

from tests.utils import should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "Set SSUI_RUN_MODEL_TESTS=1 for real model tests")
class MOSSImageModelTest(unittest.TestCase):
    def test_local_bundle_generates_image(self):
        model_path = os.environ.get("SSUI_MOSS_IMAGE_MODEL")
        if not model_path:
            self.skipTest("Set SSUI_MOSS_IMAGE_MODEL to a complete local Base/SFT bundle")
        self.assertTrue(Path(model_path).expanduser().is_dir(), "SSUI_MOSS_IMAGE_MODEL must be a local directory")
        if not torch.cuda.is_available():
            self.skipTest("Real MOSS regression requires a CUDA GPU")
        from backend.moss_image.pipeline import MOSSPipeline

        pipe = MOSSPipeline.from_pretrained(model_path, device="cuda", cpu_offload=True)
        try:
            image = pipe('一张写着「你好世界」的海报', width=512, height=512, steps=10, seed=42)
            self.assertEqual(image.size, (512, 512))
            self.assertGreater(max(image.getextrema()[0]) - min(image.getextrema()[0]), 0)
        finally:
            pipe.close()
