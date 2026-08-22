import unittest

from tests.utils import download_if_needed, should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), "需要 SSUI_RUN_MODEL_TESTS=1")
class TestLLMModel(unittest.TestCase):
    def test_llm(self):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        download_if_needed("llm")
        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen-7B-Chat", trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen-7B-Chat", device_map="auto", trust_remote_code=True
        ).eval()

        response, history = model.chat(tokenizer, "你好", history=None)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertIsInstance(history, list)
