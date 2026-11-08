"""Workflow compatibility adapter; inference lives in backend."""
from ssui.backend_adapter import initialize_adapter
from ssui.annotation import param
from ssui.controller import Input, Slider
_delegate = initialize_adapter(globals(), "motion.nodes")
RecognizePose = param("sample_fps", Slider(1, 60, 1), default=24)(param("smoothing", Slider(0, 0.95, 0.05), default=0.45)(param("detection_confidence", Slider(0, 1, 0.05), default=0.5)(param("tracking_confidence", Slider(0, 1, 0.05), default=0.5)(param("max_gap_frames", Slider(0, 12, 1), default=3)(param("model_path", Input("可选：本地 pose_landmarker .task 路径"), default="")(_delegate("RecognizePose")))))))
RenderBlenderComparison = param("blender_executable", Input("可选：blender 可执行文件路径"), default="")(_delegate("RenderBlenderComparison"))
