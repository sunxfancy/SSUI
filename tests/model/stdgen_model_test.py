import tempfile
import unittest

from pathlib import Path
import numpy as np
from PIL import Image
import yaml

from tests.utils import download_if_needed, should_run_model_tests, model_output_dir


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestStdGENModel(unittest.TestCase):
    def test_canonicalize(self):
        from stdgen.pipeline import canonicalize

        model_dir = download_if_needed("stdgen", "canonicalize")
        if not model_dir.exists():
            self.skipTest("StdGEN canonicalize 模型未放置到 TEST_DATA_DIR")

        config_path = Path(__file__).resolve().parents[2] / "extensions/3D-Model/vendor/stdgen/configs/canonicalization-infer.yaml"
        settings = yaml.safe_load(config_path.read_text())
        with tempfile.TemporaryDirectory() as tmp, model_output_dir("stdgen-canonicalize") as output:
            image = Image.open(Path(__file__).resolve().parents[1] / "typical_building_building.png").convert("RGBA")
            # Retain an explicit alpha channel to avoid downloading a separate
            # background-removal model during this model's inference test.
            image.putpixel((0, 0), (0, 0, 0, 0))
            image.save(Path(tmp) / "input.png")
            canonicalize(
                input_dir=tmp,
                output_dir=output,
                pretrained_model_path=str(model_dir),
                validation={"guidance_scale": 5.0, "use_inv_latent": False},
                use_noise=False,
                unet_condition_type="image",
                unet_from_pretrained_kwargs=settings["unet_from_pretrained_kwargs"],
                timestep=4,
                width_input=320,
                height_input=512,
            )
            result = np.asarray(Image.open(Path(output) / "input.png"))
            self.assertEqual(result.shape[:2], (512, 320))
            self.assertGreater(float(result.std()), 1.0)

    def test_multiview(self):
        from stdgen.pipeline import multiview

        model_dir = download_if_needed("stdgen", "multiview")
        if not model_dir.exists():
            self.skipTest("StdGEN multiview 模型未放置到 TEST_DATA_DIR")

        with tempfile.TemporaryDirectory() as tmp, model_output_dir("stdgen-multiview") as output:
            with Image.open(Path(__file__).resolve().parents[1] / "typical_building_building.png") as image:
                image.convert("RGB").save(Path(tmp) / "input.png")
            multiview(
                input_dir=tmp,
                output_dir=output,
                pretrained_path=str(model_dir),
                num_levels=1,
                width_input=320,
                height_input=512,
            )
            result_dir = Path(output) / "input" / "level0"
            for kind in ("color", "normal"):
                for view in range(6):
                    pixels = np.asarray(Image.open(result_dir / f"{kind}_{view}.png"))
                    self.assertTrue(np.isfinite(pixels).all())
                    self.assertGreater(float(pixels.std()), 1.0)
