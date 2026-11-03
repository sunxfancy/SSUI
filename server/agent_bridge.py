"""Live, schema-validated command routing to connected SSUI windows/editors."""
import asyncio
from ipaddress import ip_address
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from jsonschema import Draft202012Validator, ValidationError, SchemaError

router = APIRouter(prefix="/api/agent", tags=["Agent live UI"])


def check_local(connection):
    host = connection.client.host if connection.client else ""
    try:
        local = ip_address(host).is_loopback
    except ValueError:
        local = host in ("localhost", "testclient", "testserver")
    origin = connection.headers.get("origin")
    if not local or (origin and urlsplit(origin).hostname not in
                     ("localhost", "127.0.0.1", "::1", "tauri.localhost")):
        raise HTTPException(403, "Agent bridge accepts trusted local SSUI clients only")


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=128)
    arguments: dict = Field(default_factory=dict)
    timeout: float = Field(default=60, gt=0, le=600)


class AgentBridge:
    def __init__(self):
        self.targets = {}
        self.pending = {}

    async def call(self, target_id, body):
        target = self.targets.get(target_id)
        if target is None:
            raise HTTPException(404, "UI target disconnected; refresh ssui_ui_targets")
        command = next((c for c in target["commands"] if c["name"] == body.command), None)
        if command is None:
            raise HTTPException(404, "Unknown UI command; inspect target commands first")
        try:
            Draft202012Validator(command["inputSchema"]).validate(body.arguments)
        except ValidationError as exc:
            raise HTTPException(422, exc.message) from exc
        request_id = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = (target_id, future)
        try:
            await target["socket"].send_json({"type": "call", "id": request_id,
                                              "command": body.command, "arguments": body.arguments})
            result = await asyncio.wait_for(future, body.timeout)
            if result.get("error"):
                raise HTTPException(409, result["error"])
            return {"result": result.get("result")}
        except asyncio.TimeoutError as exc:
            raise HTTPException(504, "UI command timed out; inspect state before retrying") from exc
        except (WebSocketDisconnect, RuntimeError, OSError) as exc:
            raise HTTPException(409, "UI target disconnected during command; refresh targets") from exc
        finally:
            self.pending.pop(request_id, None)

    def disconnect(self, target_id):
        self.targets.pop(target_id, None)
        for owner, future in self.pending.values():
            if owner == target_id and not future.done():
                future.set_result({"error": "UI target disconnected during command"})


def bridge(app):
    # Lazy creation also supports the model-free contract app.
    if not hasattr(app.state, "agent_bridge"):
        app.state.agent_bridge = AgentBridge()
    return app.state.agent_bridge


@router.get("/targets")
async def targets(request: Request):
    check_local(request)
    return {"items": [{"id": key, "label": value["label"], "commands": value["commands"]}
                      for key, value in bridge(request.app).targets.items()]}


@router.post("/targets/{target_id}/call")
async def call(target_id: str, body: CommandRequest, request: Request):
    check_local(request)
    return await bridge(request.app).call(target_id, body)


@router.websocket("/connect")
async def connect(socket: WebSocket):
    try:
        check_local(socket)
    except HTTPException:
        await socket.close(code=1008)
        return
    await socket.accept()
    target_id = str(uuid4())
    service = bridge(socket.app)
    try:
        registration = await asyncio.wait_for(socket.receive_json(), 10)
        commands = registration.get("commands", [])
        if not isinstance(commands, list) or not 1 <= len(commands) <= 256:
            raise ValueError("Invalid command catalog")
        names = set()
        for command in commands:
            name = command["name"]
            if not isinstance(name, str) or not name or len(name) > 128 or name in names:
                raise ValueError("Invalid command name")
            names.add(name)
            Draft202012Validator.check_schema(command["inputSchema"])
        service.targets[target_id] = {"label": str(registration.get("label", "SSUI"))[:512],
                                      "commands": commands, "socket": socket}
        await socket.send_json({"type": "ready", "targetId": target_id})
        while True:
            message = await socket.receive_json()
            pending = service.pending.get(message.get("id"))
            if pending and pending[0] == target_id and not pending[1].done():
                pending[1].set_result(message)
    except (WebSocketDisconnect, ValueError, KeyError, TypeError, SchemaError, asyncio.TimeoutError):
        pass
    finally:
        service.disconnect(target_id)
        try:
            await socket.close()
        except RuntimeError:
            pass


def create_app():
    """Independent relay remains available while native server/executor restart."""
    app = FastAPI(title="SSUI local desktop agent relay")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:1420", "http://tauri.localhost", "tauri://localhost"],
                       allow_methods=["GET", "POST"], allow_headers=["content-type"])
    app.include_router(router)
    return app
