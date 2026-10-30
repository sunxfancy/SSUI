import json
import struct
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_assets import TARGETS, binary_arch, digest, verify


class AssetsTest(unittest.TestCase):
    def test_complete_release_and_reject_corrupt_missing_mixed_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for target in TARGETS:
                extension = {'windows': '.exe', 'macos': '.dmg', 'linux': '.deb'}[target.split('-')[0]]
                f = root / f'ssui-v1.0.0-{target}{extension}'
                f.write_bytes(target.encode())
                (root / (target + '.json')).write_text(json.dumps(dict(target=target, name=f.name, tag='v1.0.0', sha='a'*40, sha256=digest(f))))
            self.assertEqual(len(verify(root, 'v1.0.0', 'a'*40)), 6)
            with self.assertRaises(ValueError):
                verify(root, 'v1.0.1', 'a'*40)
            f.write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                verify(root, 'v1.0.0', 'a'*40)
            (root / (target + '.json')).unlink()
            with self.assertRaises(ValueError):
                verify(root, 'v1.0.0', 'a'*40)

    def test_executable_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'app'
            for machine, arch in [(62, 'x86_64'), (183, 'arm64')]:
                data = bytearray(64)
                data[:6] = b'\x7fELF\x02\x01'
                struct.pack_into('<H', data, 18, machine)
                p.write_bytes(data)
                self.assertEqual(binary_arch(p), arch)
            p.write_bytes(b'\xcf\xfa\xed\xfe' + struct.pack('<I', 0x100000c))
            self.assertEqual(binary_arch(p), 'arm64')
            data = bytearray(128)
            data[:2] = b'MZ'
            struct.pack_into('<I', data, 0x3c, 64)
            data[64:68] = b'PE\0\0'
            struct.pack_into('<H', data, 68, 0x8664)
            p.write_bytes(data)
            self.assertEqual(binary_arch(p), 'x86_64')
            p.write_bytes(b'not an executable')
            with self.assertRaises(ValueError):
                binary_arch(p)


class PreflightTest(unittest.TestCase):
    def test_rejects_foreign_wheels_and_cuda_arm_lock(self):
        from release_preflight import check_lock
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'deps.lock'
            for content in ['torch==2.4.1+cu124', 'pkg @ https://example.com/pkg-cp312-win_amd64.whl']:
                p.write_text(content)
                with self.assertRaises(ValueError):
                    check_lock(p, 'windows-arm64')
                check_lock(p, 'windows-x86_64')


class UploadTest(unittest.TestCase):
    def test_existing_asset_mismatch_is_never_overwritten(self):
        from unittest.mock import patch
        import upload_release_assets as uploader
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'installer.exe').write_bytes(b'new')
            def run(argv, **kwargs):
                self.assertEqual(argv[1:3], ['release', 'download'])
                (Path(argv[-1]) / 'installer.exe').write_bytes(b'old')
            meta = json.dumps(dict(isPrerelease=True, assets=[dict(name='installer.exe')]))
            with patch.object(uploader.subprocess, 'check_output', return_value=meta), patch.object(uploader.subprocess, 'run', side_effect=run):
                with self.assertRaisesRegex(ValueError, 'different bytes'):
                    uploader.upload('v1.0.0', p)

    def test_formal_release_rejects_uploads(self):
        from unittest.mock import patch
        import upload_release_assets as uploader
        with patch.object(uploader.subprocess, 'check_output', return_value='{"isPrerelease":false,"assets":[]}'), patch.object(uploader.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                uploader.upload('v1.0.0', Path('.'))
            run.assert_not_called()
