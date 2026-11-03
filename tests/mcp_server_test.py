"""Protocol and HTTP adapter regressions; no model downloads or GPU needed."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx

HAS_MCP = importlib.util.find_spec("mcp") is not None
if HAS_MCP:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from server.mcp_server import create_mcp


@unittest.skipUnless(HAS_MCP, "Optional MCP dependency: run yarn install:mcp")
class MCPServerTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_discovery_and_execute_payload(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={"outputs": ["result.png"]})
        server = create_mcp(transport=httpx.MockTransport(handler))
        tools = {tool.name: tool for tool in await server.list_tools()}
        self.assertGreater(len(tools), 40)
        self.assertTrue(tools["ssui_read_text"].annotations.readOnlyHint)
        self.assertFalse(tools["ssui_inspect_script"].annotations.readOnlyHint)
        await server.call_tool("ssui_execute_script", {"script_path": "C:/project/a.flow", "callable": "generate", "params": {"prompt": "cat"}})
        request = calls[-1]
        self.assertEqual(request.url.path, "/api/execute")
        self.assertEqual(request.url.params["script_path"], "C:/project/a.flow")
        self.assertEqual(request.url.params["callable"], "generate")
        self.assertEqual(json.loads(request.content), {"params": {"prompt": "cat"}, "details": {}})

    async def test_real_text_routes_and_conflict(self):
        from fastapi import FastAPI
        from server.routes.file_routes import router
        app = FastAPI()
        app.include_router(router)
        server = create_mcp(transport=httpx.ASGITransport(app=app))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text("original", encoding="utf-8")
            result = await server.call_tool("ssui_read_text", {"path": str(path)})
            snapshot = result[1] if isinstance(result, tuple) else json.loads(result[0].text)
            args = {"path": str(path), "content": "updated", "expected_version": snapshot["version"]}
            await server.call_tool("ssui_save_text", args)
            self.assertEqual(path.read_text(), "updated")
            with self.assertRaisesRegex(Exception, "409"):
                await server.call_tool("ssui_save_text", args)
            self.assertEqual(path.read_text(), "updated")

    async def test_errors_and_url_restriction(self):
        for url in ("http://example.com", "http://127.0.0.1/path", "https://localhost", "http://user:pass@localhost"):
            with self.assertRaises(ValueError):
                create_mcp(url)
        for response in (httpx.Response(200, json={"error": "executor failed"}),
                         httpx.Response(422, json={"detail": "bad arguments"}),
                         httpx.Response(200, text="not json")):
            server = create_mcp(transport=httpx.MockTransport(lambda _: response))
            with self.assertRaises(Exception):
                await server.call_tool("ssui_list_models", {})
        def timeout(request):
            raise httpx.ReadTimeout("slow", request=request)
        server = create_mcp(transport=httpx.MockTransport(timeout))
        with self.assertRaisesRegex(Exception, "before retrying"):
            await server.call_tool("ssui_list_models", {})

    async def test_stdio_protocol_and_backend_error(self):
        # Real subprocess: catches stdout noise, initialization/schema and error framing.
        params = StdioServerParameters(command=sys.executable, args=["-m", "server.mcp_server", "--url", "http://127.0.0.1:1", "--timeout", "1"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertGreater(len(tools.tools), 40)
                result = await session.call_tool("ssui_list_models", {})
                self.assertTrue(result.isError)
                self.assertTrue(any(message in result.content[0].text for message in
                                    ("Cannot reach SSUI", "timed out")))


if __name__ == "__main__":
    unittest.main()
