import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ssui import MotionClip, Prompt
from ssui.config import SSUIConfig
from ssui_motion.Ardy import GenerateArdyMotion, _ardy_python
from ss_executor.__main__ import convert_task_return


class ArdyMotionTest(unittest.TestCase):
    def test_prepare_does_not_launch_runtime(self):
        config = SSUIConfig()
        config.set_prepared()
        with patch('ssui_motion.Ardy._run_ardy', side_effect=AssertionError('runtime during prepare')):
            self.assertIsInstance(GenerateArdyMotion(config('ARDY'), None), MotionClip)

    def test_result_serializes_with_native_timing_and_download(self):
        with tempfile.TemporaryDirectory() as directory:
            stem = Path(directory) / 'motion'
            stem.with_suffix('.npz').write_bytes(b'NPZ')
            Path(str(stem) + '.motion.json').write_text(json.dumps({'fps': 20, 'positions': [[[0, 0, 0]]] * 40}), encoding='utf-8')
            config = SSUIConfig()
            config.set_prepared(False)
            with patch('ssui_motion.Ardy._run_ardy', return_value=stem):
                clip = GenerateArdyMotion(config('ARDY'), Prompt('walk'))
            payload = convert_task_return(clip, str(Path(directory) / 'workflow.py'))
            self.assertEqual(payload['type'], 'motion_clip')
            self.assertEqual(payload['duration'], 2)
            self.assertEqual(payload['npz_path'], str(stem) + '.npz')

    def test_empty_prompt_fails_before_process(self):
        config = SSUIConfig()
        config.set_prepared(False)
        with patch('ssui_motion.Ardy._run_ardy') as run:
            with self.assertRaisesRegex(ValueError, '描述不能为空'):
                GenerateArdyMotion(config('ARDY'), Prompt('  '))
            run.assert_not_called()

    def test_interpreter_override(self):
        with patch.dict('os.environ', {'SSUI_ARDY_PYTHON': '/runtime/python'}):
            self.assertEqual(_ardy_python(), '/runtime/python')

    def test_unicode_progress_does_not_crash_gbk_host(self):
        from ssui_motion._runtime import print_runtime_line
        output = io.BytesIO()
        stream = io.TextIOWrapper(output, encoding='gbk')
        with patch('sys.stdout', stream):
            print_runtime_line('loading \ufffd\u2588\n')
        stream.flush()
        self.assertTrue(output.getvalue())
