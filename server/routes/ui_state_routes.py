import hashlib
import json
import os
from typing import Any, Dict

from fastapi import APIRouter, Body, Request

from ss_executor import search_project_root

router = APIRouter()


@router.post("/api/ui_state_store")
async def ui_state_store(
    request: Request,
    script_path: str,
    state_data: Dict[str, Any] = Body(..., embed=True),
):
    project_root = search_project_root(script_path)
    if project_root is None:
        return {"error": "Project root not found"}

    states_dir = os.path.join(project_root, ".ssui", "ui_states")
    if not os.path.exists(states_dir):
        os.makedirs(states_dir)

    state_id = hashlib.md5(script_path.encode()).hexdigest()
    state_file = os.path.join(states_dir, f"{state_id}.json")
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/ui_state_load")
async def ui_state_load(request: Request, script_path: str):
    project_root = search_project_root(script_path)
    if project_root is None:
        return {"error": "Project root not found"}

    state_id = hashlib.md5(script_path.encode()).hexdigest()
    state_file = os.path.join(project_root, ".ssui", "ui_states", f"{state_id}.json")
    if not os.path.exists(state_file):
        return {"error": "State not found"}

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        return state_data
    except Exception as e:
        return {"error": str(e)}
