"""Host-side Kimodo routing and opt-in independent MPS runtime checks."""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]


class KimodoMpsTest(unittest.TestCase):
    def test_node_passes_explicit_mps_devices(self):
        sys.path.insert(0,str(ROOT/'extensions/Motion'))
        module=importlib.import_module('ssui_motion.Kimodo')
        config=dict(model='Kimodo-SOMA-RP-v1.1',duration=2.,diffusion_steps=20,seed=42,
                    device='mps',text_encoder_device='mps',export_bvh=True)
        process=MagicMock(returncode=0,stdout=iter([]))
        with patch.object(module,'_kimodo_python',return_value='/runtime/python'), \
             patch.object(module.subprocess,'Popen',return_value=process) as launch, \
             patch.object(module.os.path,'isfile',return_value=True):
            result=module._run_kimodo(config,MagicMock(text='A person walks.'))
        args,kwargs=launch.call_args
        self.assertEqual(kwargs['env']['SSUI_KIMODO_DEVICE'],'mps')
        self.assertEqual(kwargs['env']['TEXT_ENCODER_DEVICE'],'mps')
        self.assertIn('--bvh',args[0])
        self.assertTrue(result.endswith('.npz'))

    @unittest.skipUnless(os.environ.get('SSUI_RUN_MOTION_RUNTIME_TESTS')=='1','opt-in real Kimodo MPS runtime')
    def test_streamed_encoder_and_trained_motion_block(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/kimodo_mac_smoke.py'),'--stage','check'],
                              cwd=ROOT,capture_output=True,text=True,timeout=180)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout)
