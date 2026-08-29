import unittest
import os
import tempfile
from fastapi.testclient import TestClient
from server.app import create_app
from tests.mocks import (
    MockConfigService,
    MockModelService,
    MockScriptService,
    MockWebSocketService,
    MockTaskScheduler,
)

class TestServer(unittest.TestCase):
    def setUp(self):
        self.mock_config_service = MockConfigService()
        self.mock_model_service = MockModelService()
        self.mock_script_service = MockScriptService()
        self.mock_websocket_service = MockWebSocketService()
        self.mock_scheduler = MockTaskScheduler()

        # 通过依赖注入组装应用，不再 patch 模块全局变量
        self.app = create_app(
            config_service=self.mock_config_service,
            model_service=self.mock_model_service,
            scheduler=self.mock_scheduler,
            script_service=self.mock_script_service,
            websocket_service=self.mock_websocket_service,
        )
        self.client = TestClient(self.app)
        self.tmp_dir = tempfile.mkdtemp()

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

    def test_get_config(self):
        response = self.client.get("/config/")
        self.assertEqual(response.status_code, 200)
        self.mock_config_service.get_config.assert_called_once()

    def test_scan_models(self):
        response = self.client.post(
            f"/config/scan_models/test_client",
            json={"scan_dir": self.tmp_dir}
        )
        self.assertEqual(response.status_code, 200)
        self.mock_model_service.scan_models.assert_called_once()

    def test_available_models(self):
        response = self.client.get("/api/available_models")
        self.assertEqual(response.status_code, 200)
        self.mock_config_service.get_installed_models.assert_called_once()

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

    def test_compile_flow(self):
        response = self.client.post(
            "/api/flow/compile", params={"flow_path": "test.flow"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["script_path"], "test.flow.py")
        self.mock_script_service.compile_flow.assert_called_once_with("test.flow")

    def test_file(self):
        test_file_path = os.path.join(self.tmp_dir, "test.txt")
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write("hello")
        response = self.client.get(f"/file?path={test_file_path}")
        self.assertEqual(response.status_code, 200)


