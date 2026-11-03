import base64
import importlib.util
import json
import unittest
from pathlib import Path

import httpx

HAS_MCP = importlib.util.find_spec('mcp') is not None
if HAS_MCP:
    from server.mcp_catalog import APICatalog
    from server.mcp_server import create_mcp
    from jsonschema import Draft202012Validator


@unittest.skipUnless(HAS_MCP, 'Optional MCP dependency: yarn install:mcp')
class MCPCatalogTest(unittest.IsolatedAsyncioTestCase):
    async def test_callback_api_waits_for_actual_websocket_finish(self):
        import asyncio
        import socket
        import threading
        import uuid
        import uvicorn
        from fastapi import FastAPI
        from server.websocket_service import WebSocketService
        from server.routes.websocket_routes import router
        app = FastAPI()
        app.state.websocket_service = WebSocketService()
        app.include_router(router)
        @app.post('/scan/{client_id}')
        async def scan(client_id: str):
            request_id = str(uuid.uuid4())
            async def complete():
                await asyncio.sleep(.02)
                await app.state.websocket_service.send_message(client_id, {'type': 'callback', 'request_uuid': request_id, 'model_found': 'actual-message'})
                await app.state.websocket_service.send_message(client_id, {'type': 'finish', 'request_uuid': request_id, 'total': 1})
            asyncio.create_task(complete())
            return {'type': 'start', 'request_uuid': request_id}
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        process = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        thread = threading.Thread(target=process.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if process.started:
                    break
                await asyncio.sleep(.01)
            self.assertTrue(process.started)
            server = create_mcp(f'http://127.0.0.1:{port}')
            tool = next(tool for tool in await server.list_tools() if tool.name.startswith('ssui_api_scan'))
            result = await server.call_tool('ssui_run_callback_api', {'api_tool': tool.name, 'arguments': {}, 'wait_seconds': 5})
            result = result[1] if isinstance(result, tuple) else json.loads(result[0].text)
            self.assertEqual(result['finish']['total'], 1)
            self.assertEqual(result['callbacks'][0]['model_found'], 'actual-message')
        finally:
            process.should_exit = True
            await asyncio.to_thread(thread.join, 5)
            listener.close()

    async def test_every_checked_in_operation_has_valid_tool_schema(self):
        document = json.loads((Path(__file__).resolve().parent.parent / 'server/openapi.json').read_text(encoding='utf-8'))
        catalog = APICatalog(document)
        expected = {(method.upper(), path) for path, item in document['paths'].items() for method in item if method in ('get', 'post', 'put', 'delete', 'patch', 'head', 'options')}
        self.assertEqual({(operation['method'], operation['path']) for operation in catalog.operations.values()}, expected)
        for operation in catalog.operations.values():
            Draft202012Validator.check_schema(operation['tool'].inputSchema)
            self.assertLessEqual(len(operation['tool'].name), 64)

    async def test_live_extension_discovery_schema_validation_and_binary(self):
        from fastapi import FastAPI, UploadFile, File
        from fastapi.responses import Response
        app = FastAPI()
        @app.post('/extension/test/upload')
        async def upload(file: UploadFile = File(...)):
            return Response(await file.read(), media_type='image/png')
        server = create_mcp(transport=httpx.ASGITransport(app=app))
        tools = await server.list_tools()
        tool = next(tool for tool in tools if tool.name.startswith('ssui_api_'))
        result = await server.call_tool(tool.name, {'body': {'file': {'filename': 'test.png', 'data_base64': base64.b64encode(b'PNG content').decode()}}})
        self.assertEqual(base64.b64decode(result.structuredContent['result']['data_base64']), b'PNG content')
        self.assertEqual(result.structuredContent['result']['mimeType'], 'image/png')
        with self.assertRaisesRegex(Exception, 'required'):
            await server.call_tool(tool.name, {})
        self.assertEqual(server.schema_source, 'live backend')

    async def test_query_path_body_contract_and_reject_unknown_arguments(self):
        from fastapi import FastAPI, Body
        app = FastAPI()
        @app.post('/items/{item_id}')
        async def update(item_id: str, count: int, body: dict = Body(...)):
            return {'id': item_id, 'count': count, 'body': body}
        server = create_mcp(transport=httpx.ASGITransport(app=app))
        tool = next(tool for tool in await server.list_tools() if tool.name.startswith('ssui_api_'))
        args = {'path': {'item_id': 'one'}, 'query': {'count': 3}, 'body': {'nested': [1, 2]}}
        result = await server.call_tool(tool.name, args)
        self.assertEqual(result.structuredContent['result'], {'id': 'one', 'count': 3, 'body': {'nested': [1, 2]}})
        args['query']['count'] = 'bad'
        with self.assertRaisesRegex(Exception, 'Invalid API arguments'):
            await server.call_tool(tool.name, args)
