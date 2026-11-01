import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import trimesh
from ssui_3dmodel.holopart_closure import close_part, quadrangulate, run, thin_shell
from ssui_3dmodel.quad_quality import edge_counts, validate_glb


@unittest.skipUnless(importlib.util.find_spec('pymeshlab'), 'Optional native MeshLab required')
class HoloPartClosureTest(unittest.TestCase):
    def assert_closed(self, vertices, faces, triangles):
        self.assertTrue(all(len(f)==4 for f in faces))
        self.assertTrue(all(n==2 for n in edge_counts(faces).values()))
        self.assertTrue(trimesh.Trimesh(vertices,triangles,process=False).is_watertight)

    def test_closed_part_is_unchanged(self):
        cube=trimesh.creation.box()
        v,f=quadrangulate(cube.vertices,cube.faces)
        points,faces,triangles,stats=close_part(v,f)
        self.assertFalse(stats['refined'])
        np.testing.assert_array_equal(points,v)
        self.assertEqual(faces,f)
        self.assert_closed(points,faces,triangles)

    def test_cube_hole_is_capped_and_remains_all_quads(self):
        cube=trimesh.creation.box()
        cube.update_faces(cube.face_normals[:,2]<.5)
        v,f=quadrangulate(cube.vertices,cube.faces)
        points,faces,triangles,stats=close_part(v,f)
        self.assertTrue(stats['refined'])
        self.assertGreater(stats['inserted_triangles'],0)
        self.assert_closed(points,faces,triangles)
        np.testing.assert_allclose(np.ptp(points,axis=0),[1,1,1])

    def test_odd_boundary_loops_are_closed_without_t_junctions(self):
        v=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,0,1],[0,1,1]],dtype=float)
        f=[[0,1,4,3],[1,2,5,4],[2,0,3,5]]
        points,faces,triangles,stats=close_part(v,f)
        self.assertEqual(stats['input_boundary_edges'],6)
        self.assert_closed(points,faces,triangles)

    def test_flat_open_sheet_uses_bounded_thickness_without_losing_surface(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],dtype=float)
        points,faces,triangles,stats=close_part(v,[[0,1,2,3]])
        shell=[c for c in stats['components'] if c['method']=='bounded_thin_shell']
        self.assertEqual(len(shell),1)
        self.assertLessEqual(np.max(np.abs(points[:,2])),np.sqrt(2)*.00002*1.000001)
        self.assert_closed(points,faces,triangles)
        np.testing.assert_allclose(np.ptp(points[:,:2],axis=0),[1,1])

    def test_nonmanifold_edge_is_refused(self):
        v=[[0,0,0],[1,0,0],[0,1,0],[0,0,1],[0,-1,0]]
        with self.assertRaisesRegex(RuntimeError,'nonmanifold'):
            close_part(v,[[0,1,2],[1,0,3],[0,1,4]])

    def test_vertex_touching_sheets_remain_separate_closed_components(self):
        v=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[-1,0,0],[-1,-1,0],[0,-1,0]]
        points,faces,triangles,stats=close_part(v,[[0,1,2,3],[0,4,5,6]])
        self.assertEqual(stats['preserved_components'],2)
        self.assertGreater(stats['split_vertices'],0)
        self.assert_closed(points,faces,triangles)

    def test_worker_preserves_23_exported_group_names_and_checks_real_glb(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            preview=[]
            for i in range(23):
                preview.append({'name':f'part_{i:02d}', 'vertices':[[i*2,0,0],[i*2+1,0,0],[i*2+1,1,0],[i*2,1,0]],'faces':[[0,1,2,3]]})
            (root/'input-preview.json').write_text(json.dumps(preview))
            (root/'input-report.json').write_text(json.dumps({'quality':{'parts':23,'quads':23}}))
            (root/'source.json').write_text(json.dumps({'preview_path':str(root/'input-preview.json'),
                'artifacts':{'report.json':str(root/'input-report.json')}}))
            run(root/'source.json',root)
            scene=trimesh.load(root/'retopology.glb',force='scene',process=False)
            self.assertEqual(set(scene.geometry),{p['name'] for p in preview})
            self.assertTrue(all(m.is_watertight for m in scene.geometry.values()))
            self.assertEqual(validate_glb(root/'retopology.glb'),0)
