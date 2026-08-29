from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Literal, Optional

# 配置相关模型
class ModelInfo(BaseModel):
    path: str
    name: str
    description: str
    base_model: str
    tags: List[str]


class UiSettings(BaseModel):
    """Functional UI 用户可配置项。

    这些字段由前端 Functional UI 读写并持久化到 ``ssui_config.json``，
    目前包含主题、面板行为与外部服务相关配置。
    """

    theme: Literal["light", "dark", "system"] = "system"
    auto_open_details: bool = True
    external_code_editor: str = ""
    civitai_token: str = ""


class Settings(BaseModel):
    host_web_ui: str
    additional_model_dirs: List[str] = Field(default_factory=list)
    installed_models: List[ModelInfo] = Field(default_factory=list)
    resources_dir: Optional[str] = None
    ui: UiSettings = Field(default_factory=UiSettings)

class ScanModelsRequest(BaseModel):
    scan_dir: str = Field(description="The directory to scan for models")

# 模型相关模型
class ModelConfig(BaseModel):
    path: str
    name: str
    description: Optional[str] = None
    base_model: Optional[str] = None
    tags: List[str] = []

class ModelScanResult(BaseModel):
    path: str
    name: str


class ScriptFunctionInfo(BaseModel):
    params: Dict[str, str]
    returns: List[str]

# WebSocket相关模型
class WebSocketMessage(BaseModel):
    type: Literal["uuid", "callback", "finish"]

class WebSocketUUID(WebSocketMessage):
    type: Literal["uuid"]
    uuid: str

class WebSocketCallback(WebSocketMessage):
    type: Literal["callback"]
    request_uuid: str
    model_config = ConfigDict(extra="allow")

class WebSocketFinish(WebSocketMessage):
    type: Literal["finish"]
    request_uuid: str
    model_config = ConfigDict(extra="allow")
