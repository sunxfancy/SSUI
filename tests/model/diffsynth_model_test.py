import os
import tempfile
import unittest

import torch

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestDiffSynthModel(unittest.TestCase):
    def test_diffsynth(self):
        from diffsynth import ModelManager, SDImagePipeline, SDVideoPipeline, save_video

        sd1_path = str(download_if_needed("diffsynth", "sd1"))
        animatediff_path = str(download_if_needed("diffsynth", "animatediff"))

        use_cuda = torch.cuda.is_available()
        dtype = torch.float16 if use_cuda else torch.float32
        manager = ModelManager(torch_dtype=dtype, device="cuda" if use_cuda else "cpu")
        manager.load_models([sd1_path, animatediff_path])

        pipe_image = SDImagePipeline.from_model_manager(manager)
        image = pipe_image(
            prompt="lightning storm, sea",
            negative_prompt="",
            cfg_scale=7.5,
            num_inference_steps=1,
            height=32,
            width=32,
        )
        self.assertIsNotNone(image)

        pipe_video = SDVideoPipeline.from_model_manager(manager)
        video = pipe_video(
            prompt="lightning storm, sea",
            negative_prompt="",
            cfg_scale=7.5,
            num_frames=4,
            num_inference_steps=1,
            height=32,
            width=32,
        )
        self.assertIsNotNone(video)
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "output.mp4")
            save_video(video, output, fps=8)
            self.assertTrue(os.path.exists(output))
