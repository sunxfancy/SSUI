"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Random, Slider, Switch
_delegate = initialize_adapter(globals(), "mesh.Pixal3D")
GenPixal3DModel = param("seed", Random(), default=42)(param("auto_camera", Switch(), default=True)(param("fov_degrees", Slider(5, 120, 1), default=30)(param("resolution", Slider(1024, 1536, 512), default=1024)(param("sparse_structure_steps", Slider(1, 50, 1), default=12)(param("shape_steps", Slider(1, 50, 1), default=12)(param("texture_steps", Slider(1, 50, 1), default=12)(_delegate("GenPixal3DModel"))))))))
