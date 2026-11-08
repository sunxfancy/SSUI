"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider
_delegate = initialize_adapter(globals(), "video.Hunyuan")
HunyuanTextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 500, 1), default=129)(param("num_inference_steps", Slider(1, 50, 1), default=18)(param("height", Slider(1, 1000, 1), default=512)(param("width", Slider(1, 1000, 1), default=384)(_delegate("HunyuanTextToVideo"))))))
HunyuanImageToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(1, 500, 1), default=129)(param("num_inference_steps", Slider(1, 50, 1), default=24)(param("height", Slider(1, 1000, 1), default=720)(param("width", Slider(1, 1000, 1), default=1280)(_delegate("HunyuanImageToVideo"))))))
