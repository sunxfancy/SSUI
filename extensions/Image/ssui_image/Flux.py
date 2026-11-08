"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Select, Switch, Slider
_delegate = initialize_adapter(globals(), "image.Flux")
FluxClip = param("ignoreLastLayer", Switch(), default=False)(_delegate("FluxClip"))
class FluxLatent(FluxLatent):
    pass
FluxLatent = param(
    "width",
    Slider(1024, 4096, 64, labels=[1024, 1536, 1920, 2048, 3840, 4096]),
    default=1024,
)(param(
    "height",
    Slider(1024, 4096, 64, labels=[1024, 1536, 1920, 2048, 3840, 4096]),
    default=1024,
)(FluxLatent))
FluxDenoise = param(
    "steps",
    Slider(1, 100, 1, labels=[1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]),
    default=4,
)(param("CFG", Slider(0, 15, 0.1), default=1.0)(param("CFG_start_step", Slider(0, 100, 1), default=0)(param("CFG_end_step", Slider(-1, 100, 1), default=-1)(param("guidance", Slider(0, 15, 0.1), default=4.0)(param("add_noise", Switch(), default=True)(param("denoising_start", Slider(0, 1.0, 0.01), default=0.0)(param("denoising_end", Slider(0, 1.0, 0.01), default=1.0)(param("seed", Random(), default=123454321)(_delegate("FluxDenoise"))))))))))
