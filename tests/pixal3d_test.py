import sys
import types
import unittest
import os
from pathlib import Path
import runpy
from unittest.mock import patch

from tests.utils import add_extension_paths

add_extension_paths()

from PIL import Image as PILImage

from ssui.base import Image
from ssui.config import SSUIConfig


def _remove_trellis_test_stubs():
    """Temporarily remove the process-global fake SDK package from Trellis tests."""
    package = sys.modules.get("ssui_3dmodel")
    saved = {}
    if package is not None and getattr(package, "__file__", None) is None:
        for name in list(sys.modules):
            if name == "ssui_3dmodel" or name.startswith("ssui_3dmodel."):
                saved[name] = sys.modules.pop(name)
    return saved


class _GeneratedMesh:
    vertices = object()
    faces = object()
    attrs = object()
    coords = object()


class _Glb:
    def __init__(self):
        self.transform = None

    def apply_transform(self, transform):
        self.transform = transform

    def export(self, *args, **kwargs):
        return b"glb"


class _Pipeline:
    pbr_attr_layout = {"base_color": slice(0, 3)}

    def __init__(self):
        self.run_kwargs = None

    def preprocess_image(self, image):
        return image

    def run(self, image, **kwargs):
        self.run_kwargs = kwargs
        return [_GeneratedMesh()], (object(), object(), 128)


