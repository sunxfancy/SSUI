import os
import sys
import unittest

from ss_executor.loader import SSLoader


class MotionExtensionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        motion_extension = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "extensions", "Motion")
        )
        if motion_extension not in sys.path:
            sys.path.insert(0, motion_extension)

    def test_kimodo_node_can_be_prepared_in_sandbox(self):
        script_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "examples",
                "advance",
                "workflow-motion.py",
            )
        )
        loader = SSLoader(use_sandbox=True)
        loader.load(script_path)
        loader.Execute()

        config = loader.GetConfig("txt2motion_kimodo")
        node_config = config["Kimodo Text To Motion"]

        self.assertEqual(node_config["model"]["default"], "Kimodo-SOMA-RP-v1.1")
        self.assertEqual(node_config["text_encoder_device"]["default"], "cuda")


if __name__ == "__main__":
    unittest.main()
