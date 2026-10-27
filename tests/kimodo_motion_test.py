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

    def test_mps_runner_writes_typed_manifest_with_actual_frame_rate(self):
        import types
        from ssui_motion import _kimodo_runner as runner
        with tempfile.TemporaryDirectory() as directory:
            stem = str(Path(directory) / 'motion')
            Path(stem + '_report.json').write_text(json.dumps({'fps': 60, 'torch': 'test', 'device': 'mps'}), encoding='utf-8')
            with patch.dict('os.environ', {'SSUI_KIMODO_DEVICE': 'mps'}), \
                 patch.dict('sys.modules', {'_kimodo_mps': types.SimpleNamespace(main=lambda: None)}), \
                 patch('sys.argv', ['runner', 'walk', '--output', stem]), \
                 patch.object(runner, '_write_motion_manifest') as write:
                runner.main()
                self.assertEqual(write.call_args.args[:2], (stem, 60))
                self.assertEqual(write.call_args.args[2]['inference_device'], 'mps')

    def test_cpu_runner_overrides_device_without_recursive_loader(self):
        import types
        import torch
        from unittest.mock import Mock
        from ssui_motion import _kimodo_runner as runner

        generate = types.ModuleType('kimodo.scripts.generate')
        original = Mock(return_value=(types.SimpleNamespace(fps=24, denoiser=torch.nn.Linear(1, 1)), 'test'))
        generate.load_model = original
        generate.main = lambda: generate.load_model('test', device='cuda:0')
        scripts = types.ModuleType('kimodo.scripts')
        scripts.generate = generate
        package = types.ModuleType('kimodo')
        package.__path__ = []
        modules = {'kimodo': package, 'kimodo.scripts': scripts, 'kimodo.scripts.generate': generate}
        with patch.dict('sys.modules', modules), \
             patch.dict('os.environ', {'SSUI_KIMODO_DEVICE': 'cpu', 'TEXT_ENCODER_DEVICE': 'auto'}), \
             patch('sys.argv', ['runner', 'walk', '--output', 'motion']), \
             patch.object(runner, '_configure_text_encoder_override'), \
             patch.object(runner, '_write_motion_manifest') as write:
            runner.main()
            original.assert_called_once_with('test', device='cpu')
            self.assertIs(generate.load_model, original)
            self.assertEqual(write.call_args.args[1], 24)
            self.assertEqual(write.call_args.args[2]['inference_device'], 'cpu')
