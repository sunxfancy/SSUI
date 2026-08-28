import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image as PILImage

from ssui.base import Image, Prompt
from ssui.config import SSUIConfig
from ss_executor.loader import SSLoader


# tests/diffsynth_test.py installs a lightweight top-level diffsynth stub while
# test discovery runs. Add the two package-shaped submodules used by this node
# so this unit test remains independent from the heavyweight runtime import.
@dataclass
class FakeModelConfig:
    path: object = None
    model_id: str = None
    origin_file_pattern: object = None
    download_resource: str = "ModelScope"
    offload_device: object = None
    offload_dtype: object = None
    local_model_path: str = None


class FakeQwenImagePipeline:
    @staticmethod
    def from_pretrained(**_kwargs):
        return Mock()


diffsynth = sys.modules.setdefault("diffsynth", types.ModuleType("diffsynth"))
diffsynth.__path__ = []
pipelines = sys.modules.setdefault(
    "diffsynth.pipelines", types.ModuleType("diffsynth.pipelines")
)
qwen_pipeline = types.ModuleType("diffsynth.pipelines.qwen_image")
qwen_pipeline.QwenImagePipeline = FakeQwenImagePipeline
utils = types.ModuleType("diffsynth.utils")
utils.ModelConfig = FakeModelConfig
sys.modules["diffsynth.pipelines.qwen_image"] = qwen_pipeline
sys.modules["diffsynth.utils"] = utils
diffsynth.pipelines = pipelines

from ssui_video.QwenImage import (
    QWEN_IMAGE_EDIT_MODEL_ID,
    QwenImageEdit,
    QwenImageEditModel,
    QwenImageGenerate,
    QwenImageModel,
    QwenPixelArtEdit,
    QwenPixelArtGenerate,
    _load_pipeline,
)


