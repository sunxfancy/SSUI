import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage

from ssui.base import Image
from ssui.config import SSUIConfig
from ssui_image.PixelArt import (
    AgentPaintAsset,
    FinalizePixelArt,
    PixelSrcAsset,
    RenderAgentPaint,
    RenderPixelSrc,
)


class TestPixelArtPipeline(unittest.TestCase):
    @staticmethod
    def _config(name, values):
        config = SSUIConfig()(name)
        config._update[name] = values
        return config

    def test_finalize_pixel_art_enforces_size_palette_and_alpha(self):
        source = PILImage.new("RGBA", (32, 32), (200, 20, 20, 90))
        source.paste((20, 200, 20, 255), (0, 0, 16, 16))
        config = self._config(
            "Finalize Pixel Art",
            {
                "width": 8,
                "height": 8,
                "colors": 4,
                "alpha_threshold": 128,
                "downsample": "nearest",
                "preview_scale": 2,
            },
        )

        result = FinalizePixelArt(config, Image(source))

        self.assertEqual(result._image.size, (16, 16))
        self.assertLessEqual(len(result._image.getcolors(maxcolors=256)), 5)
        self.assertEqual(set(result._image.getchannel("A").getdata()), {0, 255})

    @staticmethod
    def _fake_cli(command, **_kwargs):
        output_flag = "--out" if "--out" in command else "-o"
        if output_flag in command:
            output = Path(command[command.index(output_flag) + 1])
            PILImage.new("RGBA", (4, 3), (1, 2, 3, 255)).save(output)

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        return Completed()

    @patch("ssui_image.PixelArt.shutil.which", return_value="pixel-cli")
    @patch("ssui_image.PixelArt.subprocess.run", side_effect=_fake_cli.__func__)
    def test_agentpaint_adapter_validates_then_renders(self, run, _which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "hero.apx"
            source.write_text("{}", encoding="utf-8")
            asset = AgentPaintAsset.load(str(source))
            config = self._config(
                "Render AgentPaint Source", {"scale": 2, "frame": 0}
            )

            result = RenderAgentPaint(config, asset)

        self.assertEqual(result._image.size, (8, 6))
        self.assertEqual(run.call_args_list[0].args[0][1], "validate")
        self.assertEqual(run.call_args_list[1].args[0][1], "render")

    @patch("ssui_image.PixelArt.shutil.which", return_value="pixel-cli")
    @patch("ssui_image.PixelArt.subprocess.run", side_effect=_fake_cli.__func__)
    def test_pixelsrc_adapter_can_request_spritesheet(self, run, _which):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "hero.pxl"
            source.write_text("{}", encoding="utf-8")
            asset = PixelSrcAsset.load(str(source))
            config = self._config(
                "Render pixelsrc Source", {"scale": 3, "spritesheet": True}
            )

            result = RenderPixelSrc(config, asset)

        self.assertEqual(result._image.size, (4, 3))
        render_command = run.call_args_list[1].args[0]
        self.assertIn("--scale", render_command)
        self.assertIn("--spritesheet", render_command)


if __name__ == "__main__":
    unittest.main()
