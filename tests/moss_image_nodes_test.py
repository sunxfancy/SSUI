"""Exercise node contracts through the normal Image extension import path."""
import unittest
from unittest.mock import Mock, patch

from PIL import Image as PILImage

from ssui.base import Image, Prompt
from ssui.config import SSUIConfig


class MOSSImageNodesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ssui_image import MOSSImage
        cls.nodes = MOSSImage

    def tearDown(self):
        self.nodes.MOSSImageModel.clear_cache()

    def test_loader_caches_by_revision_and_clears_pipeline(self):
        from backend.moss_image.pipeline import MOSSPipeline

        with patch.object(MOSSPipeline, "from_pretrained", side_effect=lambda *a, **kw: Mock()) as load:
            first = self.nodes.MOSSImageModel.load("test/moss", revision="a")
            second = self.nodes.MOSSImageModel.load("test/moss", revision="a")
            third = self.nodes.MOSSImageModel.load("test/moss", revision="b")
            self.assertIs(first.pipeline, second.pipeline)
            self.assertIsNot(first.pipeline, third.pipeline)
            self.assertEqual(load.call_count, 2)
            self.nodes.MOSSImageModel.clear_cache()
            first.pipeline.close.assert_called_once()
            third.pipeline.close.assert_called_once()

    def test_generation_forwards_layout_and_sampling_defaults(self):
        pipeline = Mock(return_value=PILImage.new("RGB", (32, 32)))
        config = SSUIConfig()("Generate")
        layout = '{"summary":{"caption":"海报"},"items":[]}'
        result = self.nodes.MOSSImageGenerate(config, self.nodes.MOSSImageModel(pipeline=pipeline),
                                               Prompt(layout), Prompt(""))
        self.assertIsInstance(result, Image)
        self.assertEqual(pipeline.call_args.kwargs["prompt"], layout)
        self.assertEqual(pipeline.call_args.kwargs["steps"], 50)
        self.assertEqual(pipeline.call_args.kwargs["shift"], 5)
        self.assertEqual(pipeline.call_args.kwargs["uncond_skip_layers"], (22,))
        config["skip_negative_layer_22"] = False
        self.nodes.MOSSImageGenerate(config, self.nodes.MOSSImageModel(pipeline=pipeline), Prompt("cat"), Prompt(""))
        self.assertEqual(pipeline.call_args.kwargs["uncond_skip_layers"], ())

    def test_prepare_does_not_require_loaded_weights(self):
        config = SSUIConfig()("Prepare")
        config.set_prepared()
        result = self.nodes.MOSSImageGenerate(config, self.nodes.MOSSImageModel(), Prompt("cat"), Prompt(""))
        self.assertIsNone(result._image)
        config.set_prepared(False)
        with self.assertRaisesRegex(ValueError, "not loaded"):
            self.nodes.MOSSImageGenerate(config, self.nodes.MOSSImageModel(), Prompt("cat"), Prompt(""))
