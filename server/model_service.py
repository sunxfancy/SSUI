import os
import threading
import asyncio
import uuid
import aioshutil
import json
from typing import List, Dict, Any, Callable
from server.models import ModelScanResult, ModelInfo
from server.resource_manager import ModelInfoCache
from backend.model_manager.config import ModelType
from server.config_service import ConfigService


class ModelService:
    def __init__(self, resources_dir: str):
        self.resources_dir = resources_dir
        self.config_service = ConfigService(
            os.path.join(resources_dir, "ssui_config.json")
        )

    async def scan_models(
        self,
        scan_dir: str,
        client_id: str,
        request_uuid: str,
        callback: Callable[[str, str, Dict[str, Any]], None],
        finish_callback: Callable[[str, str, Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        """
        扫描指定目录下的模型文件

        Args:
            scan_dir: 要扫描的目录路径
            client_id: 客户端ID
            request_uuid: 请求UUID
            callback: 回调函数，用于发送扫描进度
            finish_callback: 完成回调函数

        Returns:
            Dict[str, Any]: 包含扫描结果的字典
        """

        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        def scan_target_dir():
            try:
                scaned_models = []
                # 获取已安装的模型列表
                installed_models = self.config_service.get_installed_models()
                installed_paths = [model.path for model in installed_models]

                if os.path.exists(scan_dir):
                    for dirpath, dirnames, filenames in os.walk(scan_dir):
                        # 首先检查当前目录是否是一个模型
                        try:
                            if dirpath in installed_paths or ModelInfoCache.get(
                                dirpath
                            ):
                                # 如果当前目录是一个模型，则跳过扫描其子目录
                                callback_data = {
                                    "path": dirpath,
                                    "name": os.path.basename(dirpath),
                                    "installed": dirpath in installed_paths,
                                }
                                scaned_models.append(callback_data)
                                loop.call_soon_threadsafe(
                                    callback,
                                    client_id,
                                    request_uuid,
                                    {"model_found": callback_data},
                                )
                                # 清空dirnames列表，这样os.walk就不会继续扫描子目录
                                dirnames.clear()
                                continue
                        except Exception:
                            # 如果当前目录不是模型，继续正常扫描
                            pass

                        for filename in filenames:
                            if (
                                filename.endswith(".safetensors")
                                or filename.endswith(".pt")
                                or filename.endswith(".ckpt")
                            ):
                                model_path = os.path.join(dirpath, filename)
                                try:
                                    if not model_path in installed_paths:
                                        ModelInfoCache.get(model_path)
                                    callback_data = {
                                        "path": model_path,
                                        "name": filename,
                                        "installed": model_path in installed_paths,
                                    }
                                    scaned_models.append(callback_data)
                                    loop.call_soon_threadsafe(
                                        callback,
                                        client_id,
                                        request_uuid,
                                        {"model_found": callback_data},
                                    )
                                except Exception as e:
                                    continue

                # 发送完成回调
                finish_data = {"models": scaned_models}
                loop.call_soon_threadsafe(
                    finish_callback, client_id, request_uuid, finish_data
                )

            except Exception as e:
                error_data = {"message": str(e)}
                loop.call_soon_threadsafe(
                    finish_callback, client_id, request_uuid, error_data
                )

        # 在新线程中执行扫描
        thread = threading.Thread(target=scan_target_dir)
        thread.start()

        return {"message": "Model scan started"}

    def get_model_info(self, model_path: str):
        return ModelInfoCache.get(model_path)

    async def install_model(self, model_path: str, create_softlink: bool = False):
        model_path = os.path.normpath(model_path)
        if not os.path.exists(model_path):
            return {"type": "error", "message": "Model path not found"}

        model_config = ModelInfoCache.get(model_path)
        if model_config is None:
            return {"type": "error", "message": "Model can not be loaded"}

        tags = []
        tags.append(model_config.base)
        if model_config.type == ModelType.LoRA:
            tags.append("lora")
        elif model_config.type == ModelType.T5Encoder:
            tags.append("t5")
        elif model_config.type == ModelType.VAE:
            tags.append("vae")

        if create_softlink:
            # 创建软链接
            return {
                "type": "success",
                "message": "Models installed",
                "path": model_path,
                "name": model_config.name,
                "description": model_config.description,
                "base_model": model_config.base,
                "tags": tags,
            }
        else:
            # 复制文件
            new_model_path = os.path.join(self.resources_dir, model_config.name)
            await aioshutil.copy(model_path, new_model_path)
            ModelInfoCache.set(model_path, model_config)
            return {
                "type": "success",
                "message": "Models installed",
                "path": new_model_path,
                "name": model_config.name,
                "description": model_config.description,
                "base_model": model_config.base,
                "tags": tags,
            }

    async def hf_download(
        self,
        repo_id: str,
        local_dir: str,
        client_id: str,
        request_uuid: str,
        callback: Callable[[str, str, Dict[str, Any]], None],
        finish_callback: Callable[[str, str, Dict[str, Any]], None],
    ):
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        def download_thread():
            from huggingface_hub import snapshot_download
            from tqdm.auto import tqdm

            class download_progress_callback(tqdm):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.client_id = client_id
                    self.request_uuid = request_uuid

                def update(self, n=1):
                    super().update(n)
                    print(self.n, self.total)
                    loop.call_soon_threadsafe(
                        callback,
                        self.client_id,
                        self.request_uuid,
                        "download_progress",
                        {
                            "progress": self.n / self.total * 100 if self.total else 0,
                            "current": self.n,
                            "total": self.total,
                            "speed": self.format_dict.get("rate", 0),
                            "eta": self.format_dict.get("eta", 0),
                        },
                    )

                def close(self):
                    super().close()
                    loop.call_soon_threadsafe(
                        finish_callback,
                        self.client_id,
                        self.request_uuid,
                    )

            snapshot_download(
                repo_id=repo_id,
                local_dir=local_dir,
                tqdm_class=download_progress_callback,
            )

        # 在新线程中执行下载
        thread = threading.Thread(target=download_thread)
        thread.start()

        return {"message": "Model scan started"}

    async def download_file(
        self,
        url: str,
        local_dir: str,
        client_id: str,
        request_uuid: str,
        callback: Callable[[str, str, Dict[str, Any]], None],
        finish_callback: Callable[[str, str, Dict[str, Any]], None],
    ):
        """下载任意 URL 文件到本地目录，并通过 websocket 回调整下载进度。

        回调约定与 scan_models 一致：callback(client_id, request_uuid, {name: data})。
        """
        loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        def download_thread():
            import urllib.request
            from urllib.parse import urlparse

            try:
                os.makedirs(local_dir, exist_ok=True)
                filename = os.path.basename(urlparse(url).path) or "model.bin"
                target = os.path.join(local_dir, filename)
                print(f"downloading {url} -> {target}", flush=True)

                def report(progress: float, current: float, total: float):
                    loop.call_soon_threadsafe(
                        callback,
                        client_id,
                        request_uuid,
                        {
                            "download_progress": {
                                "progress": progress,
                                "current": current,
                                "total": total,
                            }
                        },
                    )

                def hook(blocks: int, block_size: int, total_size: int):
                    if total_size > 0:
                        report(
                            min(blocks * block_size / total_size * 100, 100),
                            blocks * block_size,
                            total_size,
                        )

                urllib.request.urlretrieve(url, target, reporthook=hook)
                loop.call_soon_threadsafe(
                    finish_callback,
                    client_id,
                    request_uuid,
                )
            except Exception as e:
                print(f"下载失败: {e}", flush=True)
                loop.call_soon_threadsafe(
                    callback,
                    client_id,
                    request_uuid,
                    {"download_error": str(e)},
                )
                loop.call_soon_threadsafe(
                    finish_callback,
                    client_id,
                    request_uuid,
                    {"error": str(e)},
                )

        thread = threading.Thread(target=download_thread)
        thread.start()

        return {"message": "Download started"}
