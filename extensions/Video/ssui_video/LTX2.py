"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider, Switch, Select
_delegate = initialize_adapter(globals(), "video.LTX2")
LTX2TextToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(9, 497, 8), default=121)(param("height", Slider(64, 1024, 64), default=512)(param("width", Slider(64, 1024, 64), default=768)(param("quantization", Select("none", "fp8-cast"), default="fp8-cast")(param("offload", Select("none", "cpu", "disk"), default="cpu")(param("enhance_prompt", Switch(), default=False)(_delegate("LTX2TextToVideo"))))))))
LTX2ImageToVideo = param("seed", Random(), default=42)(param("num_frames", Slider(9, 497, 8), default=121)(param("num_inference_steps", Slider(1, 60, 1), default=40)(param("height", Slider(32, 1024, 32), default=512)(param("width", Slider(32, 1024, 32), default=768)(param("image_strength", Slider(0, 1, 0.05), default=0.8)(param("quantization", Select("none", "fp8-cast"), default="fp8-cast")(param("offload", Select("none", "cpu", "disk"), default="cpu")(param("enhance_prompt", Switch(), default=False)(_delegate("LTX2ImageToVideo"))))))))))
