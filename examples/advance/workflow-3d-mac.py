"""Single-image to colored mesh. Download once: yarn test:3d:smoke --download-only."""
from ssui import workflow, Image, Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.TripoSR import TripoSRModel, TripoSRImageToMesh

config = SSUIConfig()


@workflow
def img2mesh_mac(image: Image) -> Mesh:
    model = None
    if not config.is_prepare():
        model = TripoSRModel.load_local()
    return TripoSRImageToMesh(config('Generate Mesh'), model, image)
