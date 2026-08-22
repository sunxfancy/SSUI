import os
import unittest

import yaml

from server.extensions import Extension, ExtensionServerConfig, ExtensionWebUIConfig


class TestExtensionConfigs(unittest.TestCase):
    """校验所有扩展的 ssextension.yaml 都能被 Extension 模型正确解析。"""

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
