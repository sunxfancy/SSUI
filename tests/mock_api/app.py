import asyncio
import base64
from copy import deepcopy
from typing import Any, Dict

from fastapi import Body, FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .models import (
    ExecuteImageResult,
    RecordedRequest,
    ScriptMeta,
    TaskList,
    TaskMutation,
    TaskUpdate,
    UploadResult,
    WebSocketUuid,
)
from .scenarios import initial_state


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

app = FastAPI(title="SSUI frontend test mock", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.test_state = initial_state()


async def record(request: Request, body: Any = None) -> None:
    app.state.test_state["requests"].append(
        RecordedRequest(
            method=request.method,
            path=request.url.path,
            query=dict(request.query_params),
            body=body,
        ).model_dump()
    )


@app.get("/")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.put("/__test__/scenario")
async def set_scenario(payload: Dict[str, str]) -> Dict[str, str]:
    name = payload.get("name", "happy-path")
    app.state.test_state = initial_state(name)
    return {"name": name}


@app.get("/__test__/requests")
async def get_requests() -> Dict[str, Any]:
    return {"items": app.state.test_state["requests"]}


@app.get("/config/")
async def get_config(request: Request) -> Dict[str, Any]:
    await record(request)
    return deepcopy(app.state.test_state["config"])


@app.post("/config/")
async def save_config(request: Request, payload: Dict[str, Any]) -> Dict[str, str]:
    await record(request, payload)
    app.state.test_state["config"].setdefault("ui", {}).update(payload.get("ui", {}))
    return {"status": "success"}


@app.get("/api/ui_state_load")
async def ui_state_load(request: Request, script_path: str, view: str = ""):
    await record(request)
    return deepcopy(app.state.test_state.setdefault("ui_states", {}).get((script_path, view), {}))


@app.post("/api/ui_state_store")
async def ui_state_store(request: Request, script_path: str, view: str = "", payload: Dict[str, Any] = Body(...)):
    await record(request, payload)
    app.state.test_state.setdefault("ui_states", {})[(script_path, view)] = deepcopy(payload["state_data"])
    return {"success": True}


@app.post("/api/ui_state_asset")
async def ui_state_asset(request: Request, script_path: str, file: UploadFile = File(...)):
    await record(request, {"filename": file.filename, "content_type": file.content_type})
    await file.close()
    return {"success": True, "path": "/fixtures/canvas-asset.png"}


@app.get("/api/script", response_model=ScriptMeta)
async def script(request: Request, script_path: str):
    await record(request)
    if app.state.test_state["scenario"] == "api-500":
        return JSONResponse({"error": {"code": "SCRIPT_FAILED", "message": "mock failure"}}, status_code=500)
    return {
        "root_path": "/fixtures",
        "functions": {
            "generate": {
                "params": {"image": "ssui.base.Image"},
                "returns": ["ssui.base.Image"],
            }
        },
    }


@app.post("/api/prepare")
async def prepare(request: Request, script_path: str, callable: str):
    payload = await request.json()
    await record(request, payload)
    return {
        "Generation": {
            "steps": {
                "controller": "Slider",
                "args": {"min": 1, "max": 50, "step": 1},
                "default": 20,
            },
            "seed": {"controller": "Random", "args": {"default": 42}, "default": 42},
        }
    }


@app.post("/files/upload", response_model=UploadResult)
async def upload(request: Request, script_path: str, file: UploadFile = File(...)):
    contents = await file.read()
    await record(
        request,
        {"filename": file.filename, "content_type": file.content_type, "size": len(contents)},
    )
    if app.state.test_state["scenario"] == "upload-rejected":
        return UploadResult(success=False, error="mock upload rejected")
    return UploadResult(success=True, path="/fixtures/uploaded.png")


@app.get("/files/{file_type}")
async def list_files(request: Request, file_type: str, script_path: str):
    await record(request)
    return [f"/fixtures/input.{file_type}"]


@app.post("/api/execute", response_model=list[ExecuteImageResult])
async def execute(request: Request, script_path: str, callable: str):
    payload = await request.json()
    await record(request, payload)
    if app.state.test_state["scenario"] == "generation-fails":
        return JSONResponse(
            {"error": {"code": "EXECUTION_FAILED", "message": "Mock generation failed", "retryable": True}},
            status_code=500,
        )
    return [{"path": "/fixtures/generated.png"}]


@app.get("/file")
async def get_file(request: Request, path: str):
    await record(request)
    return Response(PNG_1X1, media_type="image/png")


@app.get("/api/tasks", response_model=TaskList)
async def list_tasks(request: Request):
    await record(request)
    return {"items": deepcopy(app.state.test_state["tasks"])}


@app.post("/api/tasks/{task_id}/cancel", response_model=TaskMutation)
async def cancel_task(request: Request, task_id: str):
    await record(request)
    for task in app.state.test_state["tasks"]:
        if task["id"] == task_id:
            task.update(status="cancelled", progress=0)
            return {"success": True}
    return {"success": False}


@app.delete("/api/tasks/{task_id}", response_model=TaskMutation)
async def remove_task(request: Request, task_id: str):
    await record(request)
    before = len(app.state.test_state["tasks"])
    app.state.test_state["tasks"] = [task for task in app.state.test_state["tasks"] if task["id"] != task_id]
    return {"success": len(app.state.test_state["tasks"]) != before}


@app.post("/api/tasks/clear", response_model=TaskMutation)
async def clear_tasks(request: Request):
    await record(request)
    app.state.test_state["tasks"] = [
        task for task in app.state.test_state["tasks"] if task["status"] not in {"completed", "failed", "cancelled"}
    ]
    return {"success": True}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json(WebSocketUuid(type="uuid", uuid="client-1").model_dump())
        if app.state.test_state["scenario"] == "task-lifecycle" and app.state.test_state["tasks"]:
            await asyncio.sleep(0.1)
            task = app.state.test_state["tasks"][0]
            task.update(status="processing", progress=50)
            await websocket.send_json(TaskUpdate(type="task_update", task=task).model_dump())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
