import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import trimesh

from ssui import Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.Retopology import SegmentParts, QuadRemesh, quad_remesh, segment_parts, _read_polygons, _wsl
from ssui_3dmodel.p3sam_worker import split_parts


class RetopologyTest(unittest.TestCase):
    def test_component_mode_retries_and_preserves_part_grouping(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable=Path(tmp)/'quadriflow.exe'; executable.touch()
            a=trimesh.creation.box(); b=a.copy(); b.apply_translation([3,0,0])
            commands=[]
            def run(command, cwd=None):
                commands.append(command)
                if len(commands)==1:
                    raise RuntimeError('singular small-component solve')
                source=trimesh.load(command[command.index('-i')+1],force='mesh')
                x=source.bounds[0,0]
                Path(command[command.index('-o')+1]).write_text(f'v {x} 0 0\nv {x+1} 0 0\nv {x+1} 1 0\nv {x} 1 0\nf 1 2 3 4\n')
            env={'SSUI_QUADRIFLOW_EXECUTABLE':str(executable),'SSUI_QUADRIFLOW_WSL_DISTRO':'','SSUI_3D_OUTPUT':tmp}
            with patch.dict(os.environ,env),patch('ssui_3dmodel.Retopology._run',side_effect=run):
                result=quad_remesh(Mesh(trimesh.util.concatenate([a,b])),100,split_components=True)
            report=json.loads(Path(result.artifacts['report.json']).read_text())
            self.assertEqual(len(commands),3)
            self.assertEqual(report['quality']['parts'],1)
            self.assertEqual(len(report['parts'][0]['components']),2)
            self.assertFalse(report['parts'][0]['components'][0]['attempts'][0]['success'])
            self.assertEqual(len(result._model.geometry),1)

    def test_wsl_bridge_keeps_spaces_and_translates_file_paths(self):
        command = _wsl(['/home/user/python', r'C:\models with spaces\worker.py',
                        r'D:\input\model.glb', '/home/user/weights.safetensors'],
                       'Ubuntu', r'C:\P3 SAM\demo')
        self.assertEqual(command, ['wsl.exe', '--distribution', 'Ubuntu', '--cd',
            '/mnt/c/P3 SAM/demo', '--', '/home/user/python',
            '/mnt/c/models with spaces/worker.py', '/mnt/d/input/model.glb',
            '/home/user/weights.safetensors'])

    def test_split_keeps_all_faces_and_unassigned_regions(self):
        mesh = trimesh.creation.box()
        labels = np.array([0] * 4 + [1] * 4 + [-1] * 4)
        scene, counts = split_parts(mesh, labels)
        self.assertEqual(sum(counts.values()), len(mesh.faces))
        self.assertIn('unassigned_1', counts)
        self.assertEqual(len(scene.geometry), 3)
        with self.assertRaises(ValueError):
            split_parts(mesh, labels[:-1])

    def test_prepare_does_not_launch_dependencies(self):
        config = SSUIConfig()
        config.set_prepared()
        with patch('subprocess.run', side_effect=AssertionError('must not launch')):
            self.assertIsNone(SegmentParts(config('segment'), Mesh())._model)
            self.assertIsNone(QuadRemesh(config('remesh'), Mesh())._model)
        self.assertIn('target_faces', config._config['remesh'])

    def test_missing_dependencies_fail_explicitly(self):
        with patch.dict(os.environ, {'SSUI_P3SAM_ROOT': 'missing', 'SSUI_P3SAM_PYTHON': ''}):
            with self.assertRaisesRegex(RuntimeError, 'SSUI_P3SAM_ROOT'):
                segment_parts(Mesh(trimesh.creation.box()))
        with self.assertRaises(ValueError):
            quad_remesh(Mesh(), 0)
        with patch.dict(os.environ, {'SSUI_QUADRIFLOW_EXECUTABLE': 'missing-quadriflow', 'SSUI_QUADRIFLOW_WSL_DISTRO': ''}):
            with self.assertRaisesRegex(RuntimeError, 'SSUI_QUADRIFLOW_EXECUTABLE'):
                quad_remesh(Mesh(trimesh.creation.box()), 100)

    def test_polygon_reader_preserves_quads_and_rejects_bad_indices(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / 'quad.obj'
            vertices = 'v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n'
            path.write_text(vertices + 'f -4/1 -3/2 -2/3 -1/4 # quad\n')
            _, faces = _read_polygons(path)
            self.assertEqual(faces, [[0, 1, 2, 3]])
            for face in ('f 1 2 9', 'f 0 1 2', 'f 1 1 2', 'f -9 -2 -1'):
                path.write_text(vertices + face)
                with self.assertRaises(ValueError):
                    _read_polygons(path)

    def test_standalone_cli_keeps_parts_transforms_and_quad_master(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            executable = Path(tmp) / 'quadriflow.exe'; executable.touch()
            commands = []
            def run(command, cwd=None):
                commands.append(command)
                source = trimesh.load(command[command.index('-i') + 1], force='mesh')
                x = source.bounds[0][0]
                target = Path(command[command.index('-o') + 1])
                target.write_text(f'v {x} 0 0\nv {x+1} 0 0\nv {x+1} 1 0\nv {x} 1 0\nf 1 2 3 4\n')
            scene = trimesh.Scene()
            scene.add_geometry(trimesh.creation.box(), node_name='body')
            transform = np.eye(4); transform[0, 3] = 10
            scene.add_geometry(trimesh.creation.box(), node_name='armor', transform=transform)
            with patch.dict(os.environ, {'SSUI_QUADRIFLOW_EXECUTABLE': str(executable), 'SSUI_QUADRIFLOW_WSL_DISTRO': '', 'SSUI_3D_OUTPUT': tmp}), patch('ssui_3dmodel.Retopology._run', side_effect=run):
                result = quad_remesh(Mesh(scene), 100)
            self.assertEqual(len(commands), 2)
            self.assertTrue(all('-boundary' in command and '-sharp' in command for command in commands))
            vertices, faces = _read_polygons(result.artifacts['retopology.obj'])
            self.assertEqual(faces, [[0, 1, 2, 3], [4, 5, 6, 7]])
            self.assertAlmostEqual(vertices[4][0], 9.5)
            preview = json.loads(Path(result.preview_path).read_text())
            self.assertTrue(all(len(part['faces'][0]) == 4 for part in preview))
            self.assertEqual(len(result._model.geometry), 2)
            self.assertNotIn('retopology.blend', result.artifacts)
            report = json.loads(Path(result.artifacts['report.json']).read_text())
            self.assertEqual([part['requested_faces'] for part in report['parts']], [50, 50])
            self.assertEqual(report['quality']['degenerate_export_triangles'], 0)

    def test_standalone_missing_output_fails(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            executable = Path(tmp) / 'quadriflow.exe'; executable.touch()
            with patch.dict(os.environ, {'SSUI_QUADRIFLOW_EXECUTABLE': str(executable), 'SSUI_QUADRIFLOW_WSL_DISTRO': '', 'SSUI_3D_OUTPUT': tmp}), patch('ssui_3dmodel.Retopology._run'):
                with self.assertRaisesRegex(RuntimeError, 'produced no mesh'):
                    quad_remesh(Mesh(trimesh.creation.box()), 100)

    def test_segmentation_worker_contract_and_scene_transforms(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            (root / 'demo').mkdir()
            (root / 'demo' / 'auto_mask.py').touch()
            def worker(command, cwd=None):
                self.assertEqual(Path(cwd), root / 'demo')
                out = Path(command[3])
                source = trimesh.load(command[2], force='scene')
                self.assertAlmostEqual(source.bounds[0][0], 9.5)
                source.export(out / 'segmented.glb')
                (out / 'segmentation.json').write_text('{}')
            scene = trimesh.Scene()
            transform = np.eye(4); transform[0, 3] = 10
            scene.add_geometry(trimesh.creation.box(), transform=transform)
            with patch.dict(os.environ, {'SSUI_P3SAM_ROOT': tmp, 'SSUI_P3SAM_PYTHON': 'python', 'SSUI_P3SAM_WSL_DISTRO': '', 'SSUI_3D_OUTPUT': tmp}), patch('ssui_3dmodel.Retopology._run', side_effect=worker):
                result = segment_parts(Mesh(scene))
            self.assertIn('segmented.glb', result.artifacts)

    def test_executor_preserves_downloads_and_preview_transforms(self):
        from ss_executor.__main__ import convert_task_return
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            scene = trimesh.Scene()
            transform = np.eye(4); transform[0, 3] = 10
            scene.add_geometry(trimesh.creation.box(), transform=transform)
            mesh = Mesh(scene)
            mesh.artifacts = {'retopology.obj': str(Path(tmp) / 'retopology.obj')}
            mesh.quality = {'degenerate_export_triangles': 0}
            with patch('ss_executor.__main__.search_project_root', return_value=tmp):
                payload = convert_task_return(mesh, str(Path(tmp) / 'workflow.py'))
            preview = json.loads(Path(payload['preview_path']).read_text())
            self.assertAlmostEqual(min(v[0] for v in preview[0]['vertices']), 9.5)
            self.assertEqual(payload['artifacts'], mesh.artifacts)
            self.assertEqual(payload['quality'], mesh.quality)

    @unittest.skipUnless(os.environ.get('SSUI_RUN_MODEL_TESTS') == '1' and os.environ.get('SSUI_P3SAM_ROOT'), 'Requires configured real P3-SAM environment')
    def test_real_p3sam(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp, patch.dict(os.environ, {'SSUI_3D_OUTPUT': tmp}):
            scene = trimesh.Scene()
            scene.add_geometry(trimesh.creation.box())
            result = segment_parts(Mesh(scene))
            self.assertGreater(len(result._model.geometry), 0)

    @unittest.skipUnless(os.environ.get('SSUI_QUADRIFLOW_EXECUTABLE'), 'Requires standalone QuadriFlow executable')
    def test_real_quadriflow_quads(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp, patch.dict(os.environ, {'SSUI_3D_OUTPUT': tmp}):
            result = quad_remesh(Mesh(trimesh.creation.icosphere(subdivisions=2)), 100)
            report = json.loads(Path(result.artifacts['report.json']).read_text())
            self.assertGreater(report['parts'][0]['quads'], 0)
            obj = Path(result.artifacts['retopology.obj']).read_text()
            self.assertTrue(any(len(line.split()) == 5 for line in obj.splitlines() if line.startswith('f ')))
