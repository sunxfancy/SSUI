import unittest
from types import SimpleNamespace

from PIL import Image

from ssui import SkeletonAnimation, Video
from ssui_motion import PoseRecognitionOptions, recognize_pose


class FakeDetector:
    def __init__(self, results):
        self.results = iter(results)
        self.closed = False

    def detect(self, _frame, _timestamp_ms=0):
        return next(self.results)

    def close(self):
        self.closed = True


def points(offset=0.0):
    image = [SimpleNamespace(x=0.2 + offset + i * 0.001, y=0.3, z=-0.1, visibility=0.9, presence=0.8) for i in range(33)]
    world = [SimpleNamespace(x=0.01 * i, y=0.02 * i, z=0.03 * i) for i in range(33)]
    return image, world


class MotionPoseTest(unittest.TestCase):
    def test_video_accepts_uploaded_path_shape(self):
        video = Video(video="input/dance.mp4")
        self.assertEqual(video.path, "input/dance.mp4")
        self.assertEqual(video._format, "mp4")

    def test_recognize_pose_returns_overlay_and_serializable_animation(self):
        video = Video(frames=[Image.new("RGB", (160, 90)) for _ in range(3)], fps=30)
        detector = FakeDetector([points(0), points(0.1), None])

        overlay, animation = recognize_pose(
            video,
            PoseRecognitionOptions(smoothing=0.5, max_gap_frames=1),
            detector,
        )

        self.assertEqual(len(overlay.frames), 3)
        self.assertIsInstance(animation, SkeletonAnimation)
        self.assertEqual((animation.width, animation.height), (160, 90))
        self.assertEqual(len(animation.frames[0].landmarks), 33)
        self.assertAlmostEqual(animation.frames[1].landmarks[0].x, 0.25)
        self.assertFalse(animation.frames[2].detected)
        self.assertLess(animation.frames[2].landmarks[0].visibility, 0.9)
        self.assertEqual(animation.to_dict()["model"], "mediapipe-pose-33")

    def test_sampling_uses_requested_timeline_rate(self):
        video = Video(frames=[Image.new("RGB", (32, 32)) for _ in range(30)], fps=30)
        detector = FakeDetector([points() for _ in range(10)])
        _, animation = recognize_pose(video, PoseRecognitionOptions(sample_fps=10, smoothing=0), detector)
        self.assertEqual(len(animation.frames), 10)
        self.assertEqual([f.frame_index for f in animation.frames[:3]], [0, 3, 6])
        self.assertEqual(animation.fps, 10)

    def test_invalid_options_fail_early(self):
        with self.assertRaises(ValueError):
            PoseRecognitionOptions(smoothing=1.5)


if __name__ == "__main__":
    unittest.main()
