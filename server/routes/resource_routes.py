"""Short-lived, one-shot disk offload decisions shared with executor processes."""
import time
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.resource_monitor import snapshot

router = APIRouter(prefix="/api/resources")
_requests = {}


class DiskRequest(BaseModel):
    model: str = Field(max_length=512)
    required_bytes: int = Field(ge=0)


class Decision(BaseModel):
    approved: bool


def _prune():
    now = time.monotonic()
    for key in list(_requests):
        if _requests[key]["expires"] <= now:
            del _requests[key]


@router.get("/")
def resources():
    return snapshot()


@router.post("/disk-requests", status_code=201)
async def request_disk(body: DiskRequest):
    _prune()
    if len(_requests) >= 128:
        raise HTTPException(429, "Too many pending offload requests")
    key = str(uuid.uuid4())
    _requests[key] = {**body.model_dump(), "id": key, "approved": None,
                      "expires": time.monotonic() + 180}
    return {"id": key}


@router.get("/disk-requests")
async def pending():
    _prune()
    return [{k: v for k, v in r.items() if k != "expires"}
            for r in _requests.values() if r["approved"] is None]


@router.get("/disk-requests/{key}")
async def decision(key: str):
    _prune()
    if key not in _requests:
        raise HTTPException(404, "Offload request expired")
    return {"approved": _requests[key]["approved"]}


@router.post("/disk-requests/{key}")
async def decide(key: str, body: Decision):
    _prune()
    if key not in _requests:
        raise HTTPException(404, "Offload request expired")
    if _requests[key]["approved"] is not None:
        raise HTTPException(409, "Offload request already answered")
    _requests[key]["approved"] = body.approved
    return {"approved": body.approved}
