from typing import Any, Dict

from fastapi import APIRouter, Request

from ss_executor import search_project_root

router = APIRouter()


@router.post("/api/flow/compile")
async def compile_flow(request: Request, flow_path: str):
    return request.app.state.script_service.compile_flow(flow_path)


@router.get("/api/version")
async def version(request: Request):
    return request.app.state.script_service.get_torch_version()


@router.get("/api/device")
async def device(request: Request):
    return request.app.state.script_service.get_device_info()


@router.get("/api/script")
async def script(request: Request, script_path: str):
    result: Dict[str, Any] = {}
    result["functions"] = request.app.state.script_service.get_script_functions(
        script_path
    )
    result["root_path"] = search_project_root(script_path)
    return result


@router.post("/api/prepare")
async def prepare(request: Request, script_path: str, callable: str):
    return await request.app.state.script_service.prepare_script(
        script_path, callable
    )


@router.post("/api/execute")
async def execute(
    request: Request,
    script_path: str,
    callable: str,
    params: Dict[str, Any],
    details: Dict[str, Any],
):
    return await request.app.state.script_service.execute_script(
        script_path, callable, params, details
    )
