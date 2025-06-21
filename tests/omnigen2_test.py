import unittest
from tests.utils import should_run_slow_tests

@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestOmniGen2(unittest.TestCase):
    def test_omnigenerator(self):
        import torch
        from torchvision.transforms.functional import to_tensor

        import accelerate
        from omnigen2.pipelines.omnigen2.pipeline_omnigen2 import OmniGen2Pipeline
        from omnigen2.utils.img_util import create_collage

        