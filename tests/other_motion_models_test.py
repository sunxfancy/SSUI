from pathlib import Path
import unittest
from unittest.mock import patch

from ssui import MotionClip, Prompt
from ssui.config import SSUIConfig
from ss_executor.loader import SSLoader
from ssui_motion.OtherModels import GenerateHYMotion, GenerateMSFlowMotion


class OtherMotionModelsTest(unittest.TestCase):
    def test_workflows_prepare_without_loading_runtime(self):
        root = Path(__file__).resolve().parents[1]
        for engine, filename, name in [('HY', 'workflow-motion-hy.py', 'txt2motion_hy'),
                                       ('MSFlow', 'workflow-motion-msflow.py', 'txt2motion_msflow'),
                                       ('ARDY', 'workflow-motion-ardy.py', 'txt2motion_ardy')]:
            with self.subTest(engine=engine):
                loader = SSLoader(use_sandbox=True)
                loader.load(str(root / 'examples/advance' / filename))
                loader.Execute()
                self.assertTrue(loader.GetConfig(name))

    def test_prepare_and_empty_prompt_never_start_subprocess(self):
        for fn in (GenerateHYMotion, GenerateMSFlowMotion):
            with self.subTest(fn=fn.__name__), patch('ssui_motion.OtherModels._run_model') as run:
                config = SSUIConfig()
                config.set_prepared()
                self.assertIsInstance(fn(config('motion'), None), MotionClip)
                config.set_prepared(False)
                with self.assertRaisesRegex(ValueError, '描述不能为空'):
                    fn(config('motion'), Prompt(' '))
                run.assert_not_called()
