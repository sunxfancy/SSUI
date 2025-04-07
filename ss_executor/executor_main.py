import asyncio
import websockets
import json
from typing import Dict, Optional, Union
import logging
from .sandbox import Sandbox
from .model import TaskStatus, Task, ExecutorRegister, RegisterResponse, UpdateStatus, TaskResult, ExeMessage
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Executor:
    def __init__(self, scheduler_url: str = "ws://localhost:5000/"):
        self.scheduler_url = scheduler_url
        self.sandbox = Sandbox()
        self.current_task: Optional[Task] = None
        
    async def connect(self):
        """连接到调度器服务器"""
        while True:
            try:
                async with websockets.connect(self.scheduler_url) as websocket:
                    # 发送注册消息
                    register_message = ExecutorRegister(
                        host="localhost",  # 这里应该使用实际的host
                        port=0,  # 这里应该使用实际的port
                        max_tasks=1,
                        capabilities=[]
                    )
                    await websocket.send(register_message.model_dump_json())
                    logger.info("已连接到调度器服务器")

                    # 接收注册响应
                    message = await websocket.recv()
                    try:
                        response = ExeMessage.validate_json(message)
                        if isinstance(response, RegisterResponse):
                            logger.info(f"{response.message}")
                        else:
                            logger.error(f"注册失败: 收到未知消息类型")
                    except Exception as e:
                        logger.error(f"解析注册响应失败: {e}")
                    
                    # 开始接收任务
                    await self._handle_messages(websocket)
                    
            except Exception as e:
                logger.error(f"连接错误: {e}")
                await asyncio.sleep(5)  # 等待5秒后重试
                
    async def _handle_messages(self, websocket):
        """处理来自调度器的消息"""
        while True:
            try:
                # 使用ExeMessage解析消息
                async for message in websocket:
                    logger.info(f"收到消息: {message}")
                    exe_message = ExeMessage.validate_json(message, strict=True)
                    if isinstance(exe_message, Task):
                        await self._handle_task(websocket, exe_message)
                    elif isinstance(exe_message, UpdateStatus):
                        logger.info(f"收到更新状态消息: {exe_message}")
                    else:
                        logger.error(f"收到未知消息类型: {exe_message}")
            except Exception as e:
                logger.error(f"处理消息时出错: {e} \n{traceback.format_exc()}")
                break
                
    async def _handle_task(self, websocket, task: Task):
        """处理单个任务"""
        try:
            logger.info(f"开始执行任务 {task.task_id}")
            self.current_task = task
            
            # 发送任务开始状态
            status_update = UpdateStatus(
                task_id=task.task_id,
                status=TaskStatus.RUNNING
            )
            await websocket.send(status_update.model_dump_json())
            
            # 执行任务
            result = await self.sandbox.execute(task.script)
            
            # 发送任务完成状态和结果
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result
            )
            await websocket.send(task_result.model_dump_json())
            
        except Exception as e:
            # 发送任务失败状态
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e)
            )
            await websocket.send(task_result.model_dump_json())
            
        finally:
            self.current_task = None
            
def main():
    async def _start():
        executor = Executor()
        await executor.connect()
    asyncio.run(_start())

