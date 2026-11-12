import importlib.util
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest


spec = importlib.util.spec_from_file_location('ci_apt', Path(__file__).resolve().parents[1] / 'scripts/ci_apt.py')
apt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apt)

SOURCE = '''Types: deb
URIs: mirror+file:/etc/apt/apt-mirrors.txt
Suites: noble noble-updates noble-backports noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
'''


class TestCIApt(unittest.TestCase):
    def test_preserves_signed_suites_and_third_party_sources(self):
        source = SOURCE + '\nURIs: https://packages.microsoft.com/ubuntu/24.04/prod\n'
        rewritten = apt.rewrite_sources(source, apt.MIRRORS['amd64'][0])
        self.assertIn('URIs: https://mirror.math.princeton.edu/pub/ubuntu/', rewritten)
        for line in source.splitlines():
            if not line.startswith('URIs: mirror+'):
                self.assertIn(line, rewritten)
        self.assertNotIn('trusted=yes', rewritten)

    def test_legacy_sources_and_arm64_use_https(self):
        source = 'deb [arch=arm64 signed-by=/key.gpg] http://ports.ubuntu.com/ubuntu-ports noble main\n'
        rewritten = apt.rewrite_sources(source, apt.MIRRORS['arm64'][0])
        self.assertEqual(rewritten, 'deb [arch=arm64 signed-by=/key.gpg] https://mirrors.aliyun.com/ubuntu-ports/ noble main\n')
        legacy = 'deb http://azure.archive.ubuntu.com/ubuntu/ noble main\n'
        self.assertNotIn('azure.archive', apt.rewrite_sources(legacy, apt.MIRRORS['amd64'][0]))

    def exercise(self, outcomes, arch='amd64'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sources.list.d').mkdir()
            source = root / 'sources.list.d/ubuntu.sources'
            source.write_text(SOURCE)
            calls = []
            def run(command, **kwargs):
                calls.append((command, kwargs, source.read_text()))
                outcome = outcomes.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return SimpleNamespace(returncode=outcome)
            try:
                apt.prepare(root, arch, run=run)
            finally:
                self.assertIn('APT::Update::Error-Mode "any"', (root / 'apt.conf.d/80ssui-ci-network').read_text())
                self.assertTrue(all(call[1]['timeout'] == 120 for call in calls))
                self.calls = calls

    def test_success_does_not_retry(self):
        self.exercise([0])
        self.assertEqual(len(self.calls), 1)

    def test_failed_index_update_uses_independent_fallback(self):
        self.exercise([100, 0])
        self.assertEqual(len(self.calls), 2)
        self.assertIn(apt.MIRRORS['amd64'][1], self.calls[-1][2])
        self.assertIn('Signed-By:', self.calls[-1][2])

    def test_timeout_is_bounded_and_can_recover(self):
        self.exercise([subprocess.TimeoutExpired('apt-get', 120), 0])
        self.assertEqual(len(self.calls), 2)

    def test_two_failures_stop_instead_of_using_stale_indexes(self):
        with self.assertRaisesRegex(RuntimeError, 'package installation stopped'):
            self.exercise([100, 100])
        self.assertEqual(len(self.calls), 2)

    def test_arm64_fallback_keeps_ports_repository(self):
        self.exercise([100, 0], arch='arm64')
        self.assertIn(apt.MIRRORS['arm64'][0], self.calls[0][2])
        self.assertIn(apt.MIRRORS['arm64'][1], self.calls[1][2])

    def test_missing_sources_fail_before_writing_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, 'No Ubuntu package source'):
                apt.prepare(root, 'amd64')
            self.assertFalse((root / 'apt.conf.d').exists())
