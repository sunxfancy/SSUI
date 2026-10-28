import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from server.text_file_service import FileConflictError, read_text, save_text


class TextFileServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / '脚本 & #1.py'
        self.path.write_bytes(b'original\r\n')

    def test_snapshot_and_repeated_save(self):
        snapshot = read_text(str(self.path))
        self.assertEqual(snapshot['content'], 'original\r\n')
        first = save_text(str(self.path), '更新\n', snapshot['version'])
        second = save_text(str(self.path), 'final', first['version'])
        self.assertEqual(read_text(str(self.path))['version'], second['version'])

    def test_external_change_and_deletion_conflict(self):
        version = read_text(str(self.path))['version']
        self.path.write_text('external')
        with self.assertRaises(FileConflictError):
            save_text(str(self.path), 'local', version)
        self.assertEqual(self.path.read_text(), 'external')
        self.path.unlink()
        with self.assertRaises(FileConflictError):
            save_text(str(self.path), 'local', version)
        self.assertFalse(self.path.exists())

    def test_only_one_concurrent_writer_succeeds(self):
        version = read_text(str(self.path))['version']
        def write(value):
            try:
                save_text(str(self.path), value, version)
                return True
            except FileConflictError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(write, ['one', 'two'])), 1)

    def test_failed_replace_preserves_original_and_cleans_temporary(self):
        original = self.path.read_bytes()
        with patch('server.text_file_service.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                save_text(str(self.path), 'replacement')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [self.path])

    def test_legacy_save_can_create_parent_directories(self):
        path = Path(self.directory.name) / 'new' / 'script.py'
        self.assertTrue(save_text(str(path), 'created')['success'])
        self.assertEqual(path.read_text(), 'created')

    def test_missing_file_is_not_a_successful_snapshot(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            read_text(str(self.path))
