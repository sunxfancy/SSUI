import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ss_executor.__main__ import Executor
from ss_executor.model import Task
from ss_executor.scheduler import TaskScheduler


class StartupTest(unittest.TestCase):
    def test_optional_download_acceleration_is_not_required(self):
        import os
        from server.__main__ import main

        with patch.dict(os.environ), patch("server.__main__.importlib.util.find_spec", return_value=None), \
             patch("sys.argv", ["server", "--dev"]), patch("uvicorn.run"):
            os.environ.pop("HF_HUB_ENABLE_HF_TRANSFER", None)
            main()
            self.assertEqual(os.environ["HF_HUB_ENABLE_HF_TRANSFER"], "0")

    def test_download_acceleration_respects_explicit_setting(self):
        import os
        from server.__main__ import main

        with patch.dict(os.environ, {"HF_HUB_ENABLE_HF_TRANSFER": "0"}), \
             patch("sys.argv", ["server", "--dev"]), patch("uvicorn.run"):
            main()
            self.assertEqual(os.environ["HF_HUB_ENABLE_HF_TRANSFER"], "0")

    def test_scheduler_accepts_ipv4_and_ipv6(self):
        scheduler = TaskScheduler()
        for address in [("127.0.0.1", 1234), ("::1", 1234, 0, 0)]:
            self.assertEqual(
                scheduler._get_executor_id(SimpleNamespace(remote_address=address)),
                f"{address[0]}:1234",
            )

    def test_dev_server_uses_reload_import_string(self):
        from server.__main__ import main

        with patch("sys.argv", ["server", "--dev", "--port", "17422"]), patch("uvicorn.run") as run:
            main()
        self.assertEqual(run.call_args.args, ("server.server:app",))
        self.assertTrue(run.call_args.kwargs["reload"])


class ExecutorResponsivenessTest(unittest.IsolatedAsyncioTestCase):
    async def test_cpu_work_leaves_event_loop_responsive(self):
        import threading

        entered = threading.Event()
        release = threading.Event()
        executor = Executor()
        websocket = SimpleNamespace(send=AsyncMock())

        def work(_task):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("event loop did not release worker")
            return ["complete"]

        with patch.object(executor, "_execute_task", side_effect=work):
            task = asyncio.create_task(executor._handle_task(websocket, Task(script="unused.py", callable="run")))
            try:
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(entered.is_set())
            finally:
                release.set()
                await task
        self.assertIn('"status":"completed"', websocket.send.call_args.args[0])
