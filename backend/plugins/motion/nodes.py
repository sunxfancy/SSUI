from __future__ import annotations

from backend.contracts.media import SkeletonAnimation, Video
from backend.contracts.services import InferenceConfig as SSUIConfig
from backend.contracts.motion import BlenderRenderer, PoseRecognitionOptions, PoseRecognizer


def RecognizePose(config: SSUIConfig, video: Video, *,
                  recognizer: PoseRecognizer) -> tuple[Video, SkeletonAnimation]:
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
    return recognizer(video, options)


def RenderBlenderComparison(config: SSUIConfig, animation: SkeletonAnimation, *,
                            renderer: BlenderRenderer) -> Video:
    """Configurable SSUI node that renders and measures a BVH in Blender."""

    if config.is_prepare():
        return Video()
    executable = config["blender_executable"] or None
    return renderer(animation, blender_executable=executable)
