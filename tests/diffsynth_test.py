import unittest
from unittest.mock import patch


class FakeModelManager:
    def __init__(self, **kwargs):
        self.loaded = []

    def load_models(self, paths):
        self.loaded = list(paths)


class FakePipeline:
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_model_manager(cls, manager):
        return cls()

    def __call__(self, *args, **kwargs):
        return object()


class TestDiffSynthWorkflow(unittest.TestCase):
    """给定假 diffsynth 输出，验证文生图/图生视频流程能跑通。"""

    @patch("diffsynth.ModelManager", FakeModelManager)
    @patch("diffsynth.SDImagePipeline", FakePipeline)
    @patch("diffsynth.SDVideoPipeline", FakePipeline)
    @patch("diffsynth.download_models", lambda *args, **kwargs: None)
    @patch("diffsynth.save_video", lambda *args, **kwargs: None)
    def test_diffsynth(self):
        from diffsynth import (
            SDImagePipeline,
            SDVideoPipeline,
            download_models,
            ModelManager,
            save_video,
        )

        download_models(["DreamShaper_8", "AnimateDiff_v2"])

        manager = ModelManager(torch_dtype="float16", device="cpu")
        manager.load_models(
            ["models/stable_diffusion/dreamshaper_8.safetensors", "models/AnimateDiff/mm_sd_v15_v2.ckpt"]
        )

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
        save_video(video, "output.mp4", fps=8)

        self.assertEqual(len(manager.loaded), 2)
