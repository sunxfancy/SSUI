from pathlib import Path
import tempfile
import unittest

import numpy as np
import trimesh

from ssui_3dmodel.quad_quality import repair_polygons, inspect_boundaries, edge_counts, validate_glb


class QuadQualityTest(unittest.TestCase):
    def assert_valid_triangles(self, vertices, triangles):
        p = np.asarray(vertices)[np.asarray(triangles)]
        areas = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
        self.assertTrue(np.all(areas > 0))

    def test_collinear_corner_uses_the_other_diagonal_without_moving_vertices(self):
        vertices = [[0,0,0], [1,0,0], [2,0,0], [0,1,0]]
        v, faces, triangles, report = repair_polygons(vertices, [[0,1,2,3]])
        self.assertEqual(v, vertices)
        self.assertEqual(faces, [[0,1,2,3]])
        self.assert_valid_triangles(v, triangles)
        self.assertEqual(report['moved_vertices'], 0)
        self.assertAlmostEqual(trimesh.Trimesh(v, triangles, process=False).area, 1)

    def test_collapsed_edge_is_unfolded_without_changing_face_connectivity(self):
        vertices = [[0,0,0], [1,0,0], [1,0,0], [0,1,0], [2,0,0], [2,1,0]]
        faces = [[0,1,2,3], [1,4,5,2]]
        v, repaired, triangles, report = repair_polygons(vertices, faces)
        self.assertEqual(repaired, faces)
        self.assertEqual(edge_counts(repaired), edge_counts(faces))
        self.assert_valid_triangles(v, triangles)
        self.assertEqual(report['regularized_faces'], 2)
        self.assertLessEqual(report['max_vertex_displacement_fraction'], .00005 + 1e-12)

    def test_zero_area_face_removed_but_real_surface_preserved(self):
        vertices = [[0,0,0], [1,0,0], [1,1,0], [0,1,0], [2,0,0], [3,0,0]]
        v, faces, triangles, report = repair_polygons(vertices, [[0,1,2,3], [0,1,4,5]])
        self.assertEqual(report['removed_zero_area_faces'], 1)
        self.assertEqual(len(faces), 1)
        self.assertEqual(len(v), 4)
        self.assertAlmostEqual(trimesh.Trimesh(v, triangles, process=False).area, 1)

    def test_entirely_collapsed_mesh_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'no nonzero-area surface'):
            repair_polygons([[0,0,0]] * 4, [[0,1,2,3]])

    def test_cut_boundaries_are_preserved_and_matched_to_input(self):
        vertices = [[0,0,0], [1,0,0], [1,1,0], [0,1,0]]
        source = trimesh.Trimesh(vertices, [[0,1,2], [0,2,3]], process=False)
        v, faces, _, _ = repair_polygons(vertices, [[0,1,2,3]])
        report = inspect_boundaries(v, faces, source)
        self.assertEqual(report['input_boundary_edges'], 4)
        self.assertEqual(report['output_boundary_edges'], 4)
        self.assertEqual(report['boundary_edges_away_from_input'], 0)
        self.assertAlmostEqual(report['output_boundary_length'], 4)

    def test_new_hole_in_closed_input_is_reported(self):
        vertices = [[0,0,0], [1,0,0], [1,1,0], [0,1,0]]
        report = inspect_boundaries(vertices, [[0,1,2,3]], trimesh.creation.box())
        self.assertEqual(report['input_boundary_edges'], 0)
        self.assertEqual(report['boundary_edges_away_from_input'], 4)

    def test_closed_quad_cube_stays_closed(self):
        vertices = [[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]]
        faces = [[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
        v, repaired, triangles, _ = repair_polygons(vertices, faces)
        report = inspect_boundaries(v, repaired, trimesh.creation.box())
        self.assertEqual(report['output_boundary_edges'], 0)
        self.assertEqual(report['nonmanifold_edges'], 0)
        self.assertTrue(trimesh.Trimesh(v, triangles, process=False).is_watertight)

    def test_float32_export_collapse_is_detected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / 'collapsed.glb'
            vertices = np.array([[0,0,0], [1,0,0], [1,1,0], [0,1,0]], dtype=float) + 1e8
            trimesh.Trimesh(vertices, [[0,1,2], [0,2,3]], process=False).export(path)
            with self.assertRaisesRegex(ValueError, 'float32 conversion'):
                validate_glb(path)
