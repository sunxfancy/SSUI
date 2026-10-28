from ssui import workflow, Image, Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.Trellis import TrellisModel, GenModel

config = SSUIConfig()


@workflow
def img2mesh_trellis(model: TrellisModel, image: Image) -> Mesh:
    return GenModel(config("Generate TRELLIS Model"), model, image)
