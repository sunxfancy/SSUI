"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider, Switch
_delegate = initialize_adapter(globals(), "video.Wan2")
Wan2TextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 200, 1), default=81)(param("num_inference_steps", Slider(1, 100, 1), default=50)(param("height", Slider(16, 1280, 16), default=480)(param("width", Slider(16, 1280, 16), default=832)(param("tiled", Switch(), default=True)(_delegate("Wan2TextToVideo")))))))
Wan2ImageToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 200, 1), default=81)(param("num_inference_steps", Slider(1, 100, 1), default=50)(param("height", Slider(16, 1280, 16), default=480)(param("width", Slider(16, 1280, 16), default=832)(param("tiled", Switch(), default=True)(_delegate("Wan2ImageToVideo")))))))
