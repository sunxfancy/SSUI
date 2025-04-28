import os
import json
from typing import Dict, Any, List, Tuple
from server.models import Settings, ModelInfo
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
        return Settings.model_validate_json(open(self.settings_path, "r").read())
    
    def save_settings(self) -> None:
        if not os.path.exists(os.path.dirname(self.settings_path)):
            os.makedirs(os.path.dirname(self.settings_path))
        with open(self.settings_path, "w") as f:
            json.dump(self.settings.model_dump(), f, indent=4, ensure_ascii=False)
    
    def get_settings(self) -> Settings:
        return self.settings
    
    def update_config(self, config: Dict[str, Any]) -> Dict[str, str]:
        for key, value in config.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save_settings()
        return {"message": "Config updated"}
    
    def get_installed_models(self) -> List[ModelInfo]:
        return self.settings.installed_models
    
    def add_installed_model(self, model: ModelInfo) -> None:
        self.settings.installed_models.append(model)
        self.save_settings() 