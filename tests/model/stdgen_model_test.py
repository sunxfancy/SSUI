import os
import tempfile
import unittest

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestStdGENModel(unittest.TestCase):
    def test_canonicalize(self):
        from stdgen.pipeline import canonicalize

        model_dir = download_if_needed("stdgen", "canonicalize")
        if not model_dir.exists():
            self.skipTest("StdGEN canonicalize 模型未放置到 TEST_DATA_DIR")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = os.path.join(tmp, "output")
            canonicalize(
                input_dir=tmp,
                output_dir=output_dir,
                pretrained_model_path=str(model_dir),
                validation={},
                use_noise=False,
                unet_from_pretrained_kwargs={},
            )
            self.assertTrue(os.path.isdir(output_dir))

    def test_multiview(self):
        from stdgen.pipeline import multiview

        model_dir = download_if_needed("stdgen", "multiview")
        if not model_dir.exists():
            self.skipTest("StdGEN multiview 模型未放置到 TEST_DATA_DIR")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = os.path.join(tmp, "output", "multiview")
            multiview(
                input_dir=tmp,
                output_dir=output_dir,
                pretrained_path=str(model_dir),
            )
            self.assertTrue(os.path.isdir(output_dir))
