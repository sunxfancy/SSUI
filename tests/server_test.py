import unittest
from tests.utils import should_run_slow_tests
import os
from unittest.mock import patch
from tests.mocks import (
    MockConfigService,
    MockModelService,
    MockScriptService,
    MockWebSocketService,
    MockTaskScheduler,
)

class TestServer(unittest.TestCase):
    def setUp(self):
        # 创建mock对象
        self.mock_config_service = MockConfigService()
        self.mock_model_service = MockModelService()
        self.mock_script_service = MockScriptService()
        self.mock_websocket_service = MockWebSocketService()
        self.mock_scheduler = MockTaskScheduler()

        # 使用patch替换所有service
        self.patches = [
            patch('server.server.config_service', self.mock_config_service),
            patch('server.server.model_service', self.mock_model_service),
            patch('server.server.script_service', self.mock_script_service),
            patch('server.server.websocket_service', self.mock_websocket_service),
            patch('server.server.scheduler', self.mock_scheduler),
        ]
        
        # 启动所有patches
        for p in self.patches:
            p.start()
        
        # 导入app（在patch之后）
        from server.server import app
        from fastapi.testclient import TestClient
        self.client = TestClient(app)

    def tearDown(self):
        # 停止所有patches
        for p in self.patches:
            p.stop()

    def test_version(self):
        response = self.client.get("/api/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, '"2.0.0"')

    def test_device(self):
        response = self.client.get("/api/device")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, '"cuda"')

    def test_config(self):
        test_config = {
            "test_key": "test_value"
        }
        response = self.client.post("/config/", json=test_config)
        self.assertEqual(response.status_code, 200)
        self.mock_config_service.update_config.assert_called_once_with(test_config)

    def test_scan_models(self):
        test_scan_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources"))
        response = self.client.post(
            f"/config/scan_models/test_client",
            json={"scan_dir": test_scan_dir}
        )
        self.assertEqual(response.status_code, 200)
        self.mock_model_service.scan_models.assert_called_once()

    def test_available_models(self):
        response = self.client.get("/api/available_models")
        self.assertEqual(response.status_code, 200)
        self.mock_model_service.get_available_models.assert_called_once()

    def test_extensions(self):
        response = self.client.get("/api/extensions")
        self.assertEqual(response.status_code, 200)

    def test_prepare(self):
        test_script = "test_script.py"
        test_callable = "test_function"
        response = self.client.post(
            "/api/prepare",
            params={"script_path": test_script, "callable": test_callable}
        )
        self.assertEqual(response.status_code, 200)
        self.mock_script_service.prepare_script.assert_called_once()

    def test_execute(self):
        test_script = "test_script.py"
        test_callable = "test_function"
        test_params = {"param1": "value1"}
        test_details = {"detail1": "value1"}
        
        response = self.client.post(
            "/api/execute",
            params={
                "script_path": test_script,
                "callable": test_callable
            },
            json={
                "params": test_params,
                "details": test_details
            }
        )
        self.assertEqual(response.status_code, 200)
        self.mock_script_service.execute_script.assert_called_once()

    def test_file(self):
        test_file_path = "test.txt"
        response = self.client.get(f"/file?path={test_file_path}")
        self.assertEqual(response.status_code, 200)


