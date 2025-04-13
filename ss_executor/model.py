import uuid
import time
from enum import Enum
from typing import Annotated, Dict, Any, Literal, Optional, List, Union
from pydantic import BaseModel, Field, TypeAdapter

class ExecutorRegister(BaseModel):
    type: Literal["executor_register"] = Field(default="executor_register")
    executor_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    host: str = Field(description="The host of the executor")
    port: int = Field(description="The port of the executor")
    max_tasks: int = Field(default=1, description="The maximum number of tasks the executor can handle")
    capabilities: List[str] = Field(default=[], description="The capabilities of the executor")

class RegisterResponse(BaseModel):
    type: Literal["register_response"] = Field(default="register_response")
    status: str = Field(description="The status of the registration")
    message: str = Field(description="The message of the registration")

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class UpdateStatus(BaseModel):
    type: Literal["update_status"] = Field(default="update_status")
    task_id: str = Field(description="The id of the task")
    status: TaskStatus = Field(description="The status of the task")


class Task(BaseModel):
    type: Literal["task"] = Field(default="task")
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    script: str = Field(description="The script path to be executed")
    callable: str = Field(description="The callable to be executed")
    params: Dict[str, Any] = Field(default_factory=dict, description="The parameters to be passed to the callable")
    details: Dict[str, Any] = Field(default_factory=dict, description="The details of the task")
    is_prepare: bool = Field(default=False, description="Whether the task is prepare-execution")
    
    use_sandbox: bool = Field(default=True, description="Whether to use a sandbox")
    timeout: int = Field(default=300, description="The timeout for the task")
    priority: int = Field(default=0, description="The priority of the task")
    
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="The status of the task")
    started_at: Optional[str] = Field(default=None, description="The time the task was started")
    completed_at: Optional[str] = Field(default=None, description="The time the task was completed")
    result: Optional[Any] = Field(default=None, description="The result of the task")
    error: Optional[str] = Field(default=None, description="The error of the task")
    executor_id: Optional[str] = Field(default=None, description="The id of the executor that is running the task")
    

    class Config:
        arbitrary_types_allowed = True

class TaskResult(BaseModel):
    type: Literal["task_result"] = Field(default="task_result")
    task_id: str = Field(description="The id of the task")
    status: TaskStatus = Field(description="The status of the task")
    result: Optional[Any] = Field(default=None, description="The result of the task")
    error: Optional[str] = Field(default=None, description="The error of the task")

ExeMessage = TypeAdapter(Annotated[Union[ExecutorRegister, RegisterResponse, UpdateStatus, Task, TaskResult], Field(discriminator="type")])


class ExecutorInfo:
    def __init__(
        self,
        executor_id: str,
        host: str,
        port: int,
        max_tasks: int = 1,
        capabilities: Optional[List[str]] = None
    ):
        self.executor_id = executor_id
        self.host = host
        self.port = port
        self.max_tasks = max_tasks
        self.capabilities = capabilities or []
        self.current_tasks = 0
        self.last_heartbeat = time.time()
        self.is_active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executor_id": self.executor_id,
            "host": self.host,
            "port": self.port,
            "max_tasks": self.max_tasks,
            "capabilities": self.capabilities,
            "current_tasks": self.current_tasks,
            "last_heartbeat": self.last_heartbeat,
            "is_active": self.is_active
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutorInfo':
        executor = cls(
            executor_id=data["executor_id"],
            host=data["host"],
            port=data["port"],
            max_tasks=data.get("max_tasks", 1),
            capabilities=data.get("capabilities")
        )
        executor.current_tasks = data.get("current_tasks", 0)
        executor.last_heartbeat = data.get("last_heartbeat", time.time())
        executor.is_active = data.get("is_active", True)
        return executor


# 保留原有的ModelLoader类
class ModelLoader:
    def __init__(self):
        pass

    def load(self, model_path: str):
        pass