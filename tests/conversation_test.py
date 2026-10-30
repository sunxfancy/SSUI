import tempfile
import unittest
from pathlib import Path
from typing import List, Optional, Tuple

from server.conversation import infer_conversation
from server.script_service import ScriptService
from ss_executor.__main__ import Executor
from fastapi.testclient import TestClient
from server.contract_app import create_contract_app


class ConversationSignatureTest(unittest.TestCase):
    def test_pair_history_typing_and_pep585(self):
        for annotation in (List[Tuple[str, str]], Optional[List[Tuple[str, str]]], list[tuple[str, str]] | None):
            with self.subTest(annotation=annotation):
                info = infer_conversation({"model": object, "prompt": str, "history": annotation, "system_prompt": str},
                                          Tuple[str, List[Tuple[str, str]]])
                self.assertEqual(info.prompt_param, "prompt")
                self.assertEqual(info.context_param, "history")
                self.assertEqual(info.context_output, 1)

    def test_string_response_accumulates_pairs(self):
        info = infer_conversation({"question": str, "previous": list[tuple[str, str]]}, str)
        self.assertIsNone(info.context_output)

    def test_text_context_roundtrip(self):
        info = infer_conversation({"message": str, "context": str | None}, tuple[str, str])
        self.assertEqual(info.context_kind, "text")

    def test_non_chat_and_ambiguous_signatures_stay_generic(self):
        cases = [
            ({"prompt": str}, str),
            ({"prompt": str, "history": list[str]}, str),
            ({"prompt": str, "context": str}, str),
            ({"first": str, "second": str, "history": list[tuple[str, str]]}, str),
            ({"prompt": str, "history": list[tuple[str, str]]}, tuple[str, int]),
            ({"prompt": str, "history": list[tuple[str, str]], "context": str}, str),
        ]
        for params, returns in cases:
            with self.subTest(params=params, returns=returns):
                self.assertIsNone(infer_conversation(params, returns))

    def test_real_metadata_and_executor_two_turns(self):
        source = '''from typing import List, Optional, Tuple
from ssui import workflow
from ssui.config import SSUIConfig
config = SSUIConfig()
@workflow
def chat(prompt: str, history: Optional[List[Tuple[str, str]]] = None) -> Tuple[str, List[Tuple[str, str]]]:
    if config.is_prepare():
        return "", []
    answer = "turn " + str(len(history or []) + 1) + ": " + prompt
    return answer, [*(history or []), (prompt, answer)]
'''
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "ssproject.yaml").write_text("ssui_version: '0.1.0'\ndependencies: []\n", encoding="utf-8")
            script = root / "chat.py"
            script.write_text(source, encoding="utf-8")
            executor = Executor()
            class LocalScheduler:
                async def run_task(self, task):
                    return executor._execute_task(task)
            service = ScriptService(LocalScheduler())
            meta = service.get_script_functions(str(script))
            self.assertEqual(meta["chat"].conversation.context_param, "history")
            self.assertIn("typing.Union[", meta["chat"].params["history"])
            app = create_contract_app()
            app.state.script_service = service
            client = TestClient(app)
            query = {"script_path": str(script), "callable": "chat"}
            wire_meta = client.get("/api/script", params=query).json()
            self.assertEqual(wire_meta["functions"]["chat"]["conversation"]["context_output"], 1)
            self.assertEqual(client.post("/api/prepare", params=query).json(), {})
            first_response = client.post("/api/execute", params=query, json={"params": {"prompt": "你好", "history": []}, "details": {}})
            self.assertEqual(first_response.status_code, 200)
            first = first_response.json()
            # Round-trip the wire representation (JSON pairs become lists).
            second = client.post("/api/execute", params=query, json={"params": {"prompt": "继续", "history": first[1]}, "details": {}}).json()
            self.assertEqual(second[0], "turn 2: 继续")
            self.assertEqual(len(second[1]), 2)
            script.write_text(source + '\n@workflow\ndef complete(prompt: str) -> str:\n    return prompt\n', encoding="utf-8")
            multiple = service.get_script_functions(str(script))
            self.assertIsNotNone(multiple['chat'].conversation)
            self.assertIsNone(multiple['complete'].conversation)

    def test_official_chat_example_advertises_conversation(self):
        path = Path(__file__).parents[1] / "examples/basic/workflow-text-chat.py"
        info = ScriptService(None).get_script_functions(str(path))["chat"]
        self.assertEqual(info.conversation.context_kind, "pairs")
