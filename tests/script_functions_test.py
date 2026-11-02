import os
import unittest

from server.script_service import ScriptService


class ScriptFunctionsTest(unittest.TestCase):
    def test_restricted_annotations_resolve_models_lists_and_tuples(self):
        root = os.path.dirname(os.path.dirname(__file__))
        functions = ScriptService(None).get_script_functions(os.path.join(root, "examples", "basic", "workflow-sd1.py"))
        self.assertNotIn("error", functions)
        self.assertEqual(functions["txt2img"].params["model"], "ssui_image.SD1.SD1Model")
        self.assertEqual(functions["txt2imgWithRef"].returns, ["ssui.base.Image", "ssui.base.Image"])
        self.assertEqual(functions["txt2imgWithLora"].params["loras"], "typing.List[ssui_image.SD1.SD1Lora]")

    def test_pose_tuple_return_is_available_to_browser(self):
        root = os.path.dirname(os.path.dirname(__file__))
        functions = ScriptService(None).get_script_functions(os.path.join(root, "examples", "advance", "workflow-pose.py"))
        self.assertNotIn("error", functions)
        self.assertEqual(functions["video_to_skeleton"].returns, ["ssui.base.Video", "ssui.base.SkeletonAnimation"])
