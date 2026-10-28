"""Image-to-3D entry point; check native dependencies with yarn probe:3d first."""

from ssui import Image, Mesh, workflow
from ssui.config import SSUIConfig
from ssui_3dmodel.Pixal3D import GenPixal3DModel, Pixal3DModel

config = SSUIConfig()


@workflow
def img2mesh_pixal3d(image: Image) -> Mesh:
    model = Pixal3DModel.load(low_vram=True)
    return GenPixal3DModel(config("Generate Pixal3D Model"), model, image)
