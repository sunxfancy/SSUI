from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Literal, Optional

# 配置相关模型
class ModelInfo(BaseModel):
    path: str
    name: str
    description: str
    base_model: str
    tags: List[str]

class Settings(BaseModel):
    host_web_ui: str
    additional_model_dirs: List[str] = []
    installed_models: List[ModelInfo] = []
    resources_dir: Optional[str] = None

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