import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import trimesh
from ssui import Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.HoloPart import CompleteParts, complete_parts


class HoloPartTest(unittest.TestCase):
    def test_worker_failure_keeps_diagnostic_log(self):
        import sys
        from ssui_3dmodel.HoloPart import _run
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'worker.log'
            with self.assertRaisesRegex(RuntimeError, 'HIP unavailable'):
                _run([sys.executable, '-c', "print('HIP unavailable'); raise SystemExit(7)"], log)
            self.assertIn('HIP unavailable', log.read_text())

    def test_prepare_does_not_launch_or_load_weights(self):
        config = SSUIConfig()
        config.set_prepared()
        with patch('subprocess.run', side_effect=AssertionError('process started')):
            self.assertIsNone(CompleteParts(config('completion'), Mesh())._model)
        self.assertEqual(config._config['completion']['steps']['default'], 50)

    def test_missing_input_and_dependencies_fail_explicitly(self):
        with self.assertRaises(ValueError):
            complete_parts(Mesh())
        with self.assertRaises(ValueError):
            complete_parts(Mesh(trimesh.creation.box()), steps=0)
        with patch.dict(os.environ, {'SSUI_HOLOPART_PYTHON': ''}):
            with self.assertRaisesRegex(RuntimeError, 'SSUI_HOLOPART'):
                complete_parts(Mesh(trimesh.creation.box()))

    def test_native_worker_contract_preserves_parts_and_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'scripts/inference_holopart.py').touch()
            (root / 'model_index.json').write_text('{}')
            def worker(command, log):
                self.assertEqual(command[1], '-u')
                self.assertNotIn('wsl.exe', command)
                job = Path(command[6])
                source = trimesh.load(command[5], force='scene')
                source.export(str(job / 'completed.glb'))
                source.export(str(job / 'prepared.glb'))
                (job / 'preparation.json').write_text('{}')
                (job / 'completion.json').write_text(json.dumps({'input_parts': 1, 'output_parts': 1,
                    'runtime': {'backend': 'native-rocm'}}))
                from subprocess import CompletedProcess
                return CompletedProcess(command, 0, 'real worker mocked for contract', '')
            env = {'SSUI_HOLOPART_ROOT': str(root), 'SSUI_HOLOPART_WEIGHTS': str(root),
                   'SSUI_HOLOPART_PYTHON': 'native-python', 'SSUI_3D_OUTPUT': str(root)}
            with patch.dict(os.environ, env), patch('ssui_3dmodel.HoloPart._run', side_effect=worker):
                result = complete_parts(Mesh(trimesh.creation.box()))
            self.assertEqual(set(result.artifacts), {'completed.glb', 'prepared.glb', 'completion.json', 'preparation.json'})
            self.assertTrue(Path(result.artifacts['completed.glb']).is_file())
