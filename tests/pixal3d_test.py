import sys
import types
import unittest

from PIL import Image as PILImage

from ssui.base import Image
from ssui.config import SSUIConfig


def _remove_trellis_test_stubs():
    """The legacy Trellis test installs a process-global fake SDK package."""
    package = sys.modules.get("ssui_3dmodel")
    if package is not None and getattr(package, "__file__", None) is None:
        for name in list(sys.modules):
            if name == "ssui_3dmodel" or name.startswith("ssui_3dmodel."):
                sys.modules.pop(name, None)


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
    def test_manual_camera_workflow_exports_pbr_glb(self):
        _remove_trellis_test_stubs()
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
        _remove_trellis_test_stubs()
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


if __name__ == "__main__":
    unittest.main()
