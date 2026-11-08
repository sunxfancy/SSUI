"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider
_delegate = initialize_adapter(globals(), "voice.Cosyvoice")
GenVoice = param("seed", Random(), default=42)(param("use_zero_shot", Switch(), default=True)(param("zero_shot_prompt", Switch(), default=True)(param("speaker_id", Slider(0, 100, 1), default=0)(_delegate("GenVoice")))))
