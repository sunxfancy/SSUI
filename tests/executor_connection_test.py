import asyncio
import unittest

from ss_executor.model import ExecutorInfo, Task, TaskStatus
from ss_executor.scheduler import TaskScheduler


class ExecutorConnectionTest(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_completes_waiters_with_a_failure(self):
        scheduler = TaskScheduler()
        executor = ExecutorInfo("worker", "127.0.0.1", 5000)
        executor.current_tasks = 1
        scheduler.executors["worker"] = executor
        task = Task(task_id="running", script="workflow.py", callable="generate",
                    status=TaskStatus.RUNNING, executor_id="worker")
        scheduler.tasks[task.task_id] = task
        scheduler.task_completion_events[task.task_id] = asyncio.Event()
        waiter = asyncio.create_task(scheduler.wait_until_finished(task.task_id, timeout=1))
        await asyncio.sleep(0)

        await scheduler._cleanup_connection("worker")

        result = await waiter
        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIn("disconnected", result.error)
        self.assertIsNone(result.executor_id)
        self.assertFalse(executor.is_active)
        self.assertEqual(executor.current_tasks, 0)

    async def test_disconnect_does_not_change_completed_tasks(self):
        scheduler = TaskScheduler()
        scheduler.executors["worker"] = ExecutorInfo("worker", "127.0.0.1", 5000)
        task = Task(task_id="done", script="workflow.py", callable="generate",
                    status=TaskStatus.COMPLETED, result=["mesh.glb"])
        scheduler.tasks[task.task_id] = task
        await scheduler._cleanup_connection("worker")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result, ["mesh.glb"])
