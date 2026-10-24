import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import torch

from ssui.config import SSUIConfig
from ssui_llm.Qwen import Chat, QwenModel


class QwenChatTest(unittest.TestCase):
    def test_legacy_chat_contract_is_preserved(self):
        model = SimpleNamespace(chat=Mock(return_value=("answer", [("hello", "answer")])))
        result = Chat(SSUIConfig()("Chat"), QwenModel(model=model, tokenizer=object()), "hello")
        self.assertEqual(result, ("answer", [("hello", "answer")]))
        self.assertEqual(model.chat.call_args.kwargs["history"], None)

    def test_modern_chat_formats_history_decodes_only_new_tokens_and_preserves_zero_pad_id(self):
        class Inputs(dict):
            def to(self, _device):
                return self

            @property
            def input_ids(self):
                return self["input_ids"]

        inputs = Inputs(input_ids=torch.tensor([[1, 2]]), attention_mask=torch.ones((1, 2), dtype=torch.long))
        tokenizer = Mock(return_value=inputs, pad_token_id=0, eos_token_id=4)
        tokenizer.apply_chat_template.return_value = "formatted conversation"
        tokenizer.decode.return_value = "new answer"
        model = SimpleNamespace(device=torch.device("cpu"), generate=Mock(return_value=torch.tensor([[1, 2, 3]])))
        history = [("old question", "old answer")]
        result = Chat(SSUIConfig()("Chat"), QwenModel(model=model, tokenizer=tokenizer), "new question", history)
        self.assertEqual(result, ("new answer", [*history, ("new question", "new answer")]))
        self.assertEqual(history, [("old question", "old answer")])
        self.assertEqual(model.generate.call_args.kwargs["pad_token_id"], 0)
        self.assertEqual(tokenizer.decode.call_args.args[0].tolist(), [3])
        self.assertEqual(len(tokenizer.apply_chat_template.call_args.args[0]), 3)
