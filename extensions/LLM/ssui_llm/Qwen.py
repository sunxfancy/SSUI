"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider
_delegate = initialize_adapter(globals(), "llm.Qwen")
Chat = param("temperature", Slider(0.0, 2.0, 0.1), default=0.7)(param("max_length", Slider(100, 2048, 100), default=2048)(param("top_p", Slider(0.0, 1.0, 0.1), default=0.9)(_delegate("Chat"))))
