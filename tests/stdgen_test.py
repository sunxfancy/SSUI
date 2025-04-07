import unittest
from tests.utils import should_run_slow_tests

class StdGENTest(unittest.TestCase):
    @unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
    def test_canonicalize(self):
        from stdgen.pipeline import canonicalize
        canonicalize(
            input_dir="tests/data/",
            output_dir="tests/output",
            pretrained_model_path="tests/data/StdGEN/StdGEN-canonicalize-1024",
            validation={
                "guidance_scale": 5.0,
                "timestep": 40,
                "width_input": 640,
                "height_input": 1024,
                "use_inv_latent": False
            },
            use_noise=False,
            unet_condition_type="image",
            unet_from_pretrained_kwargs={
                "camera_embedding_type": 'e_de_da_sincos',
                "projection_class_embeddings_input_dim": 10,
                "joint_attention": False,
                "num_views": 1,
                "sample_size": 96,
                "zero_init_conv_in": False,
                "zero_init_camera_projection": False,
                "in_channels": 4,
                "use_safetensors": True
            }
        )

    @unittest.skipIf(not should_run_slow_tests(), "Skipping slow test")
    def test_multiview(self):
        from stdgen.pipeline import multiview
        multiview(
            input_dir="tests/output/",
            output_dir="tests/output/multiview",
            pretrained_path="tests/data/StdGEN/StdGEN-multiview-1024",
        )
