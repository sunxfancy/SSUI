from ssui import SkeletonAnimation, Video, workflow
from ssui.config import SSUIConfig
from ssui_motion import RecognizePose, RenderBlenderComparison

config = SSUIConfig()


@workflow
def video_to_skeleton(video: Video) -> tuple[Video, SkeletonAnimation]:
    """Extract a smoothed 33-joint animation and a visual verification video."""
    return RecognizePose(config("Pose Recognition"), video)


@workflow
def video_to_blender_comparison(video: Video) -> tuple[Video, SkeletonAnimation, Video]:
    """Recognize a video and render the reconstructed BVH side by side in Blender."""
    overlay, animation = RecognizePose(config("Pose Recognition"), video)
    comparison = RenderBlenderComparison(config("Blender Comparison"), animation)
    return overlay, animation, comparison
