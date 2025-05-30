import unittest
from tests.utils import should_run_slow_tests


@unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
class TestDiffSynth(unittest.TestCase):
    def test_diffsynth(self):
        import torch
        from diffsynth import ModelManager, SDImagePipeline, SDVideoPipeline, save_video, download_models
        download_models(["DreamShaper_8", "AnimateDiff_v2"])

        # Load models
        model_manager = ModelManager(torch_dtype=torch.float16, device="cuda")
        model_manager.load_models([
            "models/stable_diffusion/dreamshaper_8.safetensors",
            "models/AnimateDiff/mm_sd_v15_v2.ckpt",
        ])

        # Text -> Image
        pipe_image = SDImagePipeline.from_model_manager(model_manager)
        torch.manual_seed(0)
        image = pipe_image(
            prompt = "lightning storm, sea",
            negative_prompt = "",
            cfg_scale=7.5,
            num_inference_steps=30, height=512, width=768,
        )

        # Text + Image -> Video (6GB VRAM is enough!)
        pipe = SDVideoPipeline.from_model_manager(model_manager)
        output_video = pipe(
            prompt = "lightning storm, sea",
            negative_prompt = "",
            cfg_scale=7.5,
            num_frames=64,
            num_inference_steps=10, height=512, width=768,
            animatediff_batch_size=16, animatediff_stride=1, input_frames=[image]*64, denoising_strength=0.9,
        )

        # Save images and video
        save_video(output_video, "output_video.mp4", fps=30)