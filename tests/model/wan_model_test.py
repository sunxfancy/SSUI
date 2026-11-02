import os
import unittest
from tests.utils import download_if_needed, should_run_model_tests, model_output_dir


@unittest.skipUnless(should_run_model_tests(), '需要 SSUI_RUN_MODEL_TESTS=1')
class TestWan21Model(unittest.TestCase):
    def test_text_to_video(self):
        import imageio.v3 as iio
        from diffsynth import save_video
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_video.Wan21 import Wan21Model, Wan21TextToVideo
        model = Wan21Model.load(str(download_if_needed('wan21')))
        config = SSUIConfig()
        frames = Wan21TextToVideo(config('Generate video'), model,
                                 Prompt('A red toy car driving on a wooden table, cinematic lighting'),
                                 Prompt('blurry, distorted, still image'))
        self.assertEqual(len(frames), 17)
        self.assertEqual(frames[0]._image.size, (256, 256))
        with model_output_dir('wan21') as output:
            path = os.path.join(output, 'video.mp4')
            save_video([frame._image for frame in frames], path, fps=8)
            decoded = list(iio.imiter(path))
            self.assertEqual(len(decoded), 17)
