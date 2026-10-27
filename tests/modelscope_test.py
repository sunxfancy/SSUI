import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from server.modelscope import download_repository, fetch_models, validate_repo


class ModelScopeTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_and_repository(self):
        def handler(request):
            if request.url.path.endswith('/Qwen/small'):
                return httpx.Response(200, json={'data': {'id': 'Qwen/small', 'tasks': ['text-generation']}})
            self.assertEqual(request.url.params['search'], 'Qwen')
            self.assertEqual(request.url.params['page_size'], '100')
            return httpx.Response(200, json={'data': {'models': [{'id': 'Qwen/small', 'tasks': ['text-generation']}]}})
        factory = httpx.AsyncClient
        with patch('server.modelscope.httpx.AsyncClient', side_effect=lambda **kw: factory(transport=httpx.MockTransport(handler), **kw)):
            self.assertEqual((await fetch_models('Qwen', 200))[0]['modelId'], 'Qwen/small')
            self.assertEqual((await fetch_models(repo_id='Qwen/small'))['id'], 'Qwen/small')

    def test_download_and_path_safety(self):
        path = 'nested/config.json'
        def handler(request):
            if request.url.path.endswith('/files'):
                return httpx.Response(200, json={'Data': {'Files': [{'Path': path, 'Size': 2, 'Type': 'blob'}]}})
            return httpx.Response(200, content=b'{}')
        factory = httpx.Client
        with tempfile.TemporaryDirectory() as folder, patch('server.modelscope.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(handler), **kw)):
            updates = []
            download_repository('Qwen/small', folder, updates.append)
            self.assertEqual((Path(folder) / path).read_bytes(), b'{}')
            self.assertEqual(updates[-1]['current'], 2)
            path = '../outside'
            with self.assertRaises(ValueError):
                download_repository('Qwen/small', folder, updates.append)

    def test_invalid_repo(self):
        for value in ('../repo', 'owner/..', 'owner/repo/extra', 'https://modelscope.cn/models/a/b'):
            with self.assertRaises(ValueError):
                validate_repo(value)
