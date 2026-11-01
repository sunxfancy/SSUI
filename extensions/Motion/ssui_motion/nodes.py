from __future__ import annotations

from ssui import SkeletonAnimation, Video
from ssui.annotation import param
from ssui.config import SSUIConfig
from ssui.controller import Input, Slider

from .blender import render_blender_comparison
from .pose import PoseRecognitionOptions, recognize_pose


@param("sample_fps", Slider(1, 60, 1), default=24)
@param("smoothing", Slider(0, 0.95, 0.05), default=0.45)
@param("detection_confidence", Slider(0, 1, 0.05), default=0.5)
@param("tracking_confidence", Slider(0, 1, 0.05), default=0.5)
@param("max_gap_frames", Slider(0, 12, 1), default=3)
@param("model_path", Input("可选：本地 pose_landmarker .task 路径"), default="")
def RecognizePose(config: SSUIConfig, video: Video) -> tuple[Video, SkeletonAnimation]:
    """Configurable SSUI node for single-person pose recognition."""

    if config.is_prepare():
        return Video(), SkeletonAnimation()
    model_path = config["model_path"] or None
    options = PoseRecognitionOptions(
        model_path=model_path,
        sample_fps=float(config["sample_fps"]),
        min_detection_confidence=float(config["detection_confidence"]),
        min_tracking_confidence=float(config["tracking_confidence"]),
        smoothing=float(config["smoothing"]),
        max_gap_frames=int(config["max_gap_frames"]),
    )
    return recognize_pose(video, options)


@param("blender_executable", Input("可选：blender 可执行文件路径"), default="")
def RenderBlenderComparison(config: SSUIConfig, animation: SkeletonAnimation) -> Video:
    """Configurable SSUI node that renders and measures a BVH in Blender."""

    if config.is_prepare():
        return Video()
    executable = config["blender_executable"] or None
    return render_blender_comparison(animation, blender_executable=executable)
