"""Verify large-model mmap loading also preserves legacy checkpoint support."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import torch


class CheckpointLoadingTest(unittest.TestCase):
    def test_modern_and_legacy_checkpoints_load_identically(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            '_checkpoint_utils', root / 'extensions/Video/diffsynth/models/utils.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        expected = {'weight': torch.arange(12).reshape(3, 4).float()}
        with tempfile.TemporaryDirectory() as tmp:
            for zipped in (True, False):
                with self.subTest(zipped=zipped):
                    path = str(Path(tmp) / f'checkpoint-{zipped}.pth')
                    torch.save(expected, path, _use_new_zipfile_serialization=zipped)
                    loaded = module.load_state_dict_from_bin(path)
                    torch.testing.assert_close(loaded['weight'], expected['weight'])
