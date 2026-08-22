import asyncio
import os
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def _scheduler_task_to_dict(task) -> Dict[str, Any]:
    """把 ss_executor.Task 映射为统一的队列任务格式。"""
    status_map = {
        "pending": "waiting",
        "running": "processing",
        "completed": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    status = getattr(task, "status", None)
    status_value = status.value if hasattr(status, "value") else str(status or "pending")

    def to_timestamp(value) -> float:
        if not value:
            return 0.0
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    return {
        "id": task.task_id,
        "kind": "generation",
        "name": f"{task.callable} · {os.path.basename(task.script)}",
        "status": status_map.get(status_value, status_value),
        "progress": 100 if status_value == "completed" else 0,
        "createdAt": to_timestamp(task.started_at) or to_timestamp(task.completed_at) or time.time(),
        "error": task.error,
        "meta": {"script": task.script, "callable": task.callable},
    }


async def _start_download(
    request: Request,
    record_id: str,
    kind: str,
    name: str,
    url: Optional[str],
    repo_id: Optional[str],
) -> str:
    """创建一个下载任务并后台执行，返回 request_uuid。"""
    task_service = request.app.state.task_service
    model_service = request.app.state.model_service
    websocket_service = request.app.state.websocket_service
    resources_dir = request.app.state.resources_dir

    request_uuid = str(uuid.uuid4())
    local_dir = os.path.join(resources_dir, "downloads", record_id)
    os.makedirs(local_dir, exist_ok=True)
    loop = asyncio.get_running_loop()

    async def broadcast_task(rid: str) -> None:
        record = task_service.get(rid)
        if record is not None:
            await websocket_service.broadcast({"type": "task_update", "task": record.to_dict()})

    def progress_callback(
        client_id: str,
        request_uuid: str,
        callback_data: Dict[str, Any],
    ) -> None:
        progress_data = callback_data.get("download_progress") or callback_data.get("download_error")
        error = callback_data.get("download_error")
        if isinstance(progress_data, dict):
            progress = round(float(progress_data.get("progress") or 0))
            task_service.update(
                record_id,
                progress=progress,
                status="processing",
                error=str(error) if error else None,
            )
            loop.call_soon_threadsafe(
                asyncio.create_task, broadcast_task(record_id)
            )
        websocket_service.send_callback(client_id, request_uuid, callback_data)

    def hf_progress_callback(
        client_id: str,
        request_uuid: str,
        callback_name: str,
        callback_data: Dict[str, Any],
    ) -> None:
        progress_callback(client_id, request_uuid, {callback_name: callback_data})

    def finish_callback(
        client_id: str,
        request_uuid: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra = extra_data or {}
        error = extra.get("error")
        task_service.update(
            record_id,
            status="failed" if error else "completed",
            progress=0 if error else 100,
            error=str(error) if error else None,
        )
        loop.call_soon_threadsafe(
            asyncio.create_task, broadcast_task(record_id)
        )
        websocket_service.send_finish(client_id, request_uuid, extra)

    await _notify_task_started(task_service, websocket_service, record_id)

    if url and url.startswith(("http://", "https://")):
        await model_service.download_file(
            url=url,
            local_dir=local_dir,
            client_id="task",
            request_uuid=request_uuid,
            callback=progress_callback,
            finish_callback=finish_callback,
        )
    elif repo_id:
        if "::" in repo_id:
            # starter model 来源格式：repo::path —— 拆分为仓库与单文件下载
            hf_repo, hf_path = repo_id.split("::", 1)
            await model_service.hf_file_download(
                repo_id=hf_repo,
                filename=hf_path,
                local_dir=local_dir,
                client_id="task",
                request_uuid=request_uuid,
                callback=hf_progress_callback,
                finish_callback=finish_callback,
            )
        else:
            await model_service.hf_download(
                repo_id=repo_id,
                local_dir=local_dir,
                client_id="task",
                request_uuid=request_uuid,
                callback=hf_progress_callback,
                finish_callback=finish_callback,
            )
    else:
        task_service.update(record_id, status="failed", error="url 或 repo_id 必须提供其一")
    return request_uuid


async def _notify_task_started(task_service, websocket_service, record_id: str) -> None:
    record = task_service.get(record_id)
    if record is not None:
        await websocket_service.broadcast({"type": "task_update", "task": record.to_dict()})


@router.get("/api/tasks")
async def list_tasks(
    request: Request,
    kind: Optional[str] = None,
    status: Optional[str] = None,
):
    """列出任务：下载任务来自 TaskService，生图任务来自执行器调度器。"""
    task_service = request.app.state.task_service
    scheduler = request.app.state.scheduler

    items = [r.to_dict() for r in task_service.list(kind=kind, status=status)]
    if kind is None or kind == "generation":
        scheduler_tasks = getattr(scheduler, "tasks", {}) or {}
        for task in scheduler_tasks.values():
            item = _scheduler_task_to_dict(task)
            if status and item["status"] != status:
                continue
            items.append(item)
    return {"items": items}


@router.post("/api/tasks/download")
async def create_download_task(
    request: Request,
    kind: str = Body("url", embed=True),
    name: str = Body(..., embed=True),
    url: Optional[str] = Body(None, embed=True),
    repo_id: Optional[str] = Body(None, embed=True),
):
    """创建下载任务并后台执行（支持 HTTP(S) 直链与 HuggingFace 仓库）。"""
    task_service = request.app.state.task_service
    record = task_service.add("download", name, {"kind": kind, "url": url, "repo_id": repo_id})
    request_uuid = await _start_download(request, record.id, kind, name, url, repo_id)
    return {
        "type": "start",
        "task_id": record.id,
        "request_uuid": request_uuid,
    }


@router.delete("/api/tasks/{task_id}")
async def remove_task(request: Request, task_id: str):
    """移除任务：优先移除下载任务，其次移除调度器中已结束的生图任务。"""
    task_service = request.app.state.task_service
    scheduler = request.app.state.scheduler
    removed = task_service.remove(task_id)
    if not removed:
        remove_method = getattr(scheduler, "remove_task", None)
        if remove_method is not None:
            removed = remove_method(task_id)
    return {"success": removed}


@router.post("/api/tasks/clear")
async def clear_completed_tasks(request: Request):
    """清除所有已结束任务（下载任务 + 生图任务）。"""
    task_service = request.app.state.task_service
    scheduler = request.app.state.scheduler
    count = task_service.clear_completed()
    scheduler_removed = 0
    clear_method = getattr(scheduler, "clear_completed_tasks", None)
    if clear_method is not None:
        scheduler_removed = clear_method()
    return {"success": True, "removed": count, "scheduler_removed": scheduler_removed}


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(request: Request, task_id: str):
    task_service = request.app.state.task_service
    websocket_service = request.app.state.websocket_service
    cancelled = task_service.cancel(task_id)
    if cancelled:
        record = task_service.get(task_id)
        if record is not None:
            await websocket_service.broadcast({"type": "task_update", "task": record.to_dict()})
    return {"success": cancelled}


@router.post("/api/tasks/{task_id}/retry")
async def retry_task(request: Request, task_id: str):
    """重试失败的下载任务：按原 meta 重新创建任务。"""
    task_service = request.app.state.task_service
    record = task_service.get(task_id)
    if record is None:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    meta = record.meta or {}
    new_record = task_service.add("download", record.name, meta)
    await _start_download(
        request,
        new_record.id,
        meta.get("kind", "url"),
        record.name,
        meta.get("url"),
        meta.get("repo_id"),
    )
    return {"success": True, "task_id": new_record.id}
