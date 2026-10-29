"""Install a runtime first: yarn install:rigging unirig (or mia / riganything)."""
from ssui import Mesh, workflow
from ssui.config import SSUIConfig
from ssui_3dmodel.AutoRig import AutoRigMesh

config = SSUIConfig()


@workflow
def auto_rig(mesh: Mesh) -> Mesh:
    return AutoRigMesh(config("Auto Rig"), mesh)
