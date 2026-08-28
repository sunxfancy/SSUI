import tempfile
import unittest
from pathlib import Path

from ssui import PoseFrame, PoseLandmark, SkeletonAnimation
from ssui_motion import export_bvh, to_bvh


POSITIONS = {
    "nose": (0, 1.75, 0), "left_shoulder": (-0.2, 1.45, 0), "right_shoulder": (0.2, 1.45, 0),
    "left_elbow": (-0.5, 1.35, 0), "right_elbow": (0.5, 1.35, 0),
    "left_wrist": (-0.75, 1.25, 0), "right_wrist": (0.75, 1.25, 0),
    "left_index": (-0.82, 1.22, 0), "right_index": (0.82, 1.22, 0),
    "left_hip": (-0.14, 0.95, 0), "right_hip": (0.14, 0.95, 0),
    "left_knee": (-0.14, 0.52, 0), "right_knee": (0.14, 0.52, 0),
    "left_ankle": (-0.14, 0.08, 0), "right_ankle": (0.14, 0.08, 0),
    "left_foot_index": (-0.14, 0.02, -0.18), "right_foot_index": (0.14, 0.02, -0.18),
}


def animation():
    frames = []
    for frame_index, shift in enumerate((0.0, 0.03, 0.06)):
        positions = dict(POSITIONS)
        if frame_index == 1:
            positions.update({
                "left_elbow": (-0.424, 1.674, 0), "left_wrist": (-0.524, 1.924, 0), "left_index": (-0.594, 1.954, 0),
                "right_knee": (0.14, 0.60, -0.25), "right_ankle": (0.14, 0.24, -0.50), "right_foot_index": (0.14, 0.18, -0.68),
            })
        elif frame_index == 2:
            positions.update({
                "right_elbow": (0.424, 1.674, 0), "right_wrist": (0.524, 1.924, 0), "right_index": (0.594, 1.954, 0),
                "left_knee": (-0.14, 0.60, -0.25), "left_ankle": (-0.14, 0.24, -0.50), "left_foot_index": (-0.14, 0.18, -0.68),
            })
        landmarks = [
            PoseLandmark(name, 0.5 + x / 2 + shift, 1 - y / 2, z, 1, 1, x, y, z)
            for name, (x, y, z) in positions.items()
        ]
        frames.append(PoseFrame(frame_index, frame_index / 30, landmarks))
    return SkeletonAnimation(frames=frames, fps=30, width=1920, height=1080)


class MotionBVHTest(unittest.TestCase):
    def test_bvh_has_hierarchy_motion_and_finite_report(self):
        result = to_bvh(animation())
        self.assertIn("ROOT Hips", result.content)
        self.assertIn("JOINT LeftForeArm", result.content)
        self.assertIn("Frames: 3", result.content)
        motion_rows = result.content.split("Frame Time:", 1)[1].strip().splitlines()[1:]
        self.assertEqual(len(motion_rows), 3)
        self.assertTrue(all(len(row.split()) == 66 for row in motion_rows))
        self.assertGreaterEqual(result.report["rmse"], 0)
        self.assertEqual(len(result.report["target"]), 3)

    def test_export_writes_bvh_and_comparison_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "walk.bvh"
            result = export_bvh(animation(), path)
            self.assertEqual(path.read_text(encoding="utf-8"), result.content)
            self.assertTrue(path.with_suffix(".retarget.json").is_file())


if __name__ == "__main__":
    unittest.main()
