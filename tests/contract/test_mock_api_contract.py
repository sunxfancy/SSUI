import unittest
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests.mock_api.app import app
from tests.mock_api.models import ScriptMeta, TaskList, TaskUpdate, UploadResult, WebSocketUuid
from server.contract_app import create_contract_app


class MockApiContractTest(unittest.TestCase):
    def test_production_text_save_preserves_version_and_conflict(self):
        client = TestClient(create_contract_app())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text("original", encoding="utf-8")
            snapshot = client.get("/file/text", params={"path": str(path)})
            self.assertEqual(snapshot.status_code, 200)
            payload = {"path": str(path), "content": "updated", "expected_version": snapshot.json()["version"]}
            saved = client.post("/files/upload_json", json=payload)
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json()["success"])
            self.assertNotEqual(saved.json()["version"], payload["expected_version"])
            self.assertEqual(client.post("/files/upload_json", json=payload).status_code, 409)
            self.assertEqual(path.read_text(encoding="utf-8"), "updated")

    def setUp(self):
        self.client = TestClient(app)
        self.client.put("/__test__/scenario", json={"name": "happy-path"})

    def test_script_response_matches_contract(self):
        response = self.client.get("/api/script", params={"script_path": "/fixtures/demo.py"})
        self.assertEqual(response.status_code, 200)
        ScriptMeta.model_validate(response.json())

    def test_production_openapi_exposes_typed_core_responses(self):
        schema = create_contract_app().openapi()
        responses = schema["paths"]["/api/tasks"]["get"]["responses"]
        task_schema = responses["200"]["content"]["application/json"]["schema"]
        self.assertEqual(task_schema["$ref"], "#/components/schemas/TaskList")

        script_schema = schema["paths"]["/api/script"]["get"]["responses"]["200"]
        self.assertEqual(
            script_schema["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/ScriptMeta",
        )

    def test_upload_and_execute_match_component_contract(self):
        upload = self.client.post(
            "/files/upload",
            params={"script_path": "/fixtures/demo.py"},
            files={"file": ("input.png", b"png", "image/png")},
        )
        result = UploadResult.model_validate(upload.json())
        self.assertTrue(result.success)
        self.assertTrue(result.path)

        execute = self.client.post(
            "/api/execute",
            params={"script_path": "/fixtures/demo.py", "callable": "generate"},
            json={"params": {"image": {"image": result.path}}, "details": {}},
        )
        self.assertEqual(execute.status_code, 200)
        self.assertEqual(execute.json()[0]["path"], "/fixtures/generated.png")

    def test_task_rest_and_websocket_contracts(self):
        tasks = TaskList.model_validate(self.client.get("/api/tasks").json())
        self.assertEqual(tasks.items[0].id, "task-1")
        with self.client.websocket_connect("/ws") as websocket:
            WebSocketUuid.model_validate(websocket.receive_json())

        self.client.put("/__test__/scenario", json={"name": "task-lifecycle"})
        with self.client.websocket_connect("/ws") as websocket:
            WebSocketUuid.model_validate(websocket.receive_json())
            update = TaskUpdate.model_validate(websocket.receive_json())
            self.assertEqual(update.task.status, "processing")
            self.assertEqual(update.task.progress, 50)


if __name__ == "__main__":
    unittest.main()
