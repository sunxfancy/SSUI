import asyncio
import datetime
import os
from fastapi.encoders import jsonable_encoder
import websockets
import json
from typing import Dict, Optional, Union
import logging
import sys

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)

# 添加extensions目录到sys.path
for dir in os.listdir(os.path.join(project_root, "extensions")):
    yaml_path = os.path.join(project_root, "extensions", dir, "ssextension.yaml")
    if os.path.exists(yaml_path):
        sys.path.append(os.path.join(project_root, "extensions", dir))


from ss_executor.loader import SSLoader, search_project_root
from ssui.base import Image
from ss_executor.sandbox import Sandbox
from ss_executor.model import KillMessage, TaskStatus, Task, ExecutorRegister, RegisterResponse, UpdateStatus, TaskResult, ExeMessage
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Executor:
    def __init__(self, scheduler_url: str = "ws://localhost:5000/"):
        self.scheduler_url = scheduler_url
        self.current_task: Optional[Task] = None
        self.is_running = True
        
    async def connect(self):
        """连接到调度器服务器"""
        while self.is_running:
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
        while self.is_running:
            try:
                # 使用ExeMessage解析消息
                async for message in websocket:
                    logger.info(f"收到消息: {message}")
                    exe_message = ExeMessage.validate_json(message, strict=True)
                    if isinstance(exe_message, Task):
                        await self._handle_task(websocket, exe_message)
                    elif isinstance(exe_message, UpdateStatus):
                        logger.info(f"收到更新状态消息: {exe_message}")
                    elif isinstance(exe_message, KillMessage):
                        logger.info(f"收到停止消息")
                        self.is_running = False
                        return
                    else:
                        logger.error(f"收到未知消息类型: {exe_message}")
            except Exception as e:
                logger.error(f"处理消息时出错: {e} \n{traceback.format_exc()}")
                break
                
    async def _handle_task(self, websocket, task: Task):
        """处理单个任务"""
        logger.info(f"开始执行任务 {task.task_id}")
        self.current_task = task
        try:
            # 发送任务开始状态
            status_update = UpdateStatus(
                task_id=task.task_id,
                status=TaskStatus.RUNNING
            )
            await websocket.send(status_update.model_dump_json())
            
            # 执行任务
            loader = SSLoader(use_sandbox=task.use_sandbox)
            loader.load(task.script)
            loader.Execute()

            if task.is_prepare:
                # 执行prepare pass
                result = loader.GetConfig(task.callable)
                print("执行器结果：")
                print(result)
            else:
                # 执行execute pass
                def convert_param(param: dict): 
                    name = param['function']
                    params = param['params']

                    # 动态导入并获取属性,支持任意层级的包/模块/类/函数访问
                    parts = name.split('.')
                    current = __import__(parts[0])
                    for part in parts[1:]:
                        current = getattr(current, part)
                    return current(**params)

                def find_callable(loader: SSLoader, callable: str):
                    for func, param_types, return_type in loader.callables:
                        if func.__name__ == callable:
                            return func, param_types, return_type
                    raise ValueError(f"未找到可调用函数: {callable}")
                
                func, param_types, return_type = find_callable(loader, task.callable)
                print(task.script, task.callable, task.params, task.details)
                new_params = {}
                for name, param in task.params.items():
                    print(name, param)
                    new_params[name] = convert_param(param)

                def convert_return(result):
                    if isinstance(result, tuple):
                        return [convert_return(r) for r in result]
                    
                    if isinstance(result, Image):
                        current_time = datetime.datetime.now()
                        project_root = search_project_root(os.path.dirname(task.script))
                        output_dir = os.path.join(project_root, "output")
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)
                        path = os.path.join(output_dir, "image_" + current_time.strftime("%Y%m%d%H%M%S") + ".png")
                        result._image.save(path)
                        return {"type": "image", "path": path}
                # 注入配置
                loader.config._update = task.details
                # 执行
                result = func(**new_params)

                # 确保返回一个数组
                if not isinstance(result, tuple):
                    result = (result,)

                result = convert_return(result)

            # 发送任务完成状态和结果
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=jsonable_encoder(result)
            )
            await websocket.send(task_result.model_dump_json())
            
        except Exception as e:
            # 发送任务失败状态
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e) + '\n' + traceback.format_exc()
            )
            await websocket.send(task_result.model_dump_json())
            
        finally:
            self.current_task = None
            
def main():
    print("executor_main.py 启动")
    import ssui
    import ssui_image
    async def _start():
        executor = Executor()
        await executor.connect()
    asyncio.run(_start())

if __name__ == "__main__":
    main()