"""TRELLIS MPS workflow. Download weights with yarn test:trellis:smoke --download-only."""
from ssui import workflow, Image, Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.Trellis import TrellisModel, GenModel
config = SSUIConfig()

@workflow
def img2mesh_trellis(image: Image) -> Mesh:
    model = None
    if not config.is_prepare():
        model = TrellisModel.load('microsoft/TRELLIS-image-large')
    return GenModel(config('Generate TRELLIS Mesh'), model, image)
