"""Cross-device offload accounting without requiring GPU hardware."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch


path = Path(__file__).resolve().parents[1] / "extensions/Video/diffsynth/device_utils.py"
spec = importlib.util.spec_from_file_location("video_device_utils", path)
devices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(devices)


class VideoMemoryTest(unittest.TestCase):
    def test_cuda_uses_cuda_budget_and_usage(self):
        with patch.object(devices.torch.cuda, "mem_get_info", return_value=(4, 16)):
            self.assertEqual(devices.device_memory("cuda:0"), (16, 12))

    def test_cpu_counts_available_shared_memory(self):
        with patch.object(devices.psutil, "virtual_memory", return_value=types.SimpleNamespace(total=16, available=7)):
            self.assertEqual(devices.device_memory("cpu"), (16, 9))

    def test_mps_recommended_and_older_torch_fallback(self):
        with patch.object(devices.torch.cuda, "mem_get_info", side_effect=AssertionError("CUDA called")), \
             patch.object(devices.torch.mps, "driver_allocated_memory", return_value=3), \
             patch.object(devices.psutil, "virtual_memory", return_value=types.SimpleNamespace(total=16)):
            with patch.object(devices.torch.mps, "recommended_max_memory", return_value=12, create=True):
                self.assertEqual(devices.device_memory("mps"), (12, 3))
            with patch.object(devices.torch.mps, "recommended_max_memory", None, create=True):
                self.assertEqual(devices.device_memory("mps"), (8, 3))

    def test_cache_clear_is_device_specific(self):
        with patch.object(devices.torch.cuda, "empty_cache") as cuda, \
             patch.object(devices.torch.mps, "empty_cache") as mps:
            devices.empty_device_cache("cpu")
            cuda.assert_not_called()
            mps.assert_not_called()
            devices.empty_device_cache("mps")
            mps.assert_called_once()
            cuda.assert_not_called()
            devices.empty_device_cache("cuda")
            cuda.assert_called_once()
