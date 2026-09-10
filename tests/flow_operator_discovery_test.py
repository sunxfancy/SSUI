import os
import tempfile
import unittest

from server.script_service import ScriptService


class FlowOperatorDiscoveryTest(unittest.TestCase):
    def test_discovers_typed_sibling_functions_without_executing_module(self):
        with tempfile.TemporaryDirectory() as directory:
            flow_path = os.path.join(directory, "pipeline.flow")
            open(flow_path, "w", encoding="utf-8").close()
            with open(os.path.join(directory, "tools.py"), "w", encoding="utf-8") as source:
                source.write(
                    "raise RuntimeError('must not execute during discovery')\n"
                    "def resize(image: str, width: int) -> tuple[str, int]:\n"
                    "    return image, width\n"
                    "def missing_annotation(value):\n    return value\n"
                )
            result = ScriptService(None).get_flow_operators(flow_path)
            operator = next(item for item in result["operators"] if item.module == "tools")
            self.assertEqual(operator.module, "tools")
            self.assertEqual(operator.params, {"image": "str", "width": "int"})
            self.assertEqual(operator.returns, ["str", "int"])

    def test_reports_non_importable_python_filenames(self):
        with tempfile.TemporaryDirectory() as directory:
            flow_path = os.path.join(directory, "pipeline.flow")
            open(flow_path, "w", encoding="utf-8").close()
            open(os.path.join(directory, "not-importable.py"), "w", encoding="utf-8").close()
            result = ScriptService(None).get_flow_operators(flow_path)
            self.assertEqual(result["errors"][0]["source"], "not-importable.py")

    def test_discovers_extension_generation_and_model_load_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            flow_path = os.path.join(directory, "pipeline.flow")
            open(flow_path, "w", encoding="utf-8").close()
            operators = ScriptService(None).get_flow_operators(flow_path)["operators"]
            names = {(item.module, item.callable) for item in operators}
            self.assertIn(("ssui_image.Flux2", "Flux2KleinModel.load"), names)
            self.assertIn(("ssui_image.Flux2", "Flux2KleinGenerate"), names)
