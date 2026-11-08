"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider
_delegate = initialize_adapter(globals(), "mesh.Trellis")
GenModel = param("seed", Random(), default=42)(param("preprocess_image", Switch(), default=True)(param("sparse_structure_steps", Slider(1, 50, 1), default=12)(param("sparse_structure_cfg", Slider(0, 15, 0.1), default=7.5)(param("slat_steps", Slider(1, 50, 1), default=12)(param("slat_cfg", Slider(0, 15, 0.1), default=3.0)(_delegate("GenModel")))))))
