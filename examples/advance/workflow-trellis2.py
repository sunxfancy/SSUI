from ssui import workflow, Image, Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.Trellis2 import Trellis2Model, GenTrellis2Model

config = SSUIConfig()


@workflow
def img2mesh_trellis2(model: Trellis2Model, image: Image) -> Mesh:
    return GenTrellis2Model(config("Generate TRELLIS.2 Model"), model, image)
