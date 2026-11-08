"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider
_delegate = initialize_adapter(globals(), "video.AnimateDiff")
AnimateDiffTextToVideo = param("width", Slider(1, 1000, 1), default=768)(param("height", Slider(1, 1000, 1), default=512)(param("num_frames", Slider(1, 1000, 1), default=64)(param("cfg_scale", Slider(1, 20, 1), default=7.5)(param("num_inference_steps", Slider(1, 100, 1), default=30)(param("seed", Random(), default=42)(param("denoising_strength", Slider(0, 1, 0.01), default=0.9)(_delegate("AnimateDiffTextToVideo"))))))))
