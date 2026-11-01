from ssui import Image, workflow
from ssui.config import SSUIConfig
from ssui_image.PixelArt import (
    AgentPaintAsset,
    PixelSrcAsset,
    RenderAgentPaint,
    RenderPixelSrc,
)


config = SSUIConfig()


@workflow
def render_agentpaint(asset: AgentPaintAsset) -> Image:
    return RenderAgentPaint(config("Render AgentPaint Source"), asset)


@workflow
def render_pixelsrc(asset: PixelSrcAsset) -> Image:
    return RenderPixelSrc(config("Render pixelsrc Source"), asset)
