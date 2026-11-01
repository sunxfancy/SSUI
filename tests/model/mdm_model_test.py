import os
import unittest
import numpy as np
from tests.utils import should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestMDMModel(unittest.TestCase):
    def test_text_to_motion(self):
        from ssui.base import Prompt
        from ssui.config import SSUIConfig
        from ssui_motion.MDM import MDMModel, MDMTextToMotion

        repo = os.environ.get('SSUI_MDM_REPO')
        checkpoint = os.environ.get('SSUI_MDM_CHECKPOINT')
        self.assertTrue(repo and checkpoint,
                        'Set SSUI_MDM_REPO and SSUI_MDM_CHECKPOINT to official MDM assets')
        model = MDMModel.load(repo, checkpoint)
        config = SSUIConfig()
        motion = MDMTextToMotion(config('Generate motion'), model,
                                Prompt('a person walks forward'))
        self.assertEqual(motion.joints.shape, (40, 22, 3))
        self.assertGreater(float(np.abs(np.diff(motion.joints, axis=0)).max()), 0.001)
        exported = np.load(motion.output_dir / 'motion.npz', allow_pickle=False)
        np.testing.assert_allclose(exported['joints'], motion.joints)
        self.assertEqual(len(motion.preview()._frames), 40)
