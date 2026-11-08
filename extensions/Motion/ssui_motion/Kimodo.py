"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Select, Slider, Switch
_delegate = initialize_adapter(globals(), "motion.Kimodo")
KimodoTextToMotion = param("model", Select(*KIMODO_MODELS), default="Kimodo-SOMA-RP-v1.1")(param("duration", Slider(1, 20, 0.5), default=5.0)(param("diffusion_steps", Slider(1, 200, 1), default=100)(param("seed", Random(), default=42)(param("text_encoder_device", Select("cuda", "cpu"), default="cuda")(param("export_bvh", Switch(), default=False)(_delegate("KimodoTextToMotion")))))))
