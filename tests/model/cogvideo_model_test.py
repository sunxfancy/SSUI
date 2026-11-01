import os
import unittest
from tests.utils import should_run_model_tests, model_output_dir, download_if_needed


@unittest.skipUnless(should_run_model_tests(), '需要 SSUI_RUN_MODEL_TESTS=1')
class TestCogVideo2BModel(unittest.TestCase):
    def test_text_to_video(self):
        import imageio.v3 as iio
        from diffusers.utils import export_to_video
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_video.CogVideo2B import CogVideo2BModel, CogVideo2BTextToVideo
        model = CogVideo2BModel.load(str(download_if_needed('cogvideo2b')))
        config = SSUIConfig()
        frames = CogVideo2BTextToVideo(config('Generate video'), model,
                    Prompt('A red toy car driving on a wooden table, cinematic lighting'),
                    Prompt('blurry, distorted, still image'))
        self.assertEqual(len(frames), 49)
        self.assertEqual(frames[0]._image.size, (720, 480))
        with model_output_dir('cogvideo2b') as output:
            path = os.path.join(output, 'video.mp4')
            export_to_video([frame._image for frame in frames], path, fps=8)
            self.assertEqual(len(list(iio.imiter(path))), 49)
