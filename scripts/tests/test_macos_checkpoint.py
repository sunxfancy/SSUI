import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_macos_intel_wheels as builder


class TorchCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'native-wheels'
        self.output.mkdir()
        (self.root / 'dependencies').mkdir()
        self.wheel = self.root / '.build/torch-checkpoint/torch.whl'
        self.wheel.parent.mkdir(parents=True)
        self.wheel.write_bytes(b'compiled torch')
        recipe = dict(source=builder.SOURCES['torch'], environment=builder.BUILD_ENV, python='3.12.8')
        self.checkpoint = dict(repository='owner/repo', run=123, filename='torch.whl',
            recipe=hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest(),
            sha256=hashlib.sha256(self.wheel.read_bytes()).hexdigest())
        self.save()
        self.enterContext(patch.dict(os.environ, GITHUB_REPOSITORY='owner/repo'))
        self.enterContext(patch.object(builder.platform, 'python_version', return_value='3.12.8'))
        self.download = self.enterContext(patch.object(builder, 'run'))

    def save(self):
        (self.root / 'dependencies/macos-torch-checkpoint.json').write_text(json.dumps(self.checkpoint))

    def test_matching_recipe_and_hash_reuses_wheel(self):
        self.assertTrue(builder.restore_torch_checkpoint(self.root, self.output))
        self.assertEqual((self.output / 'torch.whl').read_bytes(), b'compiled torch')

    def test_changed_recipe_does_not_download(self):
        self.checkpoint['recipe'] = 'wrong'
        self.save()
        self.assertFalse(builder.restore_torch_checkpoint(self.root, self.output))
        self.download.assert_not_called()

    def test_corrupt_wheel_fails_closed(self):
        self.wheel.write_bytes(b'corrupted')
        with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
            builder.restore_torch_checkpoint(self.root, self.output)
        self.assertFalse((self.output / 'torch.whl').exists())

    def test_expired_checkpoint_falls_back_to_source(self):
        self.download.side_effect = builder.subprocess.CalledProcessError(1, ['gh'])
        self.assertFalse(builder.restore_torch_checkpoint(self.root, self.output))


if __name__ == '__main__':
    unittest.main()
