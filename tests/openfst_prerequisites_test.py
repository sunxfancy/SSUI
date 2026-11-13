"""Guard the source SDK's integrity boundary without downloading/building it."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("openfst_prerequisites", ROOT / "dependencies/prepare_openfst.py")
openfst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(openfst)


class TestOpenFstSourceIntegrity(unittest.TestCase):
    def test_checksum_failure_stops_before_extracting_or_building(self):
        # This boundary test needs neither native tools nor filesystem access.
        with patch.object(tempfile, "TemporaryDirectory") as work, \
                patch.object(Path, "read_bytes", return_value=b"not the pinned source"), \
                patch.object(Path, "is_file", return_value=False), \
                patch.object(Path, "mkdir"), \
                patch.object(openfst.platform, "machine", return_value="aarch64"), \
                patch.object(openfst.shutil, "which", return_value="/usr/bin/c++"), \
                patch.object(openfst.tarfile, "open") as extract, \
                patch.object(openfst.subprocess, "run") as run:
            work.return_value.__enter__.return_value = str(ROOT / "unused-build-context")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                openfst.build(ROOT / "unused-sdk", archive=ROOT / "unused-source.tar.gz")
            extract.assert_not_called()
            run.assert_not_called()

    def test_plain_http_is_rejected_without_network_access(self):
        with patch.object(openfst.urllib.request, "build_opener") as network:
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                openfst.fetch_archive("http://example.com/source.tar.gz", Path("unused"))
            network.assert_not_called()

    def test_access_refusal_propagates_without_retry_or_fallback(self):
        network = Mock()
        network.open.side_effect = urllib.error.HTTPError(openfst.SOURCE_URL, 403, "Forbidden", None, None)
        with patch.object(openfst.urllib.request, "build_opener", return_value=network):
            with self.assertRaises(urllib.error.HTTPError):
                openfst.fetch_archive(openfst.SOURCE_URL, Path("unused"))
            network.open.assert_called_once_with(openfst.SOURCE_URL, timeout=120)

    def test_insecure_redirect_is_rejected_before_following(self):
        network = Mock()
        network.open.side_effect = urllib.error.HTTPError(openfst.SOURCE_URL, 403, "Forbidden", None, None)
        with patch.object(openfst.urllib.request, "build_opener", return_value=network) as create:
            with self.assertRaises(urllib.error.HTTPError):
                openfst.fetch_archive(openfst.SOURCE_URL, Path("unused"))
            handler = create.call_args.args[0]
            with self.assertRaisesRegex(RuntimeError, "non-HTTPS"):
                handler.redirect_request(None, None, 302, "Redirect", {}, "http://example.com/source.tar.gz")
