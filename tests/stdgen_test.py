import os
import tempfile
import unittest
from unittest.mock import patch


def fake_canonicalize(input_dir, output_dir, **kwargs):
    os.makedirs(output_dir, exist_ok=True)


def fake_multiview(input_dir, output_dir, **kwargs):
    os.makedirs(output_dir, exist_ok=True)


class StdGENWorkflowTest(unittest.TestCase):
    """给定假 StdGEN 输出，验证 canonicalize / multiview 流程能跑通。"""

    @patch("stdgen.pipeline.canonicalize", fake_canonicalize)
    def test_canonicalize(self):
        from stdgen.pipeline import canonicalize

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = os.path.join(tmp, "output")
            canonicalize(
                input_dir=tmp,
                output_dir=output_dir,
                pretrained_model_path="fake/StdGEN-canonicalize-1024",
                validation={},
                use_noise=False,
                unet_from_pretrained_kwargs={},
            )
            self.assertTrue(os.path.isdir(output_dir))

    @patch("stdgen.pipeline.multiview", fake_multiview)
    def test_multiview(self):
        from stdgen.pipeline import multiview

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = os.path.join(tmp, "output", "multiview")
            multiview(
                input_dir=tmp,
                output_dir=output_dir,
                pretrained_path="fake/StdGEN-multiview-1024",
            )
            self.assertTrue(os.path.isdir(output_dir))
