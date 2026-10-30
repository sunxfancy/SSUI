from typing import Tuple

from ssui import Mesh, workflow
from ssui.config import SSUIConfig
from ssui_3dmodel.Retopology import SegmentParts, QuadRemesh

config = SSUIConfig()


@workflow
def retopology(mesh: Mesh) -> Tuple[Mesh, Mesh]:
    parts = SegmentParts(config("自动部件分割 · P3-SAM"), mesh)
    result = QuadRemesh(config("四边面重拓扑 · QuadriFlow"), parts)
    return parts, result
