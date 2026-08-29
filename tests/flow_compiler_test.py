import json
import os
import tempfile
import unittest

from flow_compiler import FlowCompileError, compile_flow_data, compile_flow_file
from ss_executor.loader import SSLoader


def identity_flow():
    return {
        "version": 1,
        "imports": [],
        "functions": [{
            "id": "identity",
            "name": "identity",
            "inputs": [{"id": "value", "name": "value", "type": "str"}],
            "outputs": [{"id": "result", "name": "result", "type": "str"}],
            "nodes": [],
            "connections": [{
                "from": {"node": "$input", "port": "value"},
                "to": {"node": "$output", "port": "result"},
            }],
        }],
    }


class TestFlowCompiler(unittest.TestCase):
    def test_compile_direct_connection(self):
        source = compile_flow_data(identity_flow(), "identity.flow")
        self.assertIn("def identity(value: str) -> str:", source)
        self.assertIn("return value", source)

    def test_compile_operator(self):
        data = identity_flow()
        data["imports"] = [{"module": "ssui", "names": ["Prompt"]}]
        data["functions"][0] = {
            "id": "make_prompt", "name": "make_prompt",
            "inputs": [{"id": "text", "name": "text", "type": "str"}],
            "outputs": [{"id": "prompt", "name": "prompt", "type": "Prompt"}],
            "nodes": [{
                "id": "create", "type": "operator", "callable": "Prompt.create",
                "inputs": ["text"], "outputs": ["prompt"],
            }],
            "connections": [
                {"from": {"node": "$input", "port": "text"}, "to": {"node": "create", "port": "text"}},
                {"from": {"node": "create", "port": "prompt"}, "to": {"node": "$output", "port": "prompt"}},
            ],
        }
        source = compile_flow_data(data)
        self.assertIn("_create_prompt = Prompt.create(text)", source)

    def test_rejects_cycles(self):
        data = identity_flow()
        function = data["functions"][0]
        function["nodes"] = [
            {"id": "a", "type": "operator", "callable": "str", "inputs": ["value"], "outputs": ["result"]},
            {"id": "b", "type": "operator", "callable": "str", "inputs": ["value"], "outputs": ["result"]},
        ]
        function["connections"] = [
            {"from": {"node": "a", "port": "result"}, "to": {"node": "b", "port": "value"}},
            {"from": {"node": "b", "port": "result"}, "to": {"node": "a", "port": "value"}},
            {"from": {"node": "a", "port": "result"}, "to": {"node": "$output", "port": "result"}},
        ]
        with self.assertRaisesRegex(FlowCompileError, "cycle"):
            compile_flow_data(data)

    def test_compiled_file_loads_as_ssui_script(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "ssproject.yaml"), "w", encoding="utf-8") as project:
                project.write("ssui_version: 1.1.5\ndependencies: []\n")
            flow_path = os.path.join(directory, "identity.flow")
            with open(flow_path, "w", encoding="utf-8") as flow:
                json.dump(identity_flow(), flow)
            loader = SSLoader()
            loader.load(compile_flow_file(flow_path))
            loader.Execute()
            self.assertEqual([item[0].__name__ for item in loader.callables], ["identity"])
