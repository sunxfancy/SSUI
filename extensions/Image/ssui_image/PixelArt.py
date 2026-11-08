"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Select, Slider, Switch
_delegate = initialize_adapter(globals(), "image.PixelArt")
RenderAgentPaint = param("scale", Slider(1, 16, 1), default=1)(param("frame", Slider(0, 255, 1), default=0)(_delegate("RenderAgentPaint")))
RenderPixelSrc = param("scale", Slider(1, 16, 1), default=1)(param("spritesheet", Switch(), default=False)(_delegate("RenderPixelSrc")))
FinalizePixelArt = param("width", Slider(8, 512, 1), default=64)(param("height", Slider(8, 512, 1), default=64)(param("colors", Slider(2, 256, 1), default=24)(param("alpha_threshold", Slider(0, 255, 1), default=128)(param("downsample", Select("box", "nearest"), default="box")(param("preview_scale", Slider(1, 16, 1), default=1)(_delegate("FinalizePixelArt")))))))
