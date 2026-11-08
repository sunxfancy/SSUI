"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider, Select
_delegate = initialize_adapter(globals(), "video.MiniMaxH3")
H3TextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(5, 365, 1), default=124)(param("num_inference_steps", Slider(1, 60, 1), default=50)(param("height", Slider(32, 1536, 32), default=768)(param("width", Slider(32, 1536, 32), default=1344)(param("quantization", Select("none", "int8", "nf4"), default="none")(_delegate("H3TextToVideo")))))))
H3ImageToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(5, 365, 1), default=124)(param("num_inference_steps", Slider(1, 60, 1), default=50)(param("height", Slider(32, 1536, 32), default=768)(param("width", Slider(32, 1536, 32), default=1344)(param("quantization", Select("none", "int8", "nf4"), default="none")(_delegate("H3ImageToVideo")))))))
