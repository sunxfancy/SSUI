"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider, Switch
_delegate = initialize_adapter(globals(), "video.Wan")
WanImageTextToVideo = param("seed", Random(), default=42)(param("tiled", Switch(), default=True)(param("num_frames", Slider(1, 200, 1), default=50)(_delegate("WanImageTextToVideo"))))
