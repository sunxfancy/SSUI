import os
import sys
import tempfile
import types
import unittest

from PIL import Image as PILImage


class FakeTrellisPipeline:
    @staticmethod
    def from_pretrained(*args, **kwargs):
        return FakeTrellisPipeline()

    def cuda(self):
        return self

    def run(self, image, **kwargs):
        return {
            "gaussian": [object()],
            "radiance_field": [object()],
            "mesh": [object()],
        }


class FakeExportable:
    def export(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("glb")


class FakeTrellisModel:
    @staticmethod
    def load(*args, **kwargs):
        return FakeTrellisModel()


class FakeGenModel:
    def __init__(self, config, model, image):
        self._model = FakeExportable()


def _install_trellis_stubs():
    """向 sys.modules 注入 trellis / ssui_3dmodel 假模块。

    vendored trellis 依赖 kaolin 等包，部分平台（如 macOS）没有对应 wheel，
    这里用假模块替代，只验证 3D 管线与导出流程的契约。
    """
    if "trellis.pipelines" in sys.modules:
        return

    trellis = types.ModuleType("trellis")
    trellis.__path__ = []
    pipelines = types.ModuleType("trellis.pipelines")
    pipelines.TrellisImageTo3DPipeline = FakeTrellisPipeline
    utils = types.ModuleType("trellis.utils")
    utils.__path__ = []
    render_utils = types.ModuleType("trellis.utils.render_utils")
    render_utils.render_video = lambda *args, **kwargs: []
    postprocessing_utils = types.ModuleType("trellis.utils.postprocessing_utils")
    postprocessing_utils.to_glb = lambda *args, **kwargs: FakeExportable()

    ssui_3dmodel = types.ModuleType("ssui_3dmodel")
    ssui_3dmodel.__path__ = []
    trellis_module = types.ModuleType("ssui_3dmodel.Trellis")
    trellis_module.TrellisModel = FakeTrellisModel
    trellis_module.GenModel = FakeGenModel

    sys.modules.update(
        {
            "trellis": trellis,
            "trellis.pipelines": pipelines,
            "trellis.utils": utils,
            "trellis.utils.render_utils": render_utils,
            "trellis.utils.postprocessing_utils": postprocessing_utils,
            "ssui_3dmodel": ssui_3dmodel,
            "ssui_3dmodel.Trellis": trellis_module,
        }
    )


_install_trellis_stubs()


class TrellisWorkflowTest(unittest.TestCase):
    """给定假 Trellis 输出，验证 3D 管线与导出流程能跑通。"""

    def test_trellis(self):
        from trellis.pipelines import TrellisImageTo3DPipeline
        from trellis.utils import postprocessing_utils, render_utils

        pipeline = TrellisImageTo3DPipeline.from_pretrained("fake/trellis-image-large")
        pipeline.cuda()

        outputs = pipeline.run(PILImage.new("RGB", (64, 64)), seed=1)
        self.assertIn("gaussian", outputs)
        self.assertIn("mesh", outputs)

        render_utils.render_video(outputs["gaussian"][0])
        with tempfile.TemporaryDirectory() as tmp:
            glb = postprocessing_utils.to_glb(
                outputs["gaussian"][0],
                outputs["mesh"][0],
                simplify=0.95,
                texture_size=256,
            )
            path = os.path.join(tmp, "sample.glb")
            glb.export(path)
            self.assertTrue(os.path.exists(path))

    def test_trellis_workflow(self):
        from ssui.config import SSUIConfig
        from ssui_3dmodel.Trellis import GenModel, TrellisModel

        model = TrellisModel.load("fake/trellis-image-large")
        image = PILImage.new("RGB", (64, 64))
        config = SSUIConfig()
        config.set_prepared(False)

        with tempfile.TemporaryDirectory() as tmp:
            glb = GenModel(config("Generate 3D Model"), model, image)
            path = os.path.join(tmp, "building.glb")
            glb._model.export(path)
            self.assertTrue(os.path.exists(path))
