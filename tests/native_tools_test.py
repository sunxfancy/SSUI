import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.native_tools import configure_native_tools


class NativeToolsTests(unittest.TestCase):
    def test_native_wheel_is_exposed_once_to_imageio_and_subprocesses(self):
        parent = Path(__file__).resolve().parents[1] / '.build/native-tools-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            self.assertTrue(Path(directory).resolve().is_relative_to(parent.resolve()))
            binary = Path(directory) / 'ffmpeg.exe'
            binary.touch()
            class Wheel:
                def locate_file(self, name):
                    self.requested = name
                    return binary
            with patch('backend.native_tools.sys.platform', 'win32'), \
                 patch('backend.native_tools.platform.machine', return_value='ARM64'), \
                 patch('backend.native_tools.importlib.metadata.distribution', return_value=Wheel()) as distribution, \
                 patch.dict(os.environ, {'PATH': 'existing'}, clear=True):
                self.assertEqual(configure_native_tools(), binary)
                self.assertEqual(configure_native_tools(), binary)
                self.assertEqual(os.environ['IMAGEIO_FFMPEG_EXE'], str(binary))
                self.assertEqual(os.environ['PATH'].split(os.pathsep), [directory, 'existing'])
                distribution.assert_called_once_with('imageio-ffmpeg')

    def test_user_override_and_other_architectures_are_preserved(self):
        with patch('backend.native_tools.sys.platform', 'win32'), \
             patch('backend.native_tools.platform.machine', return_value='ARM64'), \
             patch('backend.native_tools.importlib.metadata.distribution') as distribution, \
             patch.dict(os.environ, {'PATH': 'existing', 'IMAGEIO_FFMPEG_EXE': 'custom.exe'}, clear=True):
            self.assertEqual(configure_native_tools(), Path('custom.exe'))
            self.assertEqual(os.environ['PATH'], 'existing')
            distribution.assert_not_called()
        with patch('backend.native_tools.platform.machine', return_value='AMD64'), \
             patch('backend.native_tools.importlib.metadata.distribution') as distribution:
            self.assertIsNone(configure_native_tools())
            distribution.assert_not_called()

    def test_missing_binary_does_not_mutate_environment(self):
        class Wheel:
            def locate_file(self, name):
                return Path(__file__).parent / 'no-such-ffmpeg.exe'
        with patch('backend.native_tools.sys.platform', 'win32'), \
             patch('backend.native_tools.platform.machine', return_value='ARM64'), \
             patch('backend.native_tools.importlib.metadata.distribution', return_value=Wheel()), \
             patch.dict(os.environ, {'PATH': 'existing'}, clear=True):
            self.assertIsNone(configure_native_tools())
            self.assertEqual(dict(os.environ), {'PATH': 'existing'})
