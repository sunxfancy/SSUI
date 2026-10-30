"""Model-free generation contract prototype. State is scoped to one server process."""
import asyncio
import hashlib
import struct
import zlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(default="brick wall", max_length=2000)
    size: int = Field(default=256, ge=32, le=512)
    seed: int = Field(default=0, ge=0, le=2147483647)


class Generate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe: str = Field(min_length=1, max_length=128)
    clientId: str = Field(min_length=1, max_length=128)
    context: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    idempotencyKey: str = Field(min_length=1, max_length=128)



class Artifact(BaseModel):
    artifactId: str
    kind: str
    mimeType: str
    url: str
    sha256: str
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Job(BaseModel):
    jobId: str
    recipe: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: int
    context: dict[str, JsonValue]
    artifacts: list[Artifact]
    error: str | None
    mock: bool


# Recipe-specific validation is separate from the transport envelope.
RECIPES = {"mock.checker@1": Inputs}

def png(inputs: Inputs) -> bytes:
    """Deterministic checker PNG, using only the standard library."""
    colors = hashlib.sha256(f"{inputs.prompt}:{inputs.seed}".encode()).digest()
    n = inputs.size
    rows = b"".join(b"\0" + b"".join(
        colors[:3] if (x // 32 + y // 32) % 2 else colors[3:6]
        for x in range(n)) for y in range(n))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


class GenerationBridge:
    def __init__(self, delay=0.3):
        self.delay = delay
        self.jobs = {}
        self.keys = {}
        self.artifacts = {}
        self.tasks = {}

    def create(self, body):
        schema = RECIPES.get(body.recipe)
        if schema is None:
            raise HTTPException(404, "Recipe not found")
        try:
            inputs = schema.model_validate(body.inputs)
        except ValidationError as exc:
            raise HTTPException(422, exc.errors(include_url=False)) from exc
        payload = body.model_dump()
        key = (body.clientId, body.idempotencyKey)
        if key in self.keys:
            job_id, original = self.keys[key]
            if original != payload:
                raise HTTPException(409, "Idempotency key already used with different inputs")
            return self.jobs[job_id]
        if len(self.jobs) >= 128:
            raise HTTPException(429, "Prototype capacity reached; restart the demo server")
        job_id = str(uuid4())
        job = dict(jobId=job_id, state="queued", progress=0, recipe=body.recipe, context=body.context, artifacts=[], error=None, mock=True)
        self.jobs[job_id] = job
        self.keys[key] = (job_id, payload)
        task = asyncio.create_task(self.run(job, inputs))
        self.tasks[job_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(job_id, None))
        return job

    async def run(self, job, inputs):
        try:
            job.update(state="running", progress=10)
            await asyncio.sleep(self.delay)
            job.update(progress=60)
            await asyncio.sleep(self.delay)
            content = png(inputs)
            artifact_id = str(uuid4())
            self.artifacts[artifact_id] = content
            job.update(state="succeeded", progress=100, artifacts=[dict(
                artifactId=artifact_id, kind="image", mimeType="image/png",
                url=f"/api/generation/v1/artifacts/{artifact_id}",
                sha256=hashlib.sha256(content).hexdigest(),
                metadata={"width": inputs.size, "height": inputs.size, "colorSpace": "sRGB"})])
        except asyncio.CancelledError:
            job.update(state="cancelled")
            raise
        except Exception:
            job.update(state="failed", error="Mock generation failed")

    def get(self, job_id):
        if job_id not in self.jobs:
            raise HTTPException(404, "Job not found")
        return self.jobs[job_id]

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


router = APIRouter(prefix="/api/generation/v1", tags=["generation prototype"])


@router.get("/capabilities")
async def capabilities():
    return {"protocol": "ssui-generation", "version": "1", "mock": True,
            "features": ["recipes", "jobs", "cancellation", "idempotency", "artifact-download"],
            "persistence": "memory", "maxJobs": 128}


@router.get("/recipes")
async def recipes():
    return {"protocolVersion": 1, "mock": True, "items": [{"id": "mock.checker@1", "name": "模拟棋盘贴图", "inputSchema": Inputs.model_json_schema(), "outputSchema": Artifact.model_json_schema()}]}


@router.post("/jobs", status_code=202, response_model=Job)
async def create_job(body: Generate, request: Request):
    return request.app.state.generation_bridge.create(body)


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str, request: Request):
    return request.app.state.generation_bridge.get(job_id)


@router.post("/jobs/{job_id}/cancel", response_model=Job)
async def cancel_job(job_id: str, request: Request):
    service = request.app.state.generation_bridge
    job = service.get(job_id)
    if job["state"] in ("queued", "running"):
        job.update(state="cancelled")
        service.tasks[job_id].cancel()
    return job


@router.get("/artifacts/{artifact_id}")
async def artifact(artifact_id: str, request: Request):
    content = request.app.state.generation_bridge.artifacts.get(artifact_id)
    if content is None:
        raise HTTPException(404, "Artifact not found")
    return Response(content, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


def create_demo_app():
    @asynccontextmanager
    async def lifespan(app):
        yield
        await app.state.generation_bridge.close()
    app = FastAPI(title="SSUI Open Generation Protocol Prototype", lifespan=lifespan)
    app.state.generation_bridge = GenerationBridge()
    app.include_router(router)

    @app.get("/")
    async def demo():
        return FileResponse(Path(__file__).resolve().parent.parent / "examples/generation-client/index.html")
    return app
