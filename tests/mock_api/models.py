from typing import Any, Dict

from pydantic import BaseModel, ConfigDict

from server.models import (
    ScriptMeta,
    TaskInfo as QueueTask,
    TaskList,
    TaskMutationResult as TaskMutation,
    UploadResult,
    WebSocketTaskUpdate as TaskUpdate,
    WebSocketUUID as WebSocketUuid,
)


class ExecuteImageResult(BaseModel):
    path: str


class RecordedRequest(BaseModel):
    method: str
    path: str
    query: Dict[str, str]
    body: Any = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: Dict[str, Any]
