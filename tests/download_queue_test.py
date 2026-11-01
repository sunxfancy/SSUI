import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from server.task_service import TaskService
from server.routes.task_routes import _start_download, list_tasks, retry_task


class DownloadQueueTest(unittest.IsolatedAsyncioTestCase):
    async def test_modelscope_queue_lifecycle_and_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            tasks = TaskService()
            models = SimpleNamespace(modelscope_download=AsyncMock())
            websocket = SimpleNamespace(broadcast=AsyncMock(), send_callback=Mock(), send_finish=Mock())
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
                task_service=tasks, model_service=models, websocket_service=websocket,
                resources_dir=folder, scheduler=SimpleNamespace(tasks={})) ))
            record = tasks.add('download', 'Qwen/small', {'kind': 'modelscope', 'repo_id': 'Qwen/small'})
            await _start_download(request, record.id, 'modelscope', record.name, None, 'Qwen/small')
            self.assertEqual((await list_tasks(request))['items'][0]['status'], 'processing')
            args = models.modelscope_download.call_args.kwargs
            args['callback']('task', 'request', 'download_progress', {'progress': 42})
            self.assertEqual(record.progress, 42)
            args['finish_callback']('task', 'request', {'error': 'network error'})
            self.assertEqual(record.status, 'failed')
            result = await retry_task(request, record.id)
            self.assertNotEqual(result['task_id'], record.id)
            self.assertEqual(models.modelscope_download.await_count, 2)
            retried = tasks.get(result['task_id'])
            self.assertEqual(retried.meta['kind'], 'modelscope')
            tasks.cancel(retried.id)
            args = models.modelscope_download.call_args.kwargs
            args['callback']('task', 'request', 'download_progress', {'progress': 80})
            args['finish_callback']('task', 'request', {})
            self.assertEqual(retried.status, 'cancelled')
