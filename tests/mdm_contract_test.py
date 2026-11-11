import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from ssui.base import Prompt
from ssui.config import SSUIConfig
from ssui_motion.MDM import Motion, MDMModel, MDMTextToMotion


class MotionContractTest(unittest.TestCase):
    def test_export_is_portable_without_pickle(self):
        with tempfile.TemporaryDirectory() as tmp:
            joints = np.arange(2 * 22 * 3).reshape(2, 22, 3).astype(np.float32)
            path = str(Path(tmp) / 'motion.npz')
            Motion(joints, 20.0, Path(tmp), 'walking').export(path)
            with np.load(path, allow_pickle=False) as saved:
                np.testing.assert_array_equal(saved['joints'], joints)
                self.assertEqual(saved['fps'], 20.0)
                self.assertEqual(str(saved['text']), 'walking')

    def test_prepare_never_launches_inference(self):
        config = SSUIConfig()
        config.set_prepared(True)
        with patch('ssui_motion.MDM.subprocess.run') as run:
            result = MDMTextToMotion(config('Motion'), None, Prompt('walk'))
        run.assert_not_called()
        self.assertEqual(result.joints.shape, (0, 22, 3))

    def test_missing_official_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'repository'):
                MDMModel.load(tmp, 'missing.pt')
