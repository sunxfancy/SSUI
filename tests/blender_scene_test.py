"""Real Blender camera solve, GLB render, and video composite acceptance."""

import tempfile
import unittest
import os
import shutil
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
import trimesh

from ssui.base import Mesh, Prompt, Video
from tests.utils import add_extension_paths

add_extension_paths()
from ssui_video.BlenderSceneComposite import blender_composite_scene


class BlenderSceneTest(unittest.TestCase):
    def test_true_camera_solve_and_render(self):
        build_dir = Path(__file__).resolve().parents[1] / ".build"
        build_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_dir) as folder:
            root = Path(folder)
            source = root / "parallax.mp4"
            rng = np.random.default_rng(341)
            world = np.column_stack((rng.uniform(-2.4, 2.4, 180),
                                     rng.uniform(-1.8, 1.8, 180),
                                     rng.uniform(3.5, 9, 180))).astype(np.float32)
            camera_matrix = np.float32([[310, 0, 160], [0, 310, 120], [0, 0, 1]])
            colors = rng.integers(110, 255, (len(world), 3), dtype=np.uint8)
            writer = imageio.get_writer(str(source), fps=12, codec="libx264", macro_block_size=1)
            try:
                for index in range(16):
                    image = np.full((240, 320, 3), 35, dtype=np.uint8)
                    projected, _ = cv2.projectPoints(world, np.zeros(3),
                                                      np.float32([-index * .025, 0, 0]),
                                                      camera_matrix, np.zeros(5))
                    for point, color in zip(projected.reshape(-1, 2), colors):
                        x, y = np.rint(point).astype(int)
                        if 7 <= x < 313 and 7 <= y < 233:
                            cv2.rectangle(image, (x - 2, y - 2), (x + 2, y + 2),
                                          tuple(int(channel) for channel in color), -1)
                    writer.append_data(image)
            finally:
                writer.close()
            asset = root / "cube.glb"
            trimesh.creation.box().export(asset)
            result = blender_composite_scene(
                Video(path=str(source), metadata={"anchor_x": .52, "anchor_y": .66}),
                Mesh(path=str(asset)), Prompt("place a cube"), focal_px=310,
                max_solve_error=3, output_dir=str(root / "result"))
            self.assertTrue(Path(result.path).is_file())
            self.assertTrue(Path(result.metadata["scene_path"]).is_file())
            self.assertEqual(result.metadata["camera_frames"], 16)
            self.assertGreater(result.metadata["camera_translation_span"], .01)
            self.assertLess(result.metadata["solve_error_px"], 3)
            original = imageio.get_reader(str(source), format="ffmpeg")
            rendered = imageio.get_reader(result.path, format="ffmpeg")
            try:
                self.assertGreater(np.mean(np.abs(original.get_data(0).astype(float) -
                                                  rendered.get_data(0).astype(float))), 1)
            finally:
                original.close()
                rendered.close()
            if os.environ.get("SSUI_KEEP_BLENDER_SCENE_TEST") == "1":
                evidence = Path(__file__).resolve().parents[1] / ".build" / "blender-scene-acceptance"
                evidence.mkdir(parents=True, exist_ok=True)
                shutil.copy2(result.path, evidence / "composite.mp4")
                shutil.copy2(result.metadata["scene_path"], evidence / "scene.blend")
                shutil.copy2(result.metadata["report_path"], evidence / "solve.json")
                shutil.copy2(root / "result" / "renders" / "frame_0001.png", evidence / "frame_0001.png")


if __name__ == "__main__":
    unittest.main()
