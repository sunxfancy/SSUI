"""Project-local, portable state storage shared by UI providers."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile

from ss_executor import search_project_root

router = APIRouter()


def state_paths(script_path: str, view: str):
    script = Path(script_path).resolve()
    root = search_project_root(str(script if script.is_dir() else script.parent))
    if root is None:
        raise HTTPException(status_code=404, detail="Project root not found")
    relative = script.relative_to(Path(root)).as_posix()
    # Absolute paths change when a project is moved to another machine.
    identity = json.dumps([relative, view], ensure_ascii=False)
    state_id = hashlib.sha256(identity.encode()).hexdigest()
    directory = Path(root) / ".ssui" / "ui_states"
    legacy = directory / (hashlib.md5(script_path.encode()).hexdigest() + ".json")
    return directory / f"{state_id}.json", legacy, str(root)


def portable_paths(value, root: str, restore: bool = False):
    """Keep project file references valid when the entire project is copied."""
    if isinstance(value, dict):
        # Escape literal user dictionaries which happen to use an internal marker.
        if restore and set(value) == {"__ssui_literal__"}:
            literal = value["__ssui_literal__"]
            if not isinstance(literal, dict):
                raise ValueError("Invalid escaped value")
            return {key: portable_paths(item, root, restore) for key, item in literal.items()}
        if not restore and set(value) in ({"__ssui_project_path__"}, {"__ssui_literal__"}):
            return {"__ssui_literal__": {key: portable_paths(item, root) for key, item in value.items()}}
        if restore and set(value) == {"__ssui_project_path__"}:
            relative = value["__ssui_project_path__"]
            if not isinstance(relative, str):
                raise ValueError("Invalid project path")
            resolved = (Path(root) / relative).resolve()
            if not resolved.is_relative_to(Path(root).resolve()):
                raise ValueError("Project path escapes project root")
            return str(resolved)
        return {key: portable_paths(item, root, restore) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_paths(item, root, restore) for item in value]
    if not restore and isinstance(value, str) and (value == root or value.startswith(root + os.sep)):
        return {"__ssui_project_path__": Path(value).relative_to(root).as_posix()}
    return value


@router.post("/api/ui_state_store")
async def ui_state_store(
    request: Request,
    script_path: str,
    state_data: Dict[str, Any] = Body(..., embed=True),
    view: str = "",
    client_id: str = Body("", embed=True),
    revision: int = Body(0, embed=True),
):
    state_file, _, root = state_paths(script_path, view)
    temporary = None
    try:
        # An unload request can overtake the previous autosave from the same UI.
        if client_id and state_file.exists():
            try:
                previous = json.loads(state_file.read_text(encoding="utf-8"))
            except ValueError:
                previous = {}
            if isinstance(previous, dict) and previous.get("client_id") == client_id and previous.get("revision", -1) >= revision:
                return {"success": True}
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=state_file.parent,
                                         suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            json.dump({"version": 1, "state": portable_paths(state_data, root),
                       "client_id": client_id, "revision": revision}, stream,
                      ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, state_file)
        return {"success": True}
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Unable to save UI state") from error
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


@router.get("/api/ui_state_load")
async def ui_state_load(request: Request, script_path: str, view: str = ""):
    state_file, legacy, root = state_paths(script_path, view)
    if not state_file.exists():
        if not view and legacy.exists():
            state_file = legacy
        else:
            return {}
    try:
        with state_file.open(encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("UI state must be an object")
        if "version" in data and "state" in data:
            if data["version"] != 1 or not isinstance(data["state"], dict):
                raise ValueError("Unsupported UI state version")
            return portable_paths(data["state"], root, restore=True)
        return data
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Unable to load UI state") from error


@router.post("/api/ui_state_asset")
async def ui_state_asset(script_path: str, file: UploadFile = File(...)):
    state_file, _, _ = state_paths(script_path, "")
    directory = state_file.parent.parent / "assets"
    temporary = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = stream.name
            while chunk := await file.read(1024 * 1024):
                digest.update(chunk)
                stream.write(chunk)
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(file.content_type, ".bin")
        destination = directory / (digest.hexdigest() + suffix)
        os.replace(temporary, destination)
        return {"success": True, "path": str(destination)}
    except OSError as error:
        raise HTTPException(status_code=500, detail="Unable to save UI asset") from error
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
