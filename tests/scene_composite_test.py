"""End-to-end CPU preview check with a generated textured camera clip."""

import tempfile
import unittest
import subprocess
import io
import json
from unittest.mock import patch
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
import trimesh
import imageio_ffmpeg

from ssui.base import Mesh, Prompt, Video
from tests.utils import add_extension_paths

add_extension_paths()
from ssui_video.SceneComposite import composite_scene, _suggest_anchor


class SceneCompositeTest(unittest.TestCase):
    def test_vision_grounder_contract(self):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()

        frame = np.zeros((48, 64, 3), np.uint8)
        answer = Response(json.dumps({"point": [.7, .8], "confidence": .91}).encode())
        with patch.dict("os.environ", {"SSUI_SCENE_GROUNDER_URL": "http://localhost/ground"}), \
             patch("urllib.request.urlopen", return_value=answer) as opened:
            point, source, confidence = _suggest_anchor(frame, "on the table")
        self.assertEqual(point, (.7, .8))
        self.assertEqual(source, "vision_grounder")
        self.assertEqual(confidence, .91)
        self.assertIn("image_jpeg_base64", json.loads(opened.call_args.args[0].data))

    def test_generated_clip_and_manual_anchor(self):
        build_dir = Path(__file__).resolve().parents[1] / ".build"
        build_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_dir) as folder:
            folder = Path(folder)
            source = folder / "source.mp4"
            output = folder / "result.mp4"
            writer = imageio.get_writer(str(source), fps=12, codec="libx264", macro_block_size=1)
            rng = np.random.default_rng(42)
            background = rng.integers(50, 200, (240, 320, 3), dtype=np.uint8)
            try:
                for index in range(8):
                    zoom = 1 + index * .02
                    matrix = np.float32([[zoom, 0, index * 2], [0, zoom, index]])
                    writer.append_data(cv2.cvtColor(cv2.warpAffine(background, matrix, (320, 240)), cv2.COLOR_BGR2RGB))
            finally:
                writer.close()
            with_audio = folder / "with-audio.mp4"
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-i", str(source), "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                            "-shortest", str(with_audio)], check=True)
            mesh = Mesh(trimesh.creation.box(extents=(1, 1, 1)))
            glb = folder / "box.glb"
            mesh._model.export(glb)
            result = composite_scene(Video(path=str(with_audio), metadata={"anchor_x": .5, "anchor_y": .8}),
                                     Mesh(path=str(glb)), Prompt("在桌面放一个金色盒子"), output_path=str(output))
            self.assertTrue(output.is_file())
            self.assertEqual(result.metadata["anchor_source"], "manual")
            self.assertEqual(result.metadata["frames"], 8)
            self.assertGreater(result.metadata["tracking_confidence"], .5)
            self.assertGreater(result.metadata["scale_range"][1], 1.05)
            self.assertTrue(result.metadata["audio_muxed"])
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output),
                            "-map", "0:a:0", "-f", "null", "-"], check=True,
                           capture_output=True)
            suggested = composite_scene(Video(path=str(source)), mesh,
                                        Prompt("put a cube on the left table"),
                                        output_path=str(folder / "suggested.mp4"))
            self.assertEqual(suggested.metadata["anchor_source"], "spatial_text_hint")
            self.assertEqual(suggested.metadata["anchor_confidence"], .2)
            self.assertLess(suggested.metadata["anchor_x"], .5)
            original = imageio.get_reader(str(source), format="ffmpeg")
            rendered = imageio.get_reader(str(output), format="ffmpeg")
            try:
                frame_a = original.get_data(0)
                frame_b = rendered.get_data(0)
                self.assertGreater(np.mean(np.abs(frame_a.astype(float) - frame_b.astype(float))), 1)
            finally:
                original.close()
                rendered.close()


if __name__ == "__main__":
    unittest.main()
