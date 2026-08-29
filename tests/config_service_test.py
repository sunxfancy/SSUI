import os
import tempfile
import unittest
from unittest.mock import patch

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
        self.assertEqual(result["ui"]["theme"], "dark")
        self.assertFalse(result["ui"]["auto_open_details"])

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
        self.assertNotIn("not_a_setting", result)
        self.assertEqual(self.service.get_settings().ui.theme, "dark")

    def test_update_invalid_theme_raises(self):
        with self.assertRaises(Exception):
            self.service.update_config({"ui": {"theme": "neon"}})

    def test_update_invalid_ui_shape_raises(self):
        with self.assertRaises(ValueError):
            self.service.update_config({"ui": "dark"})

    def test_failed_write_does_not_change_in_memory_settings(self):
        with patch.object(self.service, "_write_settings", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.service.update_config({"ui": {"theme": "dark"}})
        self.assertEqual(self.service.get_settings().ui.theme, "system")

    def test_settings_instances_do_not_share_mutable_defaults(self):
        another_path = os.path.join(self.tmp_dir, "another_config.json")
        another = ConfigService(another_path)
        self.service.get_settings().additional_model_dirs.append("models")
        self.assertEqual(another.get_settings().additional_model_dirs, [])


if __name__ == "__main__":
    unittest.main()
