import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import find_native_wheels
from verify_macos_wheels import dynamic_library_paths


class MachOLoadCommandTests(unittest.TestCase):
    def test_library_identity_is_not_an_external_dependency(self):
        commands = '''
Load command 1
          cmd LC_ID_DYLIB
      cmdsize 80
         name /DLC/torchvision/.dylibs/libpng.dylib (offset 24)
Load command 2
          cmd LC_LOAD_DYLIB
      cmdsize 80
         name @loader_path/libz.dylib (offset 24)
Load command 3
          cmd LC_RPATH
      cmdsize 40
         path /Users/build/venv/lib (offset 12)
'''
        self.assertEqual(dynamic_library_paths(commands), ['@loader_path/libz.dylib', '/Users/build/venv/lib'])

    def test_absolute_weak_and_reexport_dependencies_are_still_audited(self):
        commands = '''
          cmd LC_LOAD_WEAK_DYLIB
      cmdsize 80
         name /usr/local/lib/libfoo.dylib (offset 24)
          cmd LC_REEXPORT_DYLIB
      cmdsize 80
         name /DLC/not-an-identity.dylib (offset 24)
'''
        self.assertEqual(dynamic_library_paths(commands), ['/usr/local/lib/libfoo.dylib', '/DLC/not-an-identity.dylib'])


class CompiledWheelReuseTests(unittest.TestCase):
    @patch.object(find_native_wheels, 'gh')
    def test_later_validation_failure_can_resume_compiled_wheels(self, gh):
        gh.return_value = json.dumps({'jobs': [{'steps': [
            {'name': 'Build pinned native CPU wheels', 'conclusion': 'success'},
            {'name': 'Verify source wheel manifest', 'conclusion': 'success'},
            {'name': 'Verify portable native libraries', 'conclusion': 'failure'},
        ]}]})
        self.assertTrue(find_native_wheels.compiled_wheels_available('owner/repo', {'id': 1, 'conclusion': 'failure'}))

    @patch.object(find_native_wheels, 'gh')
    def test_incomplete_compilation_is_not_reused(self, gh):
        gh.return_value = json.dumps({'jobs': [{'steps': [
            {'name': 'Build pinned native CPU wheels', 'conclusion': 'failure'},
            {'name': 'Verify source wheel manifest', 'conclusion': 'skipped'},
        ]}]})
        self.assertFalse(find_native_wheels.compiled_wheels_available('owner/repo', {'id': 1, 'conclusion': 'failure'}))

    @patch.object(find_native_wheels, 'gh')
    def test_cancelled_run_is_not_reused(self, gh):
        self.assertFalse(find_native_wheels.compiled_wheels_available('owner/repo', {'id': 1, 'conclusion': 'cancelled'}))
        gh.assert_not_called()


if __name__ == '__main__':
    unittest.main()
