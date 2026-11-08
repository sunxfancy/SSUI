"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Select, Slider
_delegate = initialize_adapter(globals(), "mesh.WorldClaw")
GenWorldClawScene = param("seed", Random(), default=42)(param("world_size", Slider(32, 512, 1), default=128)(param("terrain_resolution", Select(32, 64, 128, 256), default=64)(_delegate("GenWorldClawScene"))))
