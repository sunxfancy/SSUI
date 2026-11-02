import importlib.util
from pathlib import Path
import tempfile
import unittest
import trimesh
from ssui_3dmodel.holopart_geometry import prepare


@unittest.skipUnless(importlib.util.find_spec('pymeshlab'), 'Optional native MeshLab required')
class HoloPartGeometryTest(unittest.TestCase):
    def test_retains_meaningful_components_and_reports_small_generated_island(self):
        large = trimesh.creation.box()
        second = trimesh.creation.box(extents=[.5]*3); second.apply_translation([3,0,0])
        island = trimesh.creation.box(extents=[.001]*3); island.apply_translation([4,0,0])
        mesh = trimesh.util.concatenate([large,second,island])
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            trimesh.Scene(mesh).export(str(job/'completed.glb'))
            original = (job/'completed.glb').read_bytes()
            report = prepare(job)
            self.assertEqual(report['parts'][0]['retained_components'], 2)
            self.assertEqual(report['parts'][0]['removed_components'], 1)
            self.assertLess(report['parts'][0]['removed_area_fraction'], .001)
            self.assertEqual((job/'completed.glb').read_bytes(), original)
            self.assertTrue((job/'prepared.glb').is_file())

    def test_refuses_excessive_geometry_loss(self):
        a = trimesh.creation.box(); b=a.copy(); b.apply_translation([3,0,0])
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory)
            trimesh.Scene(trimesh.util.concatenate([a,b])).export(str(job/'completed.glb'))
            with self.assertRaises(RuntimeError):
                prepare(job, minimum_area_fraction=.6)

    def test_bad_generated_geometry_does_not_produce_prepared_output(self):
        with tempfile.TemporaryDirectory() as directory:
            job=Path(directory)
            tiny=trimesh.Trimesh(vertices=[[0,0,0],[1,0,0],[0,1,0]],faces=[[0,1,2]])
            trimesh.Scene(tiny).export(str(job/'completed.glb'))
            with self.assertRaisesRegex(RuntimeError, 'No usable'):
                prepare(job)
            self.assertFalse((job/'prepared.glb').exists())
