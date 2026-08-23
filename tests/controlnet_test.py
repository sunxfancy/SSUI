"""ControlNet（SD1.5 / SDXL / FLUX）支持的后端测试。

覆盖三类内容：
1. ControlNet / FluxControlNet API 字段的校验规则；
2. load_controlnet / load_vae 模型加载辅助函数；
3. SD1 / SDXL / FLUX 工作流节点：ControlNet 节点加载、denoise 透传，
   以及示例 workflow 脚本能注册 txt2imgWithControlNet 并完成 prepare pass。
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image as PILImage

from ssui.base import Prompt
from ssui.config import SSUIConfig

from tests.fakes.sd import (
    FakeCondition,
    FakeFluxModel,
    FakeLatent,
    FakeSD1Model,
    FakeSDXLModel,
    fake_clip,
)


def _loaded_model():
    """构造一个满足 pydantic LoadedModel 校验的最小实例。"""
    from backend.model_manager.load.load_base import LoadedModel

    return LoadedModel(
        config=None,
        cache_record=MagicMock(),
        cache=MagicMock(),
    )


def _make_control_image(path: str) -> str:
    PILImage.new("RGB", (64, 64), (200, 120, 40)).save(path)
    return path


class TestControlNetFieldValidation(unittest.TestCase):
    """ControlNet / FluxControlNet pydantic 字段的校验。"""

    def test_apply_range_rejects_inverted_range(self):
        from ssui_image.api.denoise import ApplyRange

        with self.assertRaises(ValueError):
            ApplyRange(begin_step_percent=0.8, end_step_percent=0.4)

    def test_apply_range_accepts_valid_range(self):
        from ssui_image.api.denoise import ApplyRange

        r = ApplyRange(begin_step_percent=0.2, end_step_percent=0.9)
        self.assertEqual(r.begin_step_percent, 0.2)
        self.assertEqual(r.end_step_percent, 0.9)

    def test_control_weight_range(self):
        from ssui_image.api.denoise import ControlNet, FluxControlNet

        base = {
            "image": PILImage.new("RGB", (8, 8)),
            "control_model": _loaded_model(),
        }
        for cls in (ControlNet, FluxControlNet):
            with self.assertRaises(ValueError):
                cls(**base, control_weight=3.0)
            with self.assertRaises(ValueError):
                cls(**base, control_weight=-2.0)
            field = cls(**base, control_weight=1.5)
            self.assertEqual(field.control_weight, 1.5)


class TestLoadControlNetHelpers(unittest.TestCase):
    """load_controlnet / load_vae 辅助函数。"""

    @patch("ssui_image.api.model.ModelProbe")
    @patch("ssui_image.api.model._load_model_service")
    def test_load_controlnet(self, mock_load, mock_probe):
        from ssui_image.api.model import (
            ControlNetModel,
            load_controlnet,
        )

        mock_probe.probe.return_value = MagicMock()
        mock_load.return_value = _loaded_model()

        result = load_controlnet(MagicMock(), "fake/controlnet.safetensors")

        self.assertIsInstance(result, ControlNetModel)
        mock_probe.probe.assert_called_once()
        mock_load.assert_called_once()

    @patch("ssui_image.api.model.ModelProbe")
    @patch("ssui_image.api.model._load_model_service")
    def test_load_vae(self, mock_load, mock_probe):
        from ssui_image.api.model import VAEModel, load_vae

        mock_probe.probe.return_value = MagicMock()
        mock_load.return_value = _loaded_model()

        result = load_vae(MagicMock(), "fake/vae.safetensors")

        self.assertIsInstance(result, VAEModel)
        mock_probe.probe.assert_called_once()
        mock_load.assert_called_once()


class TestSD1ControlNetWorkflow(unittest.TestCase):
    """SD1.5 ControlNet 节点加载 + denoise 透传。"""

    def setUp(self):
        self.config = SSUIConfig()
        self.positive = Prompt("a beautiful girl, masterpiece, best quality")
        self.negative = Prompt("a bad image")

    @patch("ssui_image.SD1.load_controlnet")
    def test_node_load(self, mock_load_controlnet):
        from ssui_image.SD1 import SD1ControlNet

        mock_load_controlnet.return_value = MagicMock()
        mock_load_controlnet.return_value.controlnet = _loaded_model()
        with tempfile.TemporaryDirectory() as tmp:
            image_path = _make_control_image(os.path.join(tmp, "pose.png"))
            node = SD1ControlNet.load(
                "fake/controlnet.safetensors",
                image_path,
                weight=0.7,
                resize_mode="crop_resize",
            )

        self.assertEqual(node.path, "fake/controlnet.safetensors")
        self.assertEqual(node.weight, 0.7)
        self.assertEqual(node.resize_mode, "crop_resize")
        self.assertEqual(node.image.size, (64, 64))
        field = node.to_api_field()
        self.assertEqual(field.control_weight, 0.7)
        self.assertEqual(field.resize_mode, "crop_resize")
        self.assertEqual(field.control_mode, "balanced")

    def test_node_requires_load(self):
        from ssui_image.SD1 import SD1ControlNet

        with self.assertRaises(ValueError):
            SD1ControlNet().to_api_field()

    @patch("ssui_image.SD1.SD1Clip", fake_clip)
    @patch("ssui_image.SD1.denoise_image", return_value=FakeLatent())
    def test_denoise_passes_control_field(self, mock_denoise):
        from ssui_image.SD1 import (
            SD1Clip,
            SD1ControlNet,
            SD1Denoise,
            SD1Latent,
        )

        control = SD1ControlNet(
            path="fake/controlnet.safetensors",
            image_path="",
            controlnet=MagicMock(controlnet=_loaded_model()),
            image=PILImage.new("RGB", (64, 64)),
            weight=0.8,
        )
        positive, negative = SD1Clip(
            self.config("Prompt To Condition"),
            FakeSD1Model(),
            self.positive,
            self.negative,
        )
        latent = SD1Latent(self.config("Create Empty Latent"))
        SD1Denoise(
            self.config("Denoise"),
            FakeSD1Model(),
            latent,
            positive,
            negative,
            control,
        )

        kwargs = mock_denoise.call_args.kwargs
        field = kwargs["control"]
        self.assertEqual(field.control_weight, 0.8)
        self.assertEqual(field.image.size, (64, 64))

    @patch("ssui_image.SD1.SD1Clip", fake_clip)
    @patch("ssui_image.SD1.denoise_image", return_value=FakeLatent())
    def test_denoise_without_control_passes_none(self, mock_denoise):
        from ssui_image.SD1 import (
            SD1Clip,
            SD1Denoise,
            SD1Latent,
        )

        positive, negative = SD1Clip(
            self.config("Prompt To Condition"),
            FakeSD1Model(),
            self.positive,
            self.negative,
        )
        latent = SD1Latent(self.config("Create Empty Latent"))
        SD1Denoise(
            self.config("Denoise"),
            FakeSD1Model(),
            latent,
            positive,
            negative,
        )
        self.assertIsNone(mock_denoise.call_args.kwargs["control"])


class TestSDXLControlNetWorkflow(unittest.TestCase):
    """SDXL ControlNet 节点加载 + denoise 透传。"""

    def setUp(self):
        self.config = SSUIConfig()
        self.positive = Prompt("a beautiful girl in a red dress")
        self.negative = Prompt("a bad image")

    @patch("ssui_image.SDXL.load_controlnet")
    def test_node_load(self, mock_load_controlnet):
        from ssui_image.SDXL import SDXLControlNet

        mock_load_controlnet.return_value = MagicMock(controlnet=_loaded_model())
        with tempfile.TemporaryDirectory() as tmp:
            image_path = _make_control_image(os.path.join(tmp, "depth.png"))
            node = SDXLControlNet.load(
                "fake/controlnet.safetensors",
                image_path,
                weight=0.9,
                control_mode="more_control",
            )

        self.assertEqual(node.weight, 0.9)
        self.assertEqual(node.control_mode, "more_control")
        field = node.to_api_field()
        self.assertEqual(field.control_mode, "more_control")

    @patch("ssui_image.SDXL.SDXLClip", fake_clip)
    @patch("ssui_image.SDXL.denoise_image", return_value=FakeLatent())
    def test_denoise_passes_control_field(self, mock_denoise):
        from ssui_image.SDXL import (
            SDXLClip,
            SDXLControlNet,
            SDXLDenoise,
            SDXLLatent,
        )

        control = SDXLControlNet(
            path="fake/controlnet.safetensors",
            image_path="",
            controlnet=MagicMock(controlnet=_loaded_model()),
            image=PILImage.new("RGB", (64, 64)),
            weight=0.6,
        )
        positive, negative = SDXLClip(
            self.config("Prompt To Condition"),
            FakeSDXLModel(),
            self.positive,
            self.negative,
        )
        latent = SDXLLatent(self.config("Create Empty Latent"))
        SDXLDenoise(
            self.config("Denoise"),
            FakeSDXLModel(),
            latent,
            positive,
            negative,
            control,
        )

        kwargs = mock_denoise.call_args.kwargs
        field = kwargs["control"]
        self.assertEqual(field.control_weight, 0.6)
        self.assertEqual(field.image.size, (64, 64))


class TestFluxControlNetWorkflow(unittest.TestCase):
    """FLUX ControlNet 节点加载 + denoise 透传。"""

    def setUp(self):
        self.config = SSUIConfig()
        self.positive = Prompt("a beautiful girl in a red dress")
        self.negative = Prompt("a bad image")

    @patch("ssui_image.Flux.load_controlnet")
    @patch("ssui_image.Flux.load_vae")
    def test_node_load(self, mock_load_vae, mock_load_controlnet):
        from ssui_image.Flux import FluxControlNet

        mock_load_controlnet.return_value = MagicMock(controlnet=_loaded_model())
        mock_load_vae.return_value = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            image_path = _make_control_image(os.path.join(tmp, "pose.png"))
            node = FluxControlNet.load(
                "fake/controlnet.safetensors",
                image_path,
                vae_path="fake/vae.safetensors",
                weight=0.5,
                instantx_control_mode=4,
            )

        self.assertEqual(node.weight, 0.5)
        self.assertEqual(node.instantx_control_mode, 4)
        self.assertEqual(node.vae_path, "fake/vae.safetensors")
        mock_load_vae.assert_called_once()
        field = node.to_api_field()
        self.assertEqual(field.instantx_control_mode, 4)
        self.assertEqual(field.resize_mode, "just_resize")

    @patch("ssui_image.Flux.FluxClip", fake_clip)
    @patch("ssui_image.Flux.flux_denoise_image", return_value=FakeLatent())
    def test_denoise_passes_control_and_vae(self, mock_denoise):
        from ssui_image.Flux import (
            FluxClip,
            FluxControlNet,
            FluxDenoise,
            FluxLatent,
        )

        vae = MagicMock()
        control = FluxControlNet(
            path="fake/controlnet.safetensors",
            image_path="",
            controlnet=MagicMock(controlnet=_loaded_model()),
            image=PILImage.new("RGB", (64, 64)),
            vae=vae,
            weight=0.4,
        )
        positive, negative = FluxClip(
            self.config("Prompt To Condition"),
            FakeFluxModel(),
            self.positive,
            self.negative,
        )
        latent = FluxLatent(self.config("Create Empty Latent"))
        FluxDenoise(
            self.config("Denoise"),
            FakeFluxModel(),
            latent,
            positive,
            negative,
            control,
        )

        kwargs = mock_denoise.call_args.kwargs
        self.assertEqual(kwargs["control"].control_weight, 0.4)
        self.assertIs(kwargs["controlnet_vae"], vae)


class TestControlNetWorkflowScripts(unittest.TestCase):
    """示例 workflow 脚本能注册 txt2imgWithControlNet 并完成 prepare pass。"""

    def _prepare(self, script_name: str):
        from ss_executor.loader import SSLoader

        script = os.path.join(
            os.path.dirname(__file__),
            "..",
            "examples",
            "basic",
            script_name,
        )
        loader = SSLoader(use_sandbox=False)
        loader.load(os.path.abspath(script))
        loader.Execute()
        return loader

    def test_sd1_script(self):
        loader = self._prepare("workflow-sd1.py")
        names = [func.__name__ for func, _, _ in loader.callables]
        self.assertIn("txt2imgWithControlNet", names)
        config = loader.GetConfig("txt2imgWithControlNet")
        self.assertIn("Denoise", config)
        self.assertIn("Create Empty Latent", config)

    def test_sdxl_script(self):
        loader = self._prepare("workflow-sdxl.py")
        names = [func.__name__ for func, _, _ in loader.callables]
        self.assertIn("txt2imgWithControlNet", names)
        config = loader.GetConfig("txt2imgWithControlNet")
        self.assertIn("Denoise", config)

    def test_flux_script(self):
        loader = self._prepare("workflow-flux.py")
        names = [func.__name__ for func, _, _ in loader.callables]
        self.assertIn("txt2imgWithControlNet", names)
        config = loader.GetConfig("txt2imgWithControlNet")
        self.assertIn("Denoise", config)
