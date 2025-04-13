# scheduler.py
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from .model import Task, TaskStatus, ExecutorInfo, ExecutorRegister, RegisterResponse, UpdateStatus, TaskResult, ExeMessage
import websockets
from .executor_main import main
import traceback
from multiprocessing import Pool

logger = logging.getLogger("TaskScheduler")

class TaskScheduler:
    """异步任务调度器，用于管理执行器连接和任务分配"""
    
    def __init__(self):
        # 核心数据结构
        self.tasks: Dict[str, Task] = {}
        self.executors: Dict[str, ExecutorInfo] = {}
        self.executor_websockets: Dict[str, websockets.ClientConnection] = {}
        
        # 异步组件
        self.task_queue = asyncio.PriorityQueue()
        self.lock = asyncio.Lock()
        self.server = None
        
        # 事件通知
        self.task_completion_events: Dict[str, asyncio.Event] = {}
        self.all_tasks_completion_event = asyncio.Event()
        
        # 清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self.pool = None

    async def start(self):
        """启动调度器"""
        try:
            self.server = await websockets.serve(
                self.handle_executor_connection, 
                "localhost", 
                5000
            )
            logger.info("任务调度器已启动")
            
            # 使用进程池，确保子进程和父进程使用相同的sys.path
            self.pool = Pool(processes=1)
            self.pool.apply_async(main)
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            raise
    
    async def stop(self):
        """停止调度器"""
        # 取消清理任务
        if self._cleanup_task:
            try:
                self._cleanup_task.cancel()
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self.server:
            try:
                # 关闭WebSocket服务器
                self.server.close()
                await self.server.wait_closed()
            
                # 关闭所有执行器连接
                await self._close_all_connections()
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")
            
        # 关闭进程池
        if self.pool:
            self.pool.terminate()
            self.pool.join()
            
        logger.info("任务调度器已停止")
        

    async def _close_all_connections(self):
        """关闭所有执行器连接"""
        for ws in self.executor_websockets.values():
            try:
                await ws.close()
            except Exception as e:
                logger.error(f"关闭连接失败: {e}")
        
        self.executor_websockets.clear()
        self.executors.clear()

    async def handle_executor_connection(self, websocket: websockets.ClientConnection):
        """处理执行器WebSocket连接"""
        executor_id = self._get_executor_id(websocket)
        
        try:
            await self._handle_new_connection(executor_id, websocket)
            await self._process_messages(executor_id, websocket)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"执行器 {executor_id} 已断开连接")
        except Exception as e:
            logger.error(f"处理执行器连接异常:\n{traceback.format_exc()}")
        finally:
            await self._cleanup_connection(executor_id)

    def _get_executor_id(self, websocket: websockets.ClientConnection) -> str:
        """获取执行器ID"""
        host, port, _, _ = websocket.remote_address
        return f"{host}:{port}"

    async def _handle_new_connection(self, executor_id: str, websocket: websockets.ClientConnection):
        """处理新的执行器连接"""
        # 关闭旧连接
        if executor_id in self.executor_websockets:
            await self.executor_websockets[executor_id].close()
        
        # 创建新的执行器信息
        executor = ExecutorInfo(
            executor_id=executor_id,
            host=websocket.remote_address[0],
            port=websocket.remote_address[1],
        )
        
        self.executors[executor_id] = executor
        self.executor_websockets[executor_id] = websocket

    async def _process_messages(self, executor_id: str, websocket: websockets.ClientConnection):
        """处理来自执行器的消息"""
        async for message in websocket:
            try:
                exe_message = ExeMessage.validate_json(message)
                await self._process_executor_message(executor_id, exe_message)
            except Exception as e:
                logger.error(f"处理消息失败: {e}")

    async def _cleanup_connection(self, executor_id: str):
        """清理执行器连接"""
        if executor_id in self.executor_websockets:
            del self.executor_websockets[executor_id]
        if executor_id in self.executors:
            self.executors[executor_id].is_active = False

    def add_task(self, task: Task) -> str:
        """添加新任务"""
        self.tasks[task.task_id] = task
        self.task_completion_events[task.task_id] = asyncio.Event()
        self.all_tasks_completion_event.clear()
        
        if self._try_assign_task(task):
            logger.info(f"任务 {task.task_id} 已立即分配给执行器")
        else:
            asyncio.create_task(self.task_queue.put((-task.priority, task.task_id)))
            logger.info(f"任务 {task.task_id} 已加入队列")
        
        return task.task_id

    async def run_task(self, task: Task):
        """运行任务"""
        self.add_task(task)
        task = await self.wait_until_finished(task.task_id)
        return task.result

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self.tasks.values())

    def get_all_executors(self) -> List[ExecutorInfo]:
        """获取所有执行器信息"""
        return list(self.executors.values())

    def _try_assign_task(self, task: Task) -> bool:
        """尝试将任务分配给可用的执行器"""
        if task.status != TaskStatus.PENDING:
            return False
        
        executor, websocket = self._find_available_executor()
        if not executor or not websocket:
            return False
        
        try:
            self._update_task_and_executor_status(task, executor)
            asyncio.create_task(websocket.send(task.model_dump_json()))
            return True
        except Exception as e:
            logger.error(f"分配任务时出错:\n{traceback.format_exc()}")
            self._revert_task_assignment(task, executor)
            return False

    def _find_available_executor(self) -> Tuple[Optional[ExecutorInfo], Optional[websockets.ClientConnection]]:
        """查找可用的执行器"""
        for executor_id, executor in self.executors.items():
            if (executor.is_active and 
                executor.current_tasks < executor.max_tasks and 
                (datetime.now() - executor.last_heartbeat).seconds < 30):
                return executor, self.executor_websockets.get(executor_id)
        return None, None

    def _update_task_and_executor_status(self, task: Task, executor: ExecutorInfo):
        """更新任务和执行器状态"""
        task.status = TaskStatus.RUNNING
        task.started_at = str(datetime.now())
        task.executor_id = executor.executor_id
        executor.current_tasks += 1

    def _revert_task_assignment(self, task: Task, executor: ExecutorInfo):
        """恢复任务分配状态"""
        task.status = TaskStatus.PENDING
        task.started_at = None
        task.executor_id = None
        executor.current_tasks = max(0, executor.current_tasks - 1)

    async def _process_executor_message(self, executor_id: str, message: Union[ExecutorRegister, RegisterResponse, UpdateStatus, TaskResult]):
        """处理来自执行器的消息"""
        async with self.lock:
            if executor_id not in self.executors:
                return
                
            executor = self.executors[executor_id]
            executor.last_heartbeat = datetime.now()
            
            if isinstance(message, ExecutorRegister):
                await self._handle_executor_register(executor_id)
            elif isinstance(message, UpdateStatus):
                await self._handle_status_update(message)
            elif isinstance(message, TaskResult):
                await self._handle_task_result(message, executor)

    async def _handle_executor_register(self, executor_id: str):
        """处理执行器注册"""
        register_response = RegisterResponse(
            status="success",
            message="注册成功"
        )
        await self.executor_websockets[executor_id].send(register_response.model_dump_json())
        logger.info(f"执行器 {executor_id} 已注册")
        
        if self.task_queue.qsize() > 0:
            priority, task_id = await self.task_queue.get()
            logger.info(f"尝试分配任务 {task_id}")
            self._try_assign_task(self.tasks[task_id])

    async def _handle_status_update(self, message: UpdateStatus):
        """处理状态更新"""
        task_id = message.task_id
        if task_id in self.tasks:
            self.tasks[task_id].status = message.status

    async def _handle_task_result(self, message: TaskResult, executor: ExecutorInfo):
        """处理任务结果"""
        task_id = message.task_id
        if task_id not in self.tasks:
            return
            
        task = self.tasks[task_id]
        task.status = message.status
        
        if message.status == TaskStatus.COMPLETED:
            await self._handle_completed_task(task, message, executor)
        elif message.status == TaskStatus.FAILED:
            await self._handle_failed_task(task, message, executor)

    async def _handle_completed_task(self, task: Task, message: TaskResult, executor: ExecutorInfo):
        """处理完成的任务"""
        task.result = message.result
        task.completed_at = str(datetime.now())
        task.executor_id = None
        executor.current_tasks = max(0, executor.current_tasks - 1)
        logger.info(f"任务 {task.task_id} 已完成")
        
        await self._set_task_completion_event(task.task_id)
        await self._check_all_tasks_completion()

    async def _handle_failed_task(self, task: Task, message: TaskResult, executor: ExecutorInfo):
        """处理失败的任务"""
        task.error = message.error
        task.completed_at = str(datetime.now())
        task.executor_id = None
        executor.current_tasks = max(0, executor.current_tasks - 1)
        logger.info(f"任务 {task.task_id} 失败，错误信息：{message.error}")
        
        await self._set_task_completion_event(task.task_id)
        await self._check_all_tasks_completion()

    async def _set_task_completion_event(self, task_id: str):
        """设置任务完成事件"""
        if task_id in self.task_completion_events:
            self.task_completion_events[task_id].set()

    async def _check_all_tasks_completion(self):
        """检查是否所有任务都已完成"""
        all_completed = all(
            t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            for t in self.tasks.values()
        )
        if all_completed:
            self.all_tasks_completion_event.set()

    async def wait_until_finished(self, task_id: Optional[str] = None, timeout: Optional[float] = None) -> Optional[Union[Task, List[Task]]]:
        """等待任务完成"""
        try:
            if task_id is None:
                return await self._wait_for_all_tasks(timeout)
            return await self._wait_for_single_task(task_id, timeout)
        except asyncio.TimeoutError:
            logger.warning(f"等待任务完成超时")
            return None

    async def _wait_for_all_tasks(self, timeout: Optional[float]) -> Optional[List[Task]]:
        """等待所有任务完成"""
        if not self.tasks:
            logger.info("没有任务需要等待")
            return []
        
        if timeout is not None:
            await asyncio.wait_for(self.all_tasks_completion_event.wait(), timeout)
        else:
            await self.all_tasks_completion_event.wait()
        
        return list(self.tasks.values())

    async def _wait_for_single_task(self, task_id: str, timeout: Optional[float]) -> Optional[Task]:
        """等待单个任务完成"""
        if task_id not in self.tasks:
            logger.warning(f"任务 {task_id} 不存在")
            return None
        
        task = self.tasks[task_id]
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return task
        
        if timeout is not None:
            await asyncio.wait_for(self.task_completion_events[task_id].wait(), timeout)
        else:
            await self.task_completion_events[task_id].wait()
        
        return self.tasks[task_id]