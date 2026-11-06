import os
import sys
import importlib
from unittest.mock import patch
import unittest
import tempfile
from pathlib import Path

from fastapi import FastAPI

import yaml

from server.extensions import Extension, ExtensionManager, ExtensionServerConfig, ExtensionWebUIConfig


class TestExtensionConfigs(unittest.TestCase):
    """校验所有扩展的 ssextension.yaml 都能被 Extension 模型正确解析。"""

    def test_sdk_only_extension_loads_without_http_router(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "extension.py").write_text("SDK_VERSION = '1'\n", encoding="utf-8")
            manager = ExtensionManager(directory)
            manager.extensions["SDK"] = Extension(name="SDK", path=directory, version="1")
            manager.loadPythonScripts(FastAPI())
            self.assertIsNotNone(manager.modules["SDK"])

    def test_bundled_runtime_precedes_installed_package(self):
        from backend.extension_paths import add_extension_path

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "site-packages"
            extension = root / "extension"
            vendor = extension / "vendor"
            installed.mkdir()
            vendor.mkdir(parents=True)
            name = "ssui_runtime_precedence_fixture"
            (installed / (name + ".py")).write_text("source = 'installed'\n")
            (vendor / (name + ".py")).write_text("source = 'bundled'\n")
            with patch.object(sys, "path", [str(installed), *sys.path]):
                add_extension_path(str(extension))
                try:
                    self.assertEqual(importlib.import_module(name).source, "bundled")
                    add_extension_path(str(extension))
                    self.assertEqual(sys.path.count(str(vendor)), 1)
                finally:
                    sys.modules.pop(name, None)

    def test_all_extension_yamls_are_valid(self):
        extensions_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "extensions")
        )
        found = 0
        for entry in sorted(os.listdir(extensions_dir)):
            extension_dir = os.path.join(extensions_dir, entry)
            yaml_path = os.path.join(extension_dir, "ssextension.yaml")
            if not os.path.isfile(yaml_path):
                continue
            found += 1
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            extension = Extension(
                name=data.get("name", entry),
                path=extension_dir,
                version=data["version"],
                server=ExtensionServerConfig(**data.get("server", {})),
                web_ui=ExtensionWebUIConfig(**data.get("web_ui", {})),
            )
            self.assertEqual(extension.name, data.get("name", entry))
            self.assertIsInstance(extension.server.packages, list)

        self.assertGreaterEqual(found, 7, "expected at least 7 extensions with yaml")


if __name__ == "__main__":
    unittest.main()
