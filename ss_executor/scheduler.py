# scheduler.py
import asyncio
import json
import logging
import multiprocessing
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from .model import Task, TaskStatus, ExecutorInfo, ExecutorRegister, RegisterResponse, UpdateStatus, TaskResult, ExeMessage
import time
import websockets
from .executor_main import main
import traceback

logger = logging.getLogger("TaskScheduler")

class TaskScheduler:
    """异步任务调度器，用于管理执行器连接和任务分配"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.executors: Dict[str, ExecutorInfo] = {}
        self.executor_websockets: Dict[str, websockets.ClientConnection] = {}
        self.task_queue = asyncio.PriorityQueue()
        self.lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self.server = None
        # 添加任务完成事件字典，用于通知任务完成
        self.task_completion_events: Dict[str, asyncio.Event] = {}
        # 添加所有任务完成事件
        self.all_tasks_completion_event = asyncio.Event()

    async def start(self):
        """启动调度器"""
        # 启动WebSocket服务器
        self.server = await websockets.serve(self.handle_executor_connection, "localhost", 5000)
        logger.info("任务调度器已启动")
        
        # 为executor创建新进程
        multiprocessing.Process(target=main, daemon=True).start()
    
    async def stop(self):
        """停止调度器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            
        # 关闭WebSocket服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        # 关闭所有WebSocket连接
        for ws in self.executor_websockets.values():
            await ws.close()
            
        self.executor_websockets.clear()
        self.executors.clear()
        logger.info("任务调度器已停止")
        
    async def handle_executor_connection(self, websocket: websockets.ClientConnection):
        """处理执行器WebSocket连接"""
        print(websocket.remote_address)
        host, port, _, _ = websocket.remote_address
        executor_id = f"{host}:{port}"

        try:
            # 如果执行器已存在，关闭旧连接
            if executor_id in self.executor_websockets:
                old_ws = self.executor_websockets[executor_id]
                await old_ws.close()
            
            # 创建执行器信息
            executor = ExecutorInfo(
                executor_id=executor_id,
                host=host,
                port=port,
            )
            
            self.executors[executor_id] = executor
            self.executor_websockets[executor_id] = websocket

            # 等待注册消息
            async for message in websocket:
                try:
                    # 使用ExeMessage解析消息
                    exe_message = ExeMessage.validate_json(message)
                    await self._process_executor_message(executor_id, exe_message)
                except Exception as e:
                    logger.error(f"解析消息失败: {e}")
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"执行器 {executor_id} 已断开连接")
        except Exception as e:
            # 打印异常调用栈
            logger.error(f"执行器连接处理异常详情:\n{traceback.format_exc()}")
        finally:
            # 清理连接
            if executor_id in self.executor_websockets:
                del self.executor_websockets[executor_id]
            if executor_id in self.executors:
                self.executors[executor_id].is_active = False
                
    def add_task(self, task: Task) -> str:
        """添加新任务"""
        self.tasks[task.task_id] = task
        # 为任务创建完成事件
        self.task_completion_events[task.task_id] = asyncio.Event()
        # 重置所有任务完成事件
        self.all_tasks_completion_event.clear()
        
        # 尝试立即分配任务
        if self._try_assign_task(task):
            logger.info(f"任务 {task.task_id} 已立即分配给执行器")
        else:
            # 如果无法立即分配，加入队列
            asyncio.create_task(self.task_queue.put((-task.priority, task.task_id)))
            logger.info(f"任务 {task.task_id} 已加入队列")
        return task.task_id
    
    async def run_task(self, task: Task):
        """运行任务"""
        self.add_task(task)
        await self.wait_until_finished(task.task_id)
            
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
            
        # 查找可用的执行器
        available_executor = None
        available_ws = None
        
        for executor_id, executor in self.executors.items():
            if (executor.is_active and 
                executor.current_tasks < executor.max_tasks and 
                (datetime.now() - executor.last_heartbeat).seconds < 30):
                available_executor = executor
                available_ws = self.executor_websockets.get(executor_id)
                break
                
        if not available_executor or not available_ws:
            return False
            
        try:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = str(datetime.now())
            task.executor_id = available_executor.executor_id
            
            # 更新执行器状态
            available_executor.current_tasks += 1
            
            # 发送任务给执行器
            logger.info(f"发送任务给执行器: {task.model_dump_json()}")
            asyncio.create_task(available_ws.send(task.model_dump_json()))
            
            return True
            
        except Exception as e:
            logger.error(f"分配任务时出错:\n{traceback.format_exc()}")
            # 恢复状态
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.executor_id = None
            available_executor.current_tasks = max(0, available_executor.current_tasks - 1)
            return False
            
    async def _process_executor_message(self, executor_id: str, message: Union[ExecutorRegister, RegisterResponse, UpdateStatus, TaskResult]):
        """处理来自执行器的消息"""
        async with self.lock:
            if executor_id in self.executors:
                executor = self.executors[executor_id]
                executor.last_heartbeat = datetime.now()
                
                if isinstance(message, ExecutorRegister):
                    # 发送注册成功响应
                    register_response = RegisterResponse(
                        status="success",
                        message="注册成功"
                    )
                    await self.executor_websockets[executor_id].send(register_response.model_dump_json())
                    
                    logger.info(f"执行器 {executor_id} 已注册")
                    if self.task_queue.qsize() > 0:
                        priority, task_id = self.task_queue.get_nowait()
                        logger.info(f"尝试分配任务 {task_id}")
                        self._try_assign_task(self.tasks[task_id])

                elif isinstance(message, UpdateStatus):
                    # 处理状态更新
                    task_id = message.task_id
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        task.status = message.status
                        
                elif isinstance(message, TaskResult):
                    task_id = message.task_id
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        task.status = message.status
                        
                        if message.status == TaskStatus.COMPLETED:
                            task.result = message.result
                            task.completed_at = str(datetime.now())
                            task.executor_id = None
                            executor.current_tasks = max(0, executor.current_tasks - 1)
                            logger.info(f"任务 {task_id} 已完成")
                            
                            # 设置任务完成事件 - 使用线程安全的方式
                            if task_id in self.task_completion_events:
                                # 在事件循环中设置事件
                                asyncio.create_task(self._set_task_completion_event(task_id))
                                
                            # 检查是否所有任务都已完成
                            all_completed = all(
                                t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                                for t in self.tasks.values()
                            )
                            if all_completed:
                                # 在事件循环中设置所有任务完成事件
                                asyncio.create_task(self._set_all_tasks_completion_event())
                                
                        elif message.status == TaskStatus.FAILED:
                            task.error = message.error
                            task.completed_at = str(datetime.now())
                            task.executor_id = None
                            executor.current_tasks = max(0, executor.current_tasks - 1)
                            logger.info(f"任务 {task_id} 失败")
                            
                            # 设置任务完成事件 - 使用线程安全的方式
                            if task_id in self.task_completion_events:
                                # 在事件循环中设置事件
                                asyncio.create_task(self._set_task_completion_event(task_id))
                                
                            # 检查是否所有任务都已完成
                            all_completed = all(
                                t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                                for t in self.tasks.values()
                            )
                            if all_completed:
                                # 在事件循环中设置所有任务完成事件
                                asyncio.create_task(self._set_all_tasks_completion_event())
    
    async def _set_task_completion_event(self, task_id: str):
        """在事件循环中设置任务完成事件"""
        if task_id in self.task_completion_events:
            self.task_completion_events[task_id].set()
    
    async def _set_all_tasks_completion_event(self):
        """在事件循环中设置所有任务完成事件"""
        self.all_tasks_completion_event.set()
                        
    async def _check_heartbeats(self):
        """检查执行器心跳"""
        while True:
            try:
                async with self.lock:
                    current_time = datetime.now()
                    for executor_id, executor in list(self.executors.items()):
                        if (current_time - executor.last_heartbeat).seconds > 60:
                            executor.is_active = False
                            logger.warning(f"执行器 {executor_id} 心跳超时")
                            
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"检查心跳时出错: {e}")
                await asyncio.sleep(10)
                
    async def wait_until_finished(self, task_id: Optional[str] = None, timeout: Optional[float] = None) -> Optional[Union[Task, List[Task]]]:
        """
        等待任务完成并返回任务对象
        
        Args:
            task_id: 要等待的任务ID，如果为None则等待所有任务完成
            timeout: 超时时间（秒），如果为None则无限等待
            
        Returns:
            如果指定了task_id，则返回完成的任务对象，如果超时则返回None
            如果task_id为None，则返回所有完成的任务列表，如果超时则返回None
        """
        try:
            if task_id is None:
                # 等待所有任务完成
                if not self.tasks:
                    logger.info("没有任务需要等待")
                    return []
                
                # 等待所有任务完成事件
                if timeout is not None:
                    await asyncio.wait_for(self.all_tasks_completion_event.wait(), timeout)
                else:
                    await self.all_tasks_completion_event.wait()
                
                # 返回所有任务
                return list(self.tasks.values())
            else:
                # 等待单个任务完成
                if task_id not in self.tasks:
                    logger.warning(f"任务 {task_id} 不存在")
                    return None
                
                # 如果任务已经完成，直接返回
                task = self.tasks[task_id]
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    return task
                
                # 等待任务完成事件
                if timeout is not None:
                    await asyncio.wait_for(self.task_completion_events[task_id].wait(), timeout)
                else:
                    await self.task_completion_events[task_id].wait()
                
                # 返回完成的任务
                return self.tasks[task_id]
                
        except asyncio.TimeoutError:
            logger.warning(f"等待任务完成超时")
            return None