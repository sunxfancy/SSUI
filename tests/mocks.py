from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, List, Optional
import asyncio

class MockConfigService:
    def __init__(self):
        self.config = {}
        self.update_config = MagicMock(return_value={"status": "success"})
        self.get_installed_models = MagicMock(return_value={"status": "success"})

class MockModelService:
    def __init__(self):
        self.scan_models = AsyncMock(return_value={"status": "success"})
        self.get_model_info = AsyncMock(return_value={"name": "test_model"})
        self.install_model = AsyncMock(return_value=["model1", "model2"])

class MockScriptService:
    def __init__(self):
        self.prepare_script = AsyncMock(return_value={"status": "success"})
        self.execute_script = AsyncMock(return_value={"status": "success"})
        self.get_device_info = MagicMock(return_value="cuda")
        self.get_torch_version = MagicMock(return_value="2.0.0")

class MockWebSocketService:
    def __init__(self):
        self.connect = AsyncMock()
        self.disconnect = MagicMock()
        self.send_message = AsyncMock()
        self.send_finish = AsyncMock()
        self.stop = MagicMock()

class MockTaskScheduler:
    def __init__(self):
        self.start = AsyncMock()
        self.stop = AsyncMock()
        self.add_task = AsyncMock(return_value={"task_id": "test_task_id"})
        self.get_task_status = AsyncMock(return_value={"status": "running"})
