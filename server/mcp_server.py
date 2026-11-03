"""Optional stdio MCP adapter for an already running SSUI backend.

No engine/model imports: protocol output is the only data written to stdout.
"""
import argparse
import base64
import asyncio
import json
import anyio
import os
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from server.mcp_catalog import CatalogMCP


def create_mcp(base_url: str = "http://127.0.0.1:7422", timeout: float = 600,
               transport: httpx.AsyncBaseTransport | None = None, ui_url: str | None = None) -> FastMCP:
    url = urlsplit(base_url)
    if (url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1", "::1")
            or url.username or url.password or url.query or url.fragment
            or url.path not in ("", "/")):
        raise ValueError("SSUI URL must be a loopback HTTP origin, e.g. http://127.0.0.1:7422")
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    ui_url = ui_url or base_url
    ui_parts = urlsplit(ui_url)
    if (ui_parts.scheme != "http" or ui_parts.hostname not in ("localhost", "127.0.0.1", "::1")
            or ui_parts.username or ui_parts.password or ui_parts.query or ui_parts.fragment or ui_parts.path not in ("", "/")):
        raise ValueError("UI relay must be a loopback HTTP origin")
    server = CatalogMCP("SSUI", instructions=(
        "Control the running local SSUI backend. Discover script functions, prepare their "
        "parameters, then execute with those parameters. Script discovery may load Python code. "
        "Execution needs a running SSExecutor and may take minutes. Paths refer to the SSUI "
        "machine. Only use trusted projects. Returned file paths can be opened through /file. "
        "A timeout does not cancel backend execution; inspect tasks before retrying. "
        "ssui_api_* tools cover ALL backend OpenAPI operations including extensions, uploads, "
        "configuration, model sources, downloads and UI persistence. Use ssui_ui_targets then "
        "ssui_ui_call for live desktop/native/editor commands with advertised schemas. "
        "Use ssui_capabilities to refresh runtime discovery after loading extensions."
    ))
    read = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)

    async def request(method: str, path: str, **kwargs) -> Any:
        raw = kwargs.pop("raw", False)
        origin = ui_url if path.startswith("/api/agent/targets") else base_url
        try:
            async with httpx.AsyncClient(base_url=origin.rstrip("/"), timeout=timeout,
                                         trust_env=False, transport=transport) as client:
                response = await client.request(method, path, **kwargs)
                if raw and response.is_redirect:
                    return {"status": response.status_code, "location": response.headers.get("location")}
                response.raise_for_status()
                if raw and "json" not in response.headers.get("content-type", ""):
                    if len(response.content) > 20 * 1024 * 1024:
                        raise ToolError("Response exceeds 20 MiB; use output path with local file tools")
                    return {"mimeType": response.headers.get("content-type", "application/octet-stream"),
                            "data_base64": base64.b64encode(response.content).decode()}
                result = response.json()
        except httpx.TimeoutException as exc:
            raise ToolError("SSUI request timed out. Execution may still be running; inspect ssui_list_tasks before retrying.") from exc
        except httpx.HTTPStatusError as exc:
            raise ToolError(f"SSUI HTTP {exc.response.status_code}: {exc.response.text[:2000]}") from exc
        except httpx.RequestError as exc:
            raise ToolError("Cannot reach SSUI. Start the desktop app or yarn start:server, and verify --url.") from exc
        except ValueError as exc:
            raise ToolError("SSUI returned non-JSON data; check the backend URL and version.") from exc
        if isinstance(result, dict) and (result.get("error") or result.get("success") is False):
            raise ToolError(f"SSUI operation failed: {result}")
        return result

    server.api_request = request

    @server.tool(annotations=read)
    async def ssui_project_catalog(search: str = "", kind: Literal["", "extension", "operator", "example", "error"] = "", offset: int = 0, limit: int = 50) -> dict:
        """Discover ALL first-party extension SDK public callables and bundled example scripts without importing model code. Search Image/Video/Audio/LLM/Motion/3D, model names or callable names. Paginated; source presence is not a runtime availability guarantee."""
        return await request("GET", "/api/agent/catalog", params={"search": search, "kind": kind, "offset": offset, "limit": limit})

    @server.tool(annotations=write)
    async def ssui_run_callback_api(api_tool: str, arguments: dict[str, Any], wait_seconds: float = 300) -> dict:
        """Run an API that requires client_id WebSocket callbacks (scan models, HuggingFace/preset downloads). Opens /ws before submitting, injects client_id, waits for finish and returns bounded callbacks. Inspect ssui_api_* schema for other arguments. Timeout does not cancel downloads."""
        import copy
        from websockets.asyncio.client import connect
        if not 0 < wait_seconds <= 600:
            raise ToolError("wait_seconds must be between 0 and 600")
        if server.catalog is None:
            await server.refresh_catalog()
        operation = server.catalog.operations.get(api_tool)
        if not operation or "{client_id}" not in operation["path"]:
            raise ToolError("Choose an ssui_api_* operation with client_id path parameter")
        ws_url = base_url.replace("http://", "ws://", 1).rstrip("/") + "/ws"
        try:
            with anyio.fail_after(wait_seconds):
                import inspect
                options = {"proxy": None} if "proxy" in inspect.signature(connect).parameters else {}
                async with connect(ws_url, **options) as socket:
                    hello = json.loads(await socket.recv())
                    if hello.get("type") != "uuid":
                        raise ToolError("Backend did not send a WebSocket client UUID")
                    args = copy.deepcopy(arguments)
                    args.setdefault("path", {})["client_id"] = hello["uuid"]
                    method, path, kwargs = server.catalog.prepare(api_tool, args)
                    started = await request(method, path, **kwargs)
                    callbacks, count = [], 0
                    while True:
                        event = json.loads(await socket.recv())
                        if event.get("request_uuid") != started.get("request_uuid"):
                            continue
                        if event.get("type") == "finish":
                            if event.get("error"):
                                raise ToolError(f"SSUI background operation failed: {event['error']}")
                            return {"started": started, "finish": event, "callbacks": callbacks, "callback_count": count}
                        count += 1
                        callbacks.append(event)
                        if len(callbacks) > 200:
                            callbacks.pop(0)
        except TimeoutError as exc:
            raise ToolError("Callback wait timed out; download/scan may still run. Inspect tasks/models before retrying.") from exc
        except OSError as exc:
            raise ToolError("Cannot connect to SSUI /ws; start the backend and check its URL.") from exc

    @server.tool(annotations=read)
    async def ssui_capabilities() -> dict:
        """Refresh all backend API tools after loading extensions; report live/fallback schema source and live UI command catalog."""
        await server.refresh_catalog()
        try:
            targets = await request("GET", "/api/agent/targets")
        except ToolError as exc:
            targets = {"error": str(exc)}
        return {"schema_source": server.schema_source, "api_tools": len(server.catalog.operations), "ui_targets": targets}

    @server.tool(annotations=read)
    async def ssui_ui_targets() -> dict:
        """Discover connected desktop/windows, graph editors and canvases with command schemas. Open the relevant UI first."""
        return await request("GET", "/api/agent/targets")

    @server.tool(annotations=write)
    async def ssui_ui_call(target_id: str, command: str, arguments: dict[str, Any], timeout: float = 60) -> dict:
        """Execute an advertised live UI/native command. Inspect ssui_ui_targets for exact argument schemas; returns actual command result/errors."""
        from urllib.parse import quote
        return await request("POST", f"/api/agent/targets/{quote(target_id, safe='')}/call",
                             json={"command": command, "arguments": arguments, "timeout": timeout})

    @server.tool(annotations=read)
    async def ssui_status() -> dict:
        """Get backend PyTorch version, active compute device, and installed extensions."""
        return {"version": await request("GET", "/api/version"),
                "device": await request("GET", "/api/device"),
                "extensions": await request("GET", "/api/extensions")}

    @server.tool(annotations=read)
    async def ssui_list_models() -> Any:
        """List installed model metadata and paths available to workflow parameters."""
        return await request("GET", "/api/available_models")

    @server.tool(annotations=write)
    async def ssui_inspect_script(script_path: str) -> Any:
        """Discover callable names and types in a trusted .py or .flow; may load code or compile Flow."""
        return await request("GET", "/api/script", params={"script_path": script_path})

    @server.tool(annotations=read)
    async def ssui_list_operators(flow_path: str) -> Any:
        """Inspect typed project/extension Flow operators without executing them. Parent directory must exist."""
        return await request("GET", "/api/flow/operators", params={"flow_path": flow_path})

    @server.tool(annotations=write)
    async def ssui_prepare_script(script_path: str, callable: str) -> Any:
        """Prepare a trusted callable's UI parameter schema/defaults through SSExecutor before execution."""
        return await request("POST", "/api/prepare", params={"script_path": script_path, "callable": callable})

    @server.tool(annotations=write)
    async def ssui_execute_script(script_path: str, callable: str, params: dict[str, Any],
                                  details: dict[str, Any] | None = None) -> Any:
        """Execute a trusted workflow and return its actual result/output paths. Use prepare first; may consume GPU/memory and write files. Do not blindly retry on timeout."""
        return await request("POST", "/api/execute", params={"script_path": script_path, "callable": callable},
                             json={"params": params, "details": details or {}})

    @server.tool(annotations=read)
    async def ssui_list_tasks(kind: Literal["download", "generation"] | None = None,
                              status: Literal["waiting", "processing", "completed", "failed", "cancelled"] | None = None) -> Any:
        """List backend tasks, optionally filtering by kind/status. Does not return workflow results."""
        return await request("GET", "/api/tasks", params={k: v for k, v in {"kind": kind, "status": status}.items() if v is not None})

    @server.tool(annotations=read)
    async def ssui_list_files(script_path: str, file_type: Literal["image", "video", "audio", "3dmodel", "script", "canvas"]) -> Any:
        """List matching assets within the project containing script_path."""
        return await request("GET", f"/files/{file_type}", params={"script_path": script_path})

    @server.tool(annotations=read)
    async def ssui_read_text(path: str) -> dict:
        """Read UTF-8 script/Flow/text content and its version hash for conflict-safe saving."""
        return await request("GET", "/file/text", params={"path": path})

    @server.tool(annotations=write)
    async def ssui_save_text(path: str, content: str, expected_version: str) -> dict:
        """Save an existing UTF-8 document with the version from ssui_read_text. HTTP 409 means reread and reconcile edits."""
        if not expected_version:
            raise ToolError("expected_version is required; call ssui_read_text first.")
        return await request("POST", "/files/upload_json", json={"path": path, "content": content, "expected_version": expected_version})

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("SSUI_MCP_URL", "http://127.0.0.1:7422"))
    parser.add_argument("--timeout", type=float, default=600, help="Backend request timeout in seconds")
    parser.add_argument("--ui-url", default=os.environ.get("SSUI_AGENT_URL"), help="Optional independent UI relay origin (port 7424)")
    args = parser.parse_args()
    create_mcp(args.url, args.timeout, ui_url=args.ui_url).run(transport="stdio")


if __name__ == "__main__":
    main()
