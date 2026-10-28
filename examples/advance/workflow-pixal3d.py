"""GPU image-to-3D workflow; select a Pixal3D model and upload an object image."""
from ssui import workflow, Image, Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.Pixal3D import Pixal3DModel, GenPixal3DModel

config = SSUIConfig()


@workflow
def img2mesh_pixal3d(model: Pixal3DModel, image: Image) -> Mesh:
    return GenPixal3DModel(config("Generate Pixal3D Model"), model, image)
