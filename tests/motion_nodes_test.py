import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ssui import SkeletonAnimation, Video
from ssui.config import SSUIConfig
from ssui_motion import RecognizePose, RenderBlenderComparison, render_blender_comparison
from tests.motion_bvh_test import animation


class MotionNodesTest(unittest.TestCase):
    def test_prepare_registers_pose_controls_without_running_detector(self):
        config = SSUIConfig()
        config.set_prepared()

        overlay, skeleton = RecognizePose(config("Pose Recognition"), None)

        self.assertIsInstance(overlay, Video)
        self.assertIsInstance(skeleton, SkeletonAnimation)
        self.assertEqual(
            set(config._config["Pose Recognition"]),
            {
                "sample_fps", "smoothing", "detection_confidence",
                "tracking_confidence", "max_gap_frames", "model_path",
            },
        )

    def test_prepare_registers_blender_control_without_launching_blender(self):
        config = SSUIConfig()
        config.set_prepared()

        result = RenderBlenderComparison(config("Blender Comparison"), None)

        self.assertIsInstance(result, Video)
        self.assertIn("blender_executable", config._config["Blender Comparison"])

    def test_blender_result_uses_video_port_and_preserves_artifact_metadata(self):
        def fake_blender(arguments, _explicit):
            root = Path(arguments[arguments.index("--output-dir") + 1])
            (root / "frames").mkdir(parents=True, exist_ok=True)
            (root / "pose-comparison.blend").write_bytes(b"BLENDER")
            (root / "blender-comparison.json").write_text(
                json.dumps({
                    "blender_version": "test", "rmse": 0.001,
                    "max_error": 0.002,
                }),
                encoding="utf-8",
            )
            Image.new("RGB", (32, 32), "black").save(
                root / "frames" / "pose-comparison-0001.png"
            )

        with tempfile.TemporaryDirectory() as directory, patch(
            "ssui_motion.blender._run_blender", side_effect=fake_blender
        ):
            result = render_blender_comparison(animation(), directory)

        self.assertIsInstance(result, Video)
        self.assertEqual(len(result.frames), 1)
        self.assertEqual(result.metadata["kind"], "blender_comparison")
        self.assertEqual(result.metadata["comparison_rmse"], 0.001)
        self.assertTrue(result.metadata["scene_path"].endswith("pose-comparison.blend"))


if __name__ == "__main__":
    unittest.main()
