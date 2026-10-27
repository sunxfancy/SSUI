import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ssui import MotionClip, Prompt
from ssui.config import SSUIConfig
from ssui_motion.Kimodo import GenerateKimodoMotion, _kimodo_python
from ss_executor.__main__ import convert_task_return


class KimodoMotionTest(unittest.TestCase):
    def test_prepare_needs_no_child_environment(self):
        config = SSUIConfig()
        config.set_prepared()
        with patch('ssui_motion.Kimodo._run_kimodo', side_effect=AssertionError('generation during prepare')):
            self.assertIsInstance(GenerateKimodoMotion(config('motion'), None), MotionClip)

    def test_motion_result_has_native_downloads_and_fps(self):
        with tempfile.TemporaryDirectory() as root:
            stem = Path(root) / 'motion'
            stem.with_suffix('.npz').write_bytes(b'NPZ')
            stem.with_suffix('.bvh').write_text('HIERARCHY', encoding='utf-8')
            stem.with_suffix('.motion.json').write_text(json.dumps({'fps': 30, 'positions': [[[0, 0, 0]]] * 60}), encoding='utf-8')
            config = SSUIConfig()
            config.set_prepared(False)
            with patch('ssui_motion.Kimodo._run_kimodo', return_value=str(stem.with_suffix('.npz'))):
                clip = GenerateKimodoMotion(config('motion'), Prompt('walk'))
            payload = convert_task_return(clip, str(Path(root) / 'workflow.py'))
            self.assertEqual(payload['type'], 'motion_clip')
            self.assertEqual(payload['duration'], 2)
            self.assertEqual(payload['bvh_path'], str(stem.with_suffix('.bvh')))

    def test_empty_prompt_fails_before_launching(self):
        config = SSUIConfig()
        config.set_prepared(False)
        with patch('ssui_motion.Kimodo._run_kimodo') as run:
            with self.assertRaisesRegex(ValueError, '描述不能为空'):
                GenerateKimodoMotion(config('motion'), Prompt('  '))
            run.assert_not_called()

    def test_missing_motion_manifest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'preview manifest'):
            convert_task_return(MotionClip(), 'workflow.py')

    def test_explicit_interpreter_is_preserved(self):
        with patch.dict('os.environ', {'SSUI_KIMODO_PYTHON': 'C:/models/kimodo/python.exe'}):
            self.assertEqual(_kimodo_python(), 'C:/models/kimodo/python.exe')