class TestQwenImageNodes(unittest.TestCase):
    def _config(self):
        name = "Qwen Image"
        config = SSUIConfig()(name)
        config._update[name] = {
            "seed": 7,
            "width": 512,
            "height": 512,
            "steps": 4,
            "CFG": 3.5,
            "tiled": False,
            "auto_resize_reference": True,
        }
        return config

    def _pixel_config(self, *, edit=False):
        name = "Qwen Pixel Art"
        config = SSUIConfig()(name)
        config._update[name] = {
            "seed": 11,
            "width": 512,
            "height": 512,
            "steps": 20,
            "CFG": 1.0,
            "tiled": False,
            "pixel_width": 64,
            "pixel_height": 64,
            "colors": 24,
            "alpha_threshold": 128,
            "downsample": "box",
            "preview_scale": 4,
        }
        if edit:
            config._update[name]["auto_resize_reference"] = True
        return config

    def test_generate_forwards_reproducible_parameters(self):
        pipe = Mock(return_value=PILImage.new("RGB", (2, 2)))
        result = QwenImageGenerate(
            self._config(), QwenImageModel(pipe=pipe), Prompt("hero"), Prompt("")
        )
        self.assertEqual(result._image.size, (2, 2))
        self.assertEqual(pipe.call_args.kwargs["seed"], 7)
        self.assertEqual(pipe.call_args.kwargs["num_inference_steps"], 4)

    def test_edit_wraps_single_reference_for_2509(self):
        pipe = Mock(return_value=PILImage.new("RGB", (2, 2)))
        reference = Image(PILImage.new("RGBA", (4, 4), (1, 2, 3, 255)))
        QwenImageEdit(
            self._config(),
            QwenImageEditModel(pipe=pipe),
            reference,
            Prompt("walk right"),
            Prompt(""),
        )
        edit_images = pipe.call_args.kwargs["edit_image"]
        self.assertEqual(len(edit_images), 1)
        self.assertEqual(edit_images[0].mode, "RGB")

    def test_pixel_art_node_uses_quality_preset_and_finishes_output(self):
        pipe = Mock(return_value=PILImage.new("RGB", (512, 512), (20, 40, 80)))
        result = QwenPixelArtGenerate(
            self._pixel_config(),
            QwenImageModel(pipe=pipe),
            Prompt("blue-haired adventurer"),
            Prompt("blurry"),
        )

        self.assertEqual(result._image.size, (256, 256))
        self.assertEqual(pipe.call_args.kwargs["num_inference_steps"], 20)
        self.assertEqual(pipe.call_args.kwargs["cfg_scale"], 1.0)
        self.assertLessEqual(len(result._image.getcolors(maxcolors=256)), 24)

    def test_pixel_art_edit_forwards_reference_and_finishes_output(self):
        pipe = Mock(return_value=PILImage.new("RGB", (512, 512), (80, 40, 20)))
        reference = Image(PILImage.new("RGBA", (64, 64), (1, 2, 3, 255)))
        result = QwenPixelArtEdit(
            self._pixel_config(edit=True),
            QwenImageEditModel(pipe=pipe),
            reference,
            Prompt("turn right"),
            Prompt("blurry"),
        )

        self.assertEqual(result._image.size, (256, 256))
        self.assertEqual(len(pipe.call_args.kwargs["edit_image"]), 1)

    @patch("ssui_video.QwenImage.torch.cuda.is_available", return_value=True)
    @patch("ssui_video.QwenImage.QwenImagePipeline.from_pretrained")
    def test_edit_loader_uses_processor_and_cpu_offload(self, load, _cuda):
        pipe = Mock()
        load.return_value = pipe
        _load_pipeline(QWEN_IMAGE_EDIT_MODEL_ID, edit=True, low_vram=True)
        kwargs = load.call_args.kwargs
        self.assertIsNotNone(kwargs["processor_config"])
        self.assertIsNone(kwargs["tokenizer_config"])
        self.assertTrue(all(c.offload_device == "cpu" for c in kwargs["model_configs"]))
        pipe.enable_vram_management.assert_called_once_with(vram_limit=None)

    @patch.dict(
        "ssui_video.QwenImage.os.environ",
        {"SSUI_QWEN_IMAGE_VRAM_LIMIT_GIB": "24"},
        clear=False,
    )
    @patch("ssui_video.QwenImage.torch.cuda.is_available", return_value=True)
    @patch("ssui_video.QwenImage.QwenImagePipeline.from_pretrained")
    def test_loader_can_reserve_activation_vram(self, load, _cuda):
        pipe = Mock()
        load.return_value = pipe
        _load_pipeline(QWEN_IMAGE_EDIT_MODEL_ID, edit=True, low_vram=True)
        pipe.enable_vram_management.assert_called_once_with(vram_limit=24.0)

    @patch("ssui_video.QwenImage.torch.cuda.is_available", return_value=True)
    @patch("ssui_video.QwenImage.QwenImagePipeline.from_pretrained")
    def test_model_load_exposes_vram_limit(self, load, _cuda):
        pipe = Mock()
        load.return_value = pipe

        QwenImageModel.load(vram_limit_gib=24.0)

        pipe.enable_vram_management.assert_called_once_with(vram_limit=24.0)

    def test_official_workflow_discovers_integrated_pixel_nodes(self):
        workflow_path = (
            Path(__file__).resolve().parents[1]
            / "desktop"
            / "src-tauri"
            / "workflow"
            / "pixel-assets"
            / "workflow-qwen.py"
        )
        loader = SSLoader(use_sandbox=False)
        loader.load(str(workflow_path))
        loader.Execute()

        names = {func.__name__ for func, _params, _return in loader.callables}
        self.assertEqual(
            names, {"text_to_pixel_asset", "reference_to_pixel_asset"}
        )
        config = loader.GetConfig("text_to_pixel_asset")
        node = config["Qwen Pixel Art"]
        self.assertEqual(node["width"]["default"], 512)
        self.assertEqual(node["steps"]["default"], 20)
        self.assertEqual(node["pixel_width"]["default"], 64)
        self.assertEqual(node["preview_scale"]["default"], 4)


if __name__ == "__main__":
    unittest.main()
