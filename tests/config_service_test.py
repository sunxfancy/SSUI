import os
import tempfile
import unittest

from server.config_service import ConfigService


class TestConfigService(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.settings_path = os.path.join(self.tmp_dir, "ssui_config.json")
        self.service = ConfigService(self.settings_path)

    def test_default_ui_settings(self):
        settings = self.service.get_settings()
        self.assertEqual(settings.ui.theme, "system")
        self.assertTrue(settings.ui.auto_open_details)

    def test_get_config(self):
        config = self.service.get_config()
        self.assertEqual(config["ui"]["theme"], "system")
        self.assertIn("host_web_ui", config)

    def test_update_ui_config_persists(self):
        result = self.service.update_config(
            {"ui": {"theme": "dark", "auto_open_details": False}}
        )
        self.assertIn("message", result)

        settings = self.service.get_settings()
        self.assertEqual(settings.ui.theme, "dark")
        self.assertFalse(settings.ui.auto_open_details)

        # 重新加载后配置仍然存在
        reloaded = ConfigService(self.settings_path)
        self.assertEqual(reloaded.get_settings().ui.theme, "dark")
        self.assertFalse(reloaded.get_settings().ui.auto_open_details)

    def test_update_ui_merges_without_losing_fields(self):
        self.service.update_config({"ui": {"theme": "light"}})
        settings = self.service.get_settings()
        self.assertEqual(settings.ui.theme, "light")
        self.assertTrue(settings.ui.auto_open_details)
        self.assertEqual(settings.ui.civitai_token, "")
        self.assertEqual(settings.ui.external_code_editor, "")

    def test_update_unknown_keys_are_ignored(self):
        result = self.service.update_config(
            {"ui": {"theme": "dark"}, "not_a_setting": 42}
        )
        self.assertIn("message", result)
        self.assertEqual(self.service.get_settings().ui.theme, "dark")

    def test_update_invalid_theme_raises(self):
        with self.assertRaises(Exception):
            self.service.update_config({"ui": {"theme": "neon"}})


if __name__ == "__main__":
    unittest.main()
