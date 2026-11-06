import tempfile
import unittest
from pathlib import Path
import imageio.v3 as iio
from PIL import Image as PILImage
import trimesh
from RestrictedPython import compile_restricted
from ssui.base import Image, Video, Mesh
from ss_executor.results import serialize_result


class MediaResultsTest(unittest.TestCase):
    def test_image_tuple_exports_unique_files(self):
        with tempfile.TemporaryDirectory() as root:
            image = Image(PILImage.new('RGB', (16, 16), 'red'))
            result = serialize_result((image, image), root)
            self.assertNotEqual(result[0]['path'], result[1]['path'])
            self.assertEqual(PILImage.open(result[0]['path']).getpixel((0, 0)), (255, 0, 0))

    def test_wrapped_frames_are_encoded_as_a_real_video(self):
        with tempfile.TemporaryDirectory() as root:
            frames = [Image(PILImage.new('RGB', (16, 16), (i * 30, 0, 0))) for i in range(8)]
            result = serialize_result(Video('mp4', frames, fps=8), root)
            self.assertEqual(result['type'], 'video')
            decoded = list(iio.imiter(result['path']))
            self.assertEqual(len(decoded), 8)
            self.assertGreater(float(decoded[-1].mean()), float(decoded[0].mean()) + 20)

    def test_mesh_exports_reloadable_glb(self):
        with tempfile.TemporaryDirectory() as root:
            result = serialize_result(Mesh(trimesh.creation.box()), root)
            self.assertEqual(result['type'], '3dmodel')
            mesh = trimesh.load(result['path'], force='mesh')
            self.assertEqual(len(mesh.faces), 12)

    def test_invalid_video_does_not_leave_a_published_file(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                serialize_result(Video('mp4', []), root)
            self.assertEqual(list((Path(root) / 'output').iterdir()), [])

    def test_examples_compile_in_the_actual_workflow_sandbox(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('workflow-wan21.py', 'workflow-cogvideo2b.py', 'workflow-text-to-3d.py', 'workflow-motion.py'):
            path = root / 'examples/advance' / name
            compile_restricted(path.read_text(), str(path), 'exec')

    def test_wan_example_prepares_with_the_registered_resident_model(self):
        from ss_executor.loader import SSLoader
        path = Path(__file__).resolve().parents[1] / 'examples/advance/workflow-wan21.py'
        loader = SSLoader(use_sandbox=True)
        loader.load(str(path))
        loader.Execute()
        function, params, _ = next(item for item in loader.callables if item[0].__name__ == 'text_to_video')
        self.assertEqual(params['model'].__module__, 'ssui_video.Wan21Resident')
        config = loader.GetConfig(function.__name__)['Generate video']
        self.assertEqual(config['num_frames']['default'], 17)
        self.assertEqual(config['width']['default'], 256)

    def test_motion_sidecar_is_retained_in_the_project_output(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'motion.npz'
            source.write_bytes(b'trusted motion data')
            frames = [PILImage.new('RGB', (16, 16)) for _ in range(2)]
            result = serialize_result(Video('mp4', frames, fps=8, artifacts={'motion.npz': str(source)}), root)
            exported = Path(result['artifacts'][0]['path'])
            self.assertEqual(exported.parent, Path(root) / 'output')
            self.assertEqual(exported.read_bytes(), source.read_bytes())
