"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider
_delegate = initialize_adapter(globals(), "video.CogVideo")
CogVideoTextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 200, 1), default=49)(param("num_inference_steps", Slider(1, 50, 1), default=20)(param("height", Slider(16, 1024, 16), default=480)(param("width", Slider(16, 1024, 16), default=720)(_delegate("CogVideoTextToVideo"))))))
