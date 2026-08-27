import sys
import types
import unittest
from unittest.mock import patch

import PIL.Image

from ssui.base import Image, Prompt
from ssui.config import SSUIConfig


class _FakePipeline:
    load_count = 0

    @classmethod
    def from_pretrained(cls, model_path, torch_dtype):
        cls.load_count += 1
        instance = cls()
        instance.model_path = model_path
        instance.torch_dtype = torch_dtype
        instance.device = None
        instance.offloaded = False
        instance.calls = []
        return instance

    def enable_model_cpu_offload(self):
        self.offloaded = True

    def to(self, device):
        self.device = device
        return self

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(
            images=[PIL.Image.new("RGB", (kwargs["width"], kwargs["height"]), "blue")]
        )


class TestFlux2Klein(unittest.TestCase):
    def setUp(self):
        _FakePipeline.load_count = 0
        self.diffusers = types.SimpleNamespace(Flux2KleinPipeline=_FakePipeline)

    def test_load_is_cached_and_uses_offload(self):
        from ssui_image import Flux2

        Flux2.Flux2KleinModel.clear_cache()
        with patch.dict(sys.modules, {"diffusers": self.diffusers}), patch.object(
            Flux2, "_resolve_device", return_value="cuda"
        ):
            first = Flux2.Flux2KleinModel.load("fake/flux2", cpu_offload=True)
            second = Flux2.Flux2KleinModel.load("fake/flux2", cpu_offload=True)

        self.assertIs(first.pipeline, second.pipeline)
        self.assertTrue(first.pipeline.offloaded)
        self.assertEqual(_FakePipeline.load_count, 1)

    def test_generate_accepts_multiple_references(self):
        from ssui_image import Flux2

        config = SSUIConfig()
        pipeline = _FakePipeline.from_pretrained("fake/flux2", None)
        model = Flux2.Flux2KleinModel("fake/flux2", pipeline)
        references = [
            Image(PIL.Image.new("RGB", (32, 32), "red")),
            Image(PIL.Image.new("RGB", (32, 32), "green")),
        ]

        result = Flux2.Flux2KleinGenerate(
            config("Generate"), model, Prompt("combine image 1 and image 2"), references
        )

        self.assertIsInstance(result._image, PIL.Image.Image)
        self.assertEqual(len(pipeline.calls[0]["image"]), 2)
        self.assertEqual(pipeline.calls[0]["num_inference_steps"], 4)
        self.assertEqual(pipeline.calls[0]["guidance_scale"], 1.0)

    def test_generate_without_references_uses_text_to_image_mode(self):
        from ssui_image import Flux2

        config = SSUIConfig()
        pipeline = _FakePipeline.from_pretrained("fake/flux2", None)
        model = Flux2.Flux2KleinModel("fake/flux2", pipeline)

        Flux2.Flux2KleinGenerate(
            config("Generate"), model, Prompt("a tiny robot"), []
        )

        self.assertIsNone(pipeline.calls[0]["image"])

    def test_rejects_more_than_four_references(self):
        from ssui_image import Flux2

        config = SSUIConfig()
        model = Flux2.Flux2KleinModel("fake/flux2", _FakePipeline())
        references = [Image(PIL.Image.new("RGB", (8, 8))) for _ in range(5)]
        with self.assertRaisesRegex(ValueError, "at most four"):
            Flux2.Flux2KleinGenerate(
                config("Generate"), model, Prompt("too many"), references
            )


if __name__ == "__main__":
    unittest.main()
