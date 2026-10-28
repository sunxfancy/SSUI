from typing import Tuple
from ssui import Mesh, workflow
from ssui.config import SSUIConfig
from ssui_3dmodel.Retopology import SegmentParts
from ssui_3dmodel.HoloPart import CompleteParts, QuadRemeshCompleted

config = SSUIConfig()


@workflow
def holopart(mesh: Mesh) -> Tuple[Mesh, Mesh, Mesh]:
    parts = SegmentParts(config('P3-SAM 部件分割'), mesh)
    completed = CompleteParts(config('HoloPart 部件补全'), parts)
    result = QuadRemeshCompleted(config('QuadriFlow 四边面重拓扑'), completed)
    return parts, completed, result
