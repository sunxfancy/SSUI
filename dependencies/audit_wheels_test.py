import unittest
from unittest.mock import patch

from packaging.tags import compatible_tags, cpython_tags

from audit_wheels import audit, wheel_matches, audit_inputs, audit_failed


class WheelAuditTests(unittest.TestCase):
    def setUp(self):
        self.tags = set(cpython_tags((3, 12), platforms=['win_arm64'])) | set(compatible_tags((3, 12), interpreter='cp312', platforms=['win_arm64']))

    def test_lock_indexes_are_used(self):
        lines, indexes = audit_inputs('# generated\ndemo==1\n --extra-index-url https://example.org/simple/\n--index-url=https://pypi.org/simple\n')
        self.assertEqual(lines, ['demo==1'])
        self.assertEqual(indexes, ['https://example.org/simple/', 'https://pypi.org/simple'])

    def test_strict_gate_rejects_missing_or_wrong_architecture(self):
        for status in ('source-only', 'incompatible-direct-url', 'no-compatible-distribution', 'metadata-error'):
            self.assertTrue(audit_failed([{'status': status}], strict=True))
        self.assertFalse(audit_failed([{'status': 'wheel'}, {'status': 'direct-wheel'}], strict=True))

    def test_native_and_universal_tags_do_not_accept_x64(self):
        self.assertTrue(wheel_matches('demo-1.0-cp312-cp312-win_arm64.whl', self.tags))
        self.assertTrue(wheel_matches('demo-1.0-py3-none-any.whl', self.tags))
        self.assertTrue(wheel_matches('demo-1.0-cp39-abi3-win_arm64.whl', self.tags))
        self.assertFalse(wheel_matches('demo-1.0-cp312-cp312-win_amd64.whl', self.tags))
        self.assertFalse(wheel_matches('demo-1.0-cp313-cp313-win_arm64.whl', self.tags))

    def test_explicit_prerelease_pin_is_audited(self):
        metadata = {'releases': {'0.66b1': [{'filename': 'demo-0.66b1-py3-none-any.whl', 'packagetype': 'bdist_wheel', 'requires_python': '>=3.9'}]}}
        with patch('audit_wheels.read_metadata', return_value=metadata):
            self.assertEqual(audit('demo==0.66b1', self.tags, '3.12.15')['status'], 'wheel')

    def test_source_only_is_not_reported_as_native_support(self):
        metadata = {'releases': {'1.0': [{'filename': 'demo-1.0.tar.gz', 'packagetype': 'sdist'}]}}
        with patch('audit_wheels.read_metadata', return_value=metadata):
            self.assertEqual(audit('demo>=1.0', self.tags, '3.12.15')['status'], 'source-only')

    def test_requires_python_and_yanked_releases_are_respected(self):
        metadata = {'releases': {'1.0': [{'filename': 'demo-1.0-py3-none-any.whl', 'packagetype': 'bdist_wheel', 'requires_python': '>=3.13'}], '2.0': [{'filename': 'demo-2.0-py3-none-any.whl', 'packagetype': 'bdist_wheel', 'yanked': True}]}}
        with patch('audit_wheels.read_metadata', return_value=metadata):
            self.assertEqual(audit('demo>=1.0', self.tags, '3.12.15')['status'], 'no-compatible-distribution')


if __name__ == '__main__':
    unittest.main()
