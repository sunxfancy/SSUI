import unittest
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from ss_executor.scheduler import TaskScheduler


class SchedulerAddressTest(unittest.TestCase):
    def test_ipv4_and_ipv6_executor_connections(self):
        scheduler = TaskScheduler()
        for address in [('127.0.0.1', 1234), ('::1', 1234, 0, 0)]:
            with self.subTest(address=address):
                self.assertEqual(
                    scheduler._get_executor_id(SimpleNamespace(remote_address=address)),
                    f'{address[0]}:1234',
                )


class ExecutorHeartbeatTest(unittest.IsolatedAsyncioTestCase):
    async def test_busy_executor_preserves_queued_work(self):
        from ss_executor.model import Task, TaskStatus, TaskResult, UpdateStatus

        scheduler = TaskScheduler()
        socket = SimpleNamespace(remote_address=('127.0.0.1', 1234), send=AsyncMock())
        await scheduler._handle_new_connection('worker', socket)
        first = Task(script='first.py', callable='generate')
        second = Task(script='second.py', callable='generate')
        scheduler.add_task(first)
        scheduler.add_task(second)
        await scheduler._handle_status_update(UpdateStatus(task_id=first.task_id, status=TaskStatus.RUNNING))
        self.assertEqual(scheduler.task_queue.qsize(), 1)
        self.assertEqual(second.status, TaskStatus.PENDING)
        await scheduler._handle_task_result(
            TaskResult(task_id=first.task_id, status=TaskStatus.COMPLETED, result=[]),
            scheduler.executors['worker'],
        )
        await asyncio.sleep(0)
        self.assertEqual(second.status, TaskStatus.RUNNING)
        self.assertEqual(scheduler.task_queue.qsize(), 0)
        self.assertEqual(socket.send.await_count, 2)

    async def test_inference_does_not_block_communication_loop(self):
        from ss_executor.__main__ import Executor
        from ss_executor.model import Task

        class Socket:
            def __init__(self):
                self.messages = []

            async def send(self, message):
                self.messages.append(message)

        executor = Executor()
        websocket = Socket()
        task = Task(script='unused.py', callable='generate')
        with patch.object(executor, '_execute_task', side_effect=lambda _: time.sleep(.15)):
            running = asyncio.create_task(executor._handle_task(websocket, task))
            await asyncio.sleep(.03)
            self.assertFalse(running.done(), 'Inference blocked the event loop')
            await running
        self.assertEqual(len(websocket.messages), 2)
        self.assertIn('completed', websocket.messages[-1])
