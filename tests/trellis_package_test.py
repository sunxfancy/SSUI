"""The macOS package boundary must not affect other platform imports."""
import importlib.util
from pathlib import Path
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'extensions/3D-Model/vendor/trellis/modules/sparse/topology.py'


def load_topology():
    spec = importlib.util.spec_from_file_location('_trellis_topology_boundary', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrellisPackageTest(unittest.TestCase):
    def test_macos_delegates_to_installed_package(self):
        topology = ModuleType('ssui_trellis_mps.topology')
        for name in ('unique_rows', 'count_indices', 'neighbor_pairs', 'compact_pairs'):
            setattr(topology, name, object())
        with patch.object(sys, 'platform', 'darwin'), patch.dict(sys.modules, {'ssui_trellis_mps.topology': topology}):
            module = load_topology()
        for name in ('unique_rows', 'count_indices', 'neighbor_pairs', 'compact_pairs'):
            self.assertIs(getattr(module, name), getattr(topology, name))

    def test_other_platforms_do_not_import_macos_package(self):
        with patch.object(sys, 'platform', 'linux'), patch.dict(sys.modules, {'ssui_trellis_mps': None, 'ssui_trellis_mps.topology': None}):
            module = load_topology()
        import torch
        unique, inverse, counts = module.unique_rows(torch.tensor([[1,2],[1,2]]))
        self.assertEqual(unique.tolist(), [[1,2]])
        self.assertEqual(counts.tolist(), [2])

    def test_missing_mac_package_has_install_guidance(self):
        with patch.object(sys, 'platform', 'darwin'), patch.dict(sys.modules, {'ssui_trellis_mps': None, 'ssui_trellis_mps.topology': None}):
            with self.assertRaisesRegex(ImportError, 'Install ssui-trellis-mps'):
                load_topology()
