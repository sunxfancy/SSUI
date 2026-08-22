import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TaskRecord:
    """统一任务记录：下载任务与生图任务共用。"""

    id: str
    kind: str  # download | generation
    name: str
    status: str = "waiting"  # waiting | processing | completed | failed | cancelled
    progress: int = 0
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "createdAt": self.created_at,
            "error": self.error,
            "meta": self.meta,
        }


class TaskService:
    """线程安全的任务注册表（同步方法，便于在下载线程中直接更新）。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def add(self, kind: str, name: str, meta: Optional[Dict[str, Any]] = None) -> TaskRecord:
        record = TaskRecord(
            id=str(uuid.uuid4()),
            kind=kind,
            name=name,
            meta=meta or {},
        )
        with self._lock:
            self._tasks[record.id] = record
        return record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task_id: str, **changes: Any) -> Optional[TaskRecord]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            for key, value in changes.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            return record

    def list(self, kind: Optional[str] = None, status: Optional[str] = None) -> List[TaskRecord]:
        with self._lock:
            records = list(self._tasks.values())
        if kind:
            records = [r for r in records if r.kind == kind]
        if status:
            records = [r for r in records if r.status == status]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def remove(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return False
            if record.status in ("completed", "failed", "cancelled"):
                return False
            record.status = "cancelled"
            record.progress = 0
            return True

    def clear_completed(self) -> int:
        with self._lock:
            keys = [
                k
                for k, r in self._tasks.items()
                if r.status in ("completed", "failed", "cancelled")
            ]
            for key in keys:
                del self._tasks[key]
            return len(keys)
