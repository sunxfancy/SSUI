"""HTTP -> WebSocket scheduler -> sandbox -> local model -> saved PNG.

Only weights are synthetic. All application components and inference operations
are real, and no model downloads or mocked pipeline calls are used.
"""
import asyncio
import contextlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
import httpx
from PIL import Image
import torch

from server.routes.script_routes import router
from server.script_service import ScriptService
from ss_executor.__main__ import Executor
from ss_executor.model import TaskStatus
from ss_executor.scheduler import TaskScheduler
from tests.moss_image_fixtures import create_moss_bundle


class MOSSImageEndToEndTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from ssui_image.MOSSImage import MOSSImageModel

        self.model_class = MOSSImageModel
        self.model_class.clear_cache()
        self.previous_threads = torch.get_num_threads()
        torch.set_num_threads(1)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = create_moss_bundle(self.root / "model")
        (self.root / "ssproject.yaml").write_text("ssui_version: 1.0.0\ndependencies: []\n", encoding="utf-8")
        self.script = self.root / "workflow.py"
        example = Path(__file__).resolve().parents[1] / "examples/basic/workflow-moss-image.py"
        shutil.copyfile(example, self.script)
        self.scheduler = TaskScheduler()
        with patch.dict(os.environ, {"SSUI_SCHEDULER_HOST": "127.0.0.1", "SSUI_SCHEDULER_PORT": "0"}):
            await self.scheduler.start()
        self.addAsyncCleanup(self.shutdown)
        port = self.scheduler.server.sockets[0].getsockname()[1]
        self.executor = Executor(f"ws://127.0.0.1:{port}")
        self.connection = asyncio.create_task(self.executor.connect())
        # Registration is exercised by the prepare request queued immediately below.
        app = FastAPI()
        app.state.script_service = ScriptService(self.scheduler)
        app.include_router(router)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ssui-test")

    async def shutdown(self):
        if hasattr(self, "client"):
            await self.client.aclose()
        if hasattr(self, "executor"):
            self.executor.is_running = False
        await self.scheduler.stop()
        if hasattr(self, "connection"):
            self.connection.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.connection
        self.model_class.clear_cache()
        self.temp.cleanup()
        torch.set_num_threads(self.previous_threads)

    async def post(self, endpoint, body=None):
        return await asyncio.wait_for(self.client.post(
            endpoint, params={"script_path": str(self.script), "callable": "txt2img"}, json=body,
        ), timeout=30)

    async def execute(self, prompt="a cat", **settings):
        values = dict(width=32, height=32, steps=2, guidance=3., shift=5., seed=42,
                      skip_negative_layer_22=True)
        values.update(settings)
        response = await self.post("/api/execute", {
            "params": {
                "model": {"function": "ssui_image.MOSSImage.MOSSImageModel.load", "params": {"model_path": str(self.bundle)}},
                "prompt": {"function": "ssui.base.Prompt.create", "params": {"text": prompt}},
                "negative_prompt": {"function": "ssui.base.Prompt.create", "params": {"text": ""}},
            },
            "details": {"MOSS Generate": values},
        })
        self.assertEqual(response.status_code, 200)
        return response.json()

    def read_image(self, result, name):
        self.assertIsInstance(result, list, result)
        self.assertEqual(result[0]["type"], "image")
        path = Path(result[0]["path"])
        self.assertEqual(path.parent, self.root / "output")
        with Image.open(path) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            pixels = image.tobytes()
            size = image.size
        if destination := os.environ.get("SSUI_MOSS_TEST_OUTPUT"):
            folder = Path(destination)
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, folder / f"{name}.png")
        return path, size, pixels

    async def test_prepare_generate_layout_and_failure_recovery(self):
        response = await self.client.get("/api/script", params={"script_path": str(self.script)})
        self.assertEqual(response.status_code, 200)
        self.assertIn("txt2img", response.json()["functions"])
        self.assertEqual(response.json()["functions"]["txt2img"]["params"]["model"], "ssui_image.MOSSImage.MOSSImageModel")
        # Prepare must succeed before any component weights are available.
        hidden = self.root / "hidden-model"
        self.bundle.rename(hidden)
        try:
            prepared = await self.post("/api/prepare")
        finally:
            hidden.rename(self.bundle)
        self.assertEqual(prepared.status_code, 200)
        self.assertEqual(prepared.json()["MOSS Generate"]["steps"]["default"], 50)
        first, size, pixels = self.read_image(await self.execute(), "text")
        self.assertEqual(size, (32, 32))
        again, _, repeated = self.read_image(await self.execute(), "text-repeat")
        self.assertEqual(pixels, repeated)
        self.assertNotEqual(first, again)
        _, _, changed = self.read_image(await self.execute(seed=43), "text-seed43")
        self.assertNotEqual(pixels, changed)
        layout = json.dumps({"summary": {"caption": "你好世界海报"}, "items": []}, ensure_ascii=False)
        _, layout_size, _ = self.read_image(await self.execute(layout, width=48, height=32,
                                                               skip_negative_layer_22=False), "layout")
        self.assertEqual(layout_size, (48, 32))
        failed = await self.execute(width=31)
        self.assertIn("multiples of 16", failed["error"])
        _, recovered_size, _ = self.read_image(await self.execute(), "recovered")
        self.assertEqual(recovered_size, (32, 32))
        statuses = [task.status for task in self.scheduler.tasks.values()]
        self.assertEqual(statuses.count(TaskStatus.FAILED), 1)
        self.assertEqual(statuses.count(TaskStatus.COMPLETED), 6)
        self.assertTrue(all(executor.current_tasks == 0 for executor in self.scheduler.executors.values()))
