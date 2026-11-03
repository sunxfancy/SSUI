import concurrent.futures
import re
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from server.agent_bridge import create_app
from server.agent_catalog import project_catalog


class AgentBridgeTest(unittest.TestCase):
    def test_command_roundtrip_validation_disconnect(self):
        with TestClient(create_app()) as client:
            with client.websocket_connect('/api/agent/connect', headers={'origin': 'http://localhost:1420'}) as socket:
                socket.send_json({'label': 'canvas', 'commands': [{'name': 'layer.add', 'inputSchema': {
                    'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name'], 'additionalProperties': False}}]})
                target = socket.receive_json()['targetId']
                self.assertEqual(client.get('/api/agent/targets').json()['items'][0]['id'], target)
                url = f'/api/agent/targets/{target}/call'
                self.assertEqual(client.post(url, json={'command': 'layer.add', 'arguments': {}}).status_code, 422)
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pending = pool.submit(client.post, url, json={'command': 'layer.add', 'arguments': {'name': 'ink'}})
                    call = socket.receive_json()
                    self.assertEqual(call['arguments'], {'name': 'ink'})
                    socket.send_json({'id': call['id'], 'result': {'layerId': 'new'}})
                    self.assertEqual(pending.result(5).json(), {'result': {'layerId': 'new'}})
                    pending = pool.submit(client.post, url, json={'command': 'layer.add', 'arguments': {'name': 'ink'}})
                    call = socket.receive_json()
                    socket.send_json({'id': call['id'], 'error': 'Layer locked'})
                    self.assertEqual(pending.result(5).status_code, 409)
                self.assertEqual(client.post(url, json={'command': 'unknown'}).status_code, 404)
            self.assertEqual(client.get('/api/agent/targets').json()['items'], [])
            self.assertEqual(client.post(url, json={'command': 'layer.add'}).status_code, 404)

    def test_foreign_origin_rejected(self):
        with TestClient(create_app()) as client:
            self.assertEqual(client.get('/api/agent/targets', headers={'origin': 'https://evil.example'}).status_code, 403)
            with self.assertRaises(Exception):
                with client.websocket_connect('/api/agent/connect', headers={'origin': 'https://evil.example'}):
                    pass

    def test_source_catalog_and_native_command_parity(self):
        root = Path(__file__).resolve().parent.parent
        entries = list(project_catalog(root))
        manifests = list((root / 'extensions').glob('*/ssextension.yaml'))
        self.assertEqual(sum(entry['kind'] == 'extension' for entry in entries), len(manifests))
        self.assertGreater(sum(entry['kind'] == 'operator' for entry in entries), 100)
        rust = (root / 'desktop/src-tauri/src/lib.rs').read_text(encoding='utf-8')
        handler = rust.split('tauri::generate_handler![')[1].split(']')[0]
        commands = set(re.findall(r'\b\w+\b', handler))
        typescript = (root / 'desktop/src/services/AgentCommands.ts').read_text(encoding='utf-8')
        for command in commands:
            self.assertRegex(typescript, rf'\b{command}:\s*\{{', command + ' missing MCP bridge schema')
