import unittest
from unittest.mock import patch

from tests.fakes.llm import FakeLLM, FakeTokenizer


class TestLLMWorkflow(unittest.TestCase):
    """给定假 LLM 输出，验证对话接口能跑通。"""

    @patch("transformers.AutoModelForCausalLM", FakeLLM)
    @patch("transformers.AutoTokenizer", FakeTokenizer)
    def test_llm(self):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen-7B-Chat", trust_remote_code=True
        )
        model = (
            AutoModelForCausalLM.from_pretrained(
                "Qwen/Qwen-7B-Chat", device_map="auto", trust_remote_code=True
            )
            .eval()
        )

        response, history = model.chat(tokenizer, "你好", history=None)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        self.assertIsInstance(history, list)

        response2, history = model.chat(tokenizer, "讲个故事", history=history)
        self.assertTrue(len(response2) > 0)
