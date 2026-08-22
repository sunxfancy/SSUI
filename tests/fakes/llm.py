"""Transformers LLM 的确定性假实现。"""


class FakeTokenizer:
    @staticmethod
    def from_pretrained(*args, **kwargs):
        return FakeTokenizer()


class FakeLLM:
    @staticmethod
    def from_pretrained(*args, **kwargs):
        return FakeLLM()

    def eval(self):
        return self

    def chat(self, tokenizer, text, history=None):
        return "这是一个模拟回复", history or []
