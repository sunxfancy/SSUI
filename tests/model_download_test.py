import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from tests.download_models import _download_file


class ModelDownloadTest(unittest.TestCase):
    def test_snapshot_returns_the_selected_model_subdirectory(self):
        from tests.download_models import download_entry
        entry = dict(repo='test/model', snapshot=True, snapshot_subdir='component')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch('tests.download_models.load_manifest', return_value={'model': entry}), \
                    patch('tests.download_models.data_dir', return_value=root), \
                    patch('tests.download_models._download_snapshot') as download:
                result = download_entry('model')
            download.assert_called_once_with(entry, root / 'model')
            self.assertEqual(result, root / 'model/component')

    def download(self, dest, chunks, size=4, digest=''):
        response = Mock(headers={'content-length': str(size)})
        response.iter_content.return_value = iter(chunks)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('tests.download_models.requests.get', return_value=response):
            _download_file(dict(repo='test/model', file='model.bin', sha256=digest), dest)

    def test_complete_download_is_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'model.bin'
            self.download(dest, [b'ab', b'cd'], digest=hashlib.sha256(b'abcd').hexdigest())
            self.assertEqual(dest.read_bytes(), b'abcd')
            self.assertFalse(dest.with_suffix('.bin.partial').exists())

    def test_truncated_download_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'model.bin'
            with self.assertRaisesRegex(RuntimeError, '下载不完整'):
                self.download(dest, [b'ab'])
            self.assertFalse(dest.exists())

    def test_hash_mismatch_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'model.bin'
            with self.assertRaisesRegex(RuntimeError, 'sha256'):
                self.download(dest, [b'abcd'], digest='bad')
            self.assertFalse(dest.exists())

    def test_existing_file_is_also_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'model.bin'
            dest.write_bytes(b'abcd')
            with self.assertRaisesRegex(RuntimeError, 'sha256'):
                self.download(dest, [], digest='bad')

    def test_hub_download_uses_the_model_data_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / 'transformer/nf4/model.safetensors'
            def download(*args, **kwargs):
                self.assertEqual(kwargs['local_dir'], str(root))
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b'abcd')
                return str(dest)
            with patch('huggingface_hub.hf_hub_download', side_effect=download):
                _download_file(dict(repo='test/model', file='transformer/nf4/model.safetensors',
                                    download_backend='hub'), dest)
            self.assertEqual(dest.read_bytes(), b'abcd')

    def test_auxiliary_config_does_not_inherit_weight_digest(self):
        from tests.download_models import download_entry
        with tempfile.TemporaryDirectory() as tmp:
            entry = dict(repo='test/model', file='weights.bin', sha256='weight-digest',
                         extra_files=['config.json'])
            with patch('tests.download_models.load_manifest', return_value={'model': entry}), \
                    patch('tests.download_models.data_dir', return_value=Path(tmp)), \
                    patch('tests.download_models._download_file') as download:
                download_entry('model')
            self.assertEqual(download.call_args_list[0].args[0]['sha256'], 'weight-digest')
            self.assertEqual(download.call_args_list[1].args[0]['sha256'], '')
