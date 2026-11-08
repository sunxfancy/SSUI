"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider
_delegate = initialize_adapter(globals(), "image.Flux2")
Flux2KleinGenerate = param("width", Slider(256, 2048, 64, labels=[512, 768, 1024, 1536, 2048]), default=1024)(param("height", Slider(256, 2048, 64, labels=[512, 768, 1024, 1536, 2048]), default=1024)(param("steps", Slider(1, 50, 1, labels=[1, 4, 8, 20, 28, 50]), default=4)(param("guidance", Slider(1, 10, 0.1), default=1.0)(param("seed", Random(), default=123454321)(_delegate("Flux2KleinGenerate"))))))
