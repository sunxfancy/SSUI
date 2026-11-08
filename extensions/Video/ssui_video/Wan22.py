"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider, Switch
_delegate = initialize_adapter(globals(), "video.Wan22")
Wan22TextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 300, 1), default=81)(param("num_inference_steps", Slider(1, 100, 1), default=50)(param("height", Slider(16, 1280, 16), default=480)(param("width", Slider(16, 1280, 16), default=832)(param("tiled", Switch(), default=True)(_delegate("Wan22TextToVideo")))))))
Wan22ImageToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 300, 1), default=81)(param("num_inference_steps", Slider(1, 100, 1), default=50)(param("height", Slider(16, 1280, 16), default=480)(param("width", Slider(16, 1280, 16), default=832)(param("tiled", Switch(), default=True)(_delegate("Wan22ImageToVideo")))))))
Wan22T2VA14BTextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 300, 1), default=81)(param("num_inference_steps", Slider(1, 100, 1), default=50)(param("height", Slider(16, 1280, 16), default=480)(param("width", Slider(16, 1280, 16), default=832)(param("switch_diT_boundary", Slider(0, 1, 0.05), default=0.875)(param("tiled", Switch(), default=True)(_delegate("Wan22T2VA14BTextToVideo"))))))))
Wan22I2VA14BImageToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 300, 1), default=81)(param("num_inference_steps", Slider(1, 100, 1), default=50)(param("height", Slider(16, 1280, 16), default=480)(param("width", Slider(16, 1280, 16), default=832)(param("switch_diT_boundary", Slider(0, 1, 0.05), default=0.9)(param("tiled", Switch(), default=True)(_delegate("Wan22I2VA14BImageToVideo"))))))))
