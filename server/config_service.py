import json
import os
import tempfile
from threading import RLock
from typing import Any, Dict, List

from server.models import ModelInfo, Settings


class ConfigService:
    def __init__(self, settings_path: str):
        self.settings_path = settings_path
        self._lock = RLock()
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Settings:
        if not os.path.exists(self.settings_path):
            return Settings(host_web_ui=os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "frontend", "functional_ui", "dist"
            ))
        with open(self.settings_path, "r", encoding="utf-8") as f:
            return Settings.model_validate_json(f.read())
    
    def _write_settings(self, settings: Settings) -> None:
        """原子写入配置，避免进程中断留下半截 JSON 文件。"""
        settings_dir = os.path.dirname(os.path.abspath(self.settings_path))
        os.makedirs(settings_dir, exist_ok=True)
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=settings_dir,
                prefix=".ssui_config_",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = temp_file.name
                json.dump(
                    settings.model_dump(mode="json"),
                    temp_file,
                    indent=4,
                    ensure_ascii=False,
                )
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, self.settings_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def save_settings(self) -> None:
        with self._lock:
            self._write_settings(self.settings)
    
    def get_settings(self) -> Settings:
        return self.settings

    def get_config(self) -> Dict[str, Any]:
        """返回可序列化的完整配置（供前端读取）。"""
        with self._lock:
            return self.settings.model_dump(mode="json")

    def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(config, dict):
            raise ValueError("Config must be a JSON object")

        with self._lock:
            current = self.settings.model_dump()
            allowed_fields = set(Settings.model_fields)
            for key, value in config.items():
                if key not in allowed_fields:
                    continue
                if key == "ui":
                    if not isinstance(value, dict):
                        raise ValueError("ui must be a JSON object")
                    current["ui"] = {
                        **self.settings.ui.model_dump(),
                        **value,
                    }
                else:
                    current[key] = value

            # 对整个结果重新校验，避免 model_copy(update=...) 绕过字段校验。
            updated = Settings.model_validate(current)
            self._write_settings(updated)
            self.settings = updated
            return self.settings.model_dump(mode="json")
    
    def get_installed_models(self) -> List[ModelInfo]:
        return self.settings.installed_models
    
    def add_installed_model(self, model: ModelInfo) -> None:
        with self._lock:
            updated = self.settings.model_copy(deep=True)
            updated.installed_models.append(model)
            self._write_settings(updated)
            self.settings = updated
