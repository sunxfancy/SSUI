import os
import json
from typing import Dict, Any, List, Tuple
from server.models import Settings, UiSettings, ModelInfo
from server.opener_service import FileOpenerManager

class ConfigService:
    def __init__(self, settings_path: str):
        self.settings_path = settings_path
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Settings:
        if not os.path.exists(self.settings_path):
            return Settings(host_web_ui=os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "frontend", "functional_ui", "dist"
            ))
        with open(self.settings_path, "r", encoding="utf-8") as f:
            return Settings.model_validate_json(f.read())
    
    def save_settings(self) -> None:
        if not os.path.exists(os.path.dirname(self.settings_path)):
            os.makedirs(os.path.dirname(self.settings_path))
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings.model_dump(), f, indent=4, ensure_ascii=False)
    
    def get_settings(self) -> Settings:
        return self.settings

    def get_config(self) -> Dict[str, Any]:
        """返回可序列化的完整配置（供前端读取）。"""
        return self.settings.model_dump(mode="json")

    def update_config(self, config: Dict[str, Any]) -> Dict[str, str]:
        if not isinstance(config, dict):
            raise ValueError("Config must be a JSON object")

        updated = self.settings.model_copy(deep=True)
        for key, value in config.items():
            if key == "ui" and isinstance(value, dict):
                merged = UiSettings.model_validate(
                    {**updated.ui.model_dump(), **value}
                )
                updated = updated.model_copy(update={"ui": merged})
            elif hasattr(updated, key):
                updated = updated.model_copy(update={key: value})
        self.settings = updated
        self.save_settings()
        return {"message": "Config updated"}
    
    def get_installed_models(self) -> List[ModelInfo]:
        return self.settings.installed_models
    
    def add_installed_model(self, model: ModelInfo) -> None:
        self.settings.installed_models.append(model)
        self.save_settings() 