class Pixal3DWorkflowTest(unittest.TestCase):
    def setUp(self):
        self._saved_ssui_3dmodel_modules = _remove_trellis_test_stubs()

    def tearDown(self):
        if not self._saved_ssui_3dmodel_modules:
            return
        for name in list(sys.modules):
            if name == "ssui_3dmodel" or name.startswith("ssui_3dmodel."):
                sys.modules.pop(name, None)
        sys.modules.update(self._saved_ssui_3dmodel_modules)

    def test_manual_camera_workflow_exports_pbr_glb(self):
        glb = _Glb()
        postprocess = types.SimpleNamespace(to_glb=lambda **kwargs: glb)
        old_o_voxel = sys.modules.get("o_voxel")
        sys.modules["o_voxel"] = types.SimpleNamespace(postprocess=postprocess)
        try:
            from ssui_3dmodel.Pixal3D import GenPixal3DModel, Pixal3DModel

            pipeline = _Pipeline()
            model = Pixal3DModel("fake/pixal3d", pipeline, low_vram=True)
            config = SSUIConfig()
            config.set_prepared(False)
            node_config = config("Generate Pixal3D Model")
            node_config["auto_camera"] = False
            node_config["fov_degrees"] = 30
            node_config["resolution"] = 1024
            node_config["seed"] = 7
            node_config["sparse_structure_steps"] = 8
            node_config["shape_steps"] = 9
            node_config["texture_steps"] = 10

            result = GenPixal3DModel(
                node_config, model, Image(PILImage.new("RGB", (64, 64), "white"))
            )

            self.assertIs(result._model, glb)
            self.assertIsNotNone(glb.transform)
            self.assertEqual(pipeline.run_kwargs["pipeline_type"], "1024_cascade")
            self.assertEqual(pipeline.run_kwargs["seed"], 7)
            self.assertEqual(
                pipeline.run_kwargs["tex_slat_sampler_params"]["steps"], 10
            )
        finally:
            if old_o_voxel is None:
                sys.modules.pop("o_voxel", None)
            else:
                sys.modules["o_voxel"] = old_o_voxel

    def test_prepare_does_not_run_pipeline(self):
        from ssui_3dmodel.Pixal3D import GenPixal3DModel, Pixal3DModel

        pipeline = _Pipeline()
        config = SSUIConfig()
        config.set_prepared(True)
        result = GenPixal3DModel(
            config("Generate Pixal3D Model"),
            Pixal3DModel("fake/pixal3d", pipeline),
            Image(PILImage.new("RGB", (8, 8))),
        )
        self.assertIsNone(result._model)
        self.assertIsNone(pipeline.run_kwargs)

    def test_load_stops_before_weights_when_native_export_is_broken(self):
        from ssui_3dmodel.Pixal3D import Pixal3DModel

        pipeline = types.SimpleNamespace(
            Pixal3DImageTo3DPipeline=unittest.mock.Mock(),
        )
        with patch("torch.cuda.is_available", return_value=True), patch(
            "ssui_3dmodel.runtime.require_glb_runtime",
            side_effect=RuntimeError("native export unavailable"),
        ), patch.dict(sys.modules, {"pixal3d.pipelines": pipeline}):
            with self.assertRaisesRegex(RuntimeError, "native export unavailable"):
                Pixal3DModel.load("must-not-download")
            pipeline.Pixal3DImageTo3DPipeline.from_pretrained.assert_not_called()

    def test_legacy_trellis_rejects_rocm_before_cuda_import(self):
        from ssui_3dmodel.Trellis import TrellisModel

        with patch("torch.version.hip", "7.2"):
            with self.assertRaisesRegex(RuntimeError, "Pixal3D"):
                TrellisModel.load("must-not-download")

    def test_rgba_preprocessing_does_not_load_background_model(self):
        module = Path(__file__).resolve().parents[1] / "extensions/3D-Model/vendor/pixal3d/modules/image_feature_extractor.py"
        with patch.dict(sys.modules, {"transformers": types.SimpleNamespace()}):
            runpy.run_path(str(module))
        from pixal3d.pipelines import Pixal3DImageTo3DPipeline
        from PIL import ImageDraw
        pipeline = Pixal3DImageTo3DPipeline.__new__(Pixal3DImageTo3DPipeline)
        pipeline.rembg_model = None
        pipeline.low_vram = True
        image = PILImage.new("RGBA", (64, 64))
        ImageDraw.Draw(image).rectangle((16, 16, 48, 48), fill=(220, 80, 40, 255))
        # No rembg config or GPU is needed for a supplied foreground mask.
        result = pipeline.preprocess_image(image)
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.getpixel((result.width // 2, result.height // 2)), (220, 80, 40))
        self.assertIsNone(pipeline.rembg_model)

    def test_windows_rocm_streamed_checkpoint_preserves_weights(self):
        from importlib.metadata import version
        from packaging.version import Version
        if Version(version("safetensors")) < Version("0.8.0"):
            self.skipTest("Windows ROCm pread loading requires safetensors >= 0.8.0")
        import json
        import tempfile
        import torch
        from safetensors.torch import save_file
        from pixal3d import models
        expected = torch.nn.Linear(3, 2)
        with tempfile.TemporaryDirectory() as directory:
            stem = Path(directory) / "linear"
            stem.with_suffix(".json").write_text(json.dumps({
                "name": "TestLinear", "args": {"in_features": 3, "out_features": 2},
            }))
            save_file(expected.state_dict(), str(stem.with_suffix(".safetensors")))
            with patch.object(models, "__getattr__", return_value=torch.nn.Linear), patch(
                "sys.platform", "win32"
            ), patch("torch.version.hip", "7.2"):
                actual = models.from_pretrained(str(stem))
            for name, value in expected.state_dict().items():
                torch.testing.assert_close(actual.state_dict()[name], value)
            # Assignment must preserve the constructor's inference dtype,
            # rather than silently adopting the checkpoint's FP32 dtype.
            with patch.object(models, "__getattr__", return_value=lambda **kw: torch.nn.Linear(**kw).half()), patch(
                "sys.platform", "win32"
            ), patch("torch.version.hip", "7.2"):
                half = models.from_pretrained(str(stem))
            torch.testing.assert_close(half.weight, expected.weight.half())
            save_file({'weight': expected.weight}, str(stem.with_suffix(".safetensors")))
            with patch.object(models, "__getattr__", return_value=torch.nn.Linear), patch(
                "sys.platform", "win32"
            ), patch("torch.version.hip", "7.2"):
                with self.assertRaisesRegex(ValueError, 'missing model tensors'):
                    models.from_pretrained(str(stem))

    def test_stage_weights_release_and_reload_without_cpu_copy(self):
        import torch
        from pixal3d.pipelines.base import StageModels
        expected = torch.nn.Linear(3, 2).state_dict()
        def load(source):
            model = torch.nn.Linear(3, 2)
            model.load_state_dict(expected)
            return model
        loader = unittest.mock.Mock(side_effect=load)
        store = StageModels({'shape': 'checkpoint'}, loader)
        self.assertIn('shape', store)
        self.assertEqual(list(store), ['shape'])
        loader.assert_not_called()
        first = store['shape']
        self.assertIs(first, store['shape'])
        self.assertFalse(first.training)
        with patch.object(first, 'cpu', side_effect=AssertionError('CPU copy')):
            store.release(first)
        self.assertEqual(first.weight.device.type, 'meta')
        self.assertFalse(store.loaded)
        second = store['shape']
        self.assertIsNot(first, second)
        self.assertEqual(loader.call_count, 2)
        torch.testing.assert_close(second.weight, expected['weight'])

    def test_conditioners_share_frozen_backbone_without_reloading(self):
        import torch
        from pixal3d.trainers.flow_matching.mixins.image_conditioned_proj import DinoV3ProjFeatureExtractor
        backbone = torch.nn.Linear(8, 8)
        backbone.config = types.SimpleNamespace(patch_size=16, hidden_size=8)
        with patch.dict(sys.modules, {"transformers": types.SimpleNamespace() }):
            first = DinoV3ProjFeatureExtractor("unused", grid_resolution=2, backbone=backbone)
            second = DinoV3ProjFeatureExtractor("unused", grid_resolution=4, backbone=backbone)
        self.assertIs(first.model, second.model)
        self.assertIsNot(first.proj_grid, second.proj_grid)
        self.assertFalse(any(p.requires_grad for p in backbone.parameters()))

    def test_rocm_defaults_and_explicit_backend_overrides(self):
        modules = Path(__file__).resolve().parents[1] / "extensions/3D-Model/vendor/pixal3d/modules"
        with patch("torch.version.hip", "7.2"), patch("sys.platform", "win32"), patch.dict(
            os.environ, {}, clear=True,
        ):
            self.assertEqual(runpy.run_path(str(modules / "attention/config.py"))["BACKEND"], "sdpa")
            self.assertEqual(runpy.run_path(str(modules / "sparse/config.py"))["ATTN"], "sdpa")
            self.assertEqual(runpy.run_path(str(modules / "sparse/conv/config.py"))["FLEX_GEMM_ALGO"], "explicit_gemm")
            with patch.dict(os.environ, {"ATTN_BACKEND": "flash_attn", "FLEX_GEMM_ALGO": "implicit_gemm"}):
                self.assertEqual(runpy.run_path(str(modules / "attention/config.py"))["BACKEND"], "flash_attn")
                self.assertEqual(runpy.run_path(str(modules / "sparse/config.py"))["ATTN"], "flash_attn")
                self.assertEqual(runpy.run_path(str(modules / "sparse/conv/config.py"))["FLEX_GEMM_ALGO"], "implicit_gemm")
        with patch("torch.version.hip", None), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runpy.run_path(str(modules / "attention/config.py"))["BACKEND"], "flash_attn")
            self.assertEqual(runpy.run_path(str(modules / "sparse/conv/config.py"))["FLEX_GEMM_ALGO"], "masked_implicit_gemm_splitk")


if __name__ == "__main__":
    unittest.main()
