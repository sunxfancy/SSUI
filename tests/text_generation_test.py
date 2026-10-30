import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import torch

from ssui.config import SSUIConfig
from ssui_llm.Text import Chat, Generate, TextModel


class TextGenerationTest(unittest.TestCase):
    def setUp(self):
        class Inputs(dict):
            def to(self, device):
                return self
        self.tokenizer = Mock(pad_token_id=0, eos_token_id=4, chat_template="template")
        self.tokenizer.return_value = Inputs(input_ids=torch.tensor([[1, 2]]))
        self.tokenizer.decode.return_value = "answer"
        self.tokenizer.apply_chat_template.return_value = "formatted"
        self.raw = SimpleNamespace(device="cpu", generate=Mock(return_value=torch.tensor([[1, 2, 3]])))
        self.model = TextModel(model=self.raw, tokenizer=self.tokenizer)
        self.config = SSUIConfig()("text")

    def test_chat_preserves_history_and_decodes_new_tokens(self):
        history = [("old", "reply")]
        result = Chat(self.config, self.model, "hello", history, "be concise")
        self.assertEqual(result, ("answer", [*history, ("hello", "answer")]))
        self.assertEqual(history, [("old", "reply")])
        self.assertEqual(self.tokenizer.decode.call_args.args[0].tolist(), [3])
        self.assertFalse(self.tokenizer.call_args.kwargs["add_special_tokens"])
        self.assertEqual(self.tokenizer.apply_chat_template.call_args.args[0][0]["role"], "system")
        self.assertEqual(self.raw.generate.call_args.kwargs["max_new_tokens"], 512)
        self.assertEqual(self.raw.generate.call_args.kwargs["pad_token_id"], 0)

    def test_greedy_completion(self):
        self.config["temperature"] = 0
        Generate(self.config, self.model, "hello")
        options = self.raw.generate.call_args.kwargs
        self.assertFalse(options["do_sample"])
        self.assertNotIn("temperature", options)
        self.assertNotIn("top_p", options)
        self.assertTrue(self.tokenizer.call_args.kwargs["add_special_tokens"])

    def test_prepare_does_not_run_model(self):
        self.config.set_prepared()
        self.assertEqual(Chat(self.config, None, "hello"), ("", []))
        self.assertEqual(Generate(self.config, None, "hello"), "")

    def test_encoder_decoder_output_does_not_drop_prompt_length(self):
        self.raw.config = SimpleNamespace(is_encoder_decoder=True)
        Generate(self.config, self.model, "hello")
        self.assertEqual(self.tokenizer.decode.call_args.args[0].tolist(), [1, 2, 3])

    def test_missing_template_is_actionable(self):
        self.tokenizer.chat_template = None
        with self.assertRaisesRegex(ValueError, "use Generate"):
            Chat(self.config, self.model, "hello")

    def test_invalid_generation_options(self):
        for key, value in [("temperature", -1), ("max_new_tokens", 0), ("top_p", 0)]:
            config = SSUIConfig()("text")
            config[key] = value
            with self.assertRaises(ValueError):
                Generate(config, self.model, "hello")
        self.raw.generate.assert_not_called()

    def test_workflow_prepares_in_executor(self):
        from ss_executor.loader import SSLoader
        loader = SSLoader()
        loader.load(str(Path(__file__).parents[1] / "examples/basic/workflow-text.py"))
        loader.Execute()
        self.assertIsNotNone(loader.GetConfig("chat"))
        self.assertIsNotNone(loader.GetConfig("complete"))


class TextLoRAIntegrationTest(unittest.TestCase):
    """Actual Transformers + PEFT round trip, with tiny local random weights."""

    def test_local_model_weighted_adapter_and_unmodified_base(self):
        from peft import LoraConfig, get_peft_model
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from transformers import GPT2Config, GPT2LMHeadModel, PreTrainedTokenizerFast

        with tempfile.TemporaryDirectory() as temp:
            base, adapter = Path(temp) / "base", Path(temp) / "adapter"
            model = GPT2LMHeadModel(GPT2Config(vocab_size=8, n_positions=32, n_embd=8, n_layer=1, n_head=1,
                                             bos_token_id=1, eos_token_id=2, pad_token_id=0))
            model.save_pretrained(base)
            tokenizer = PreTrainedTokenizerFast(
                tokenizer_object=Tokenizer(WordLevel({"[PAD]": 0, "[BOS]": 1, "[EOS]": 2, "[UNK]": 3, "hello": 4}, unk_token="[UNK]")),
                pad_token="[PAD]", bos_token="[BOS]", eos_token="[EOS]", unk_token="[UNK]")
            tokenizer.save_pretrained(base)
            adapted = get_peft_model(model, LoraConfig(task_type="CAUSAL_LM", r=2, lora_alpha=2, target_modules=["c_attn"]))
            for name, parameter in adapted.named_parameters():
                if "lora_" in name:
                    torch.nn.init.constant_(parameter, 0.1)
            adapted.save_pretrained(adapter)
            loaded = TextModel.load(str(base), str(adapter), -0.5, device="cpu", local_files_only=True)
            layer = loaded.model.base_model.model.transformer.h[0].attn.c_attn
            original_layer = adapted.base_model.model.transformer.h[0].attn.c_attn
            torch.testing.assert_close(layer.get_delta_weight("source"), original_layer.get_delta_weight("default") * -0.5)
            config = SSUIConfig()("text")
            config["max_new_tokens"] = 2
            config["temperature"] = 0
            self.assertIsInstance(Generate(config, loaded, "hello"), str)
            plain = TextModel.load(str(base), device="cpu", local_files_only=True)
            self.assertFalse(any("lora_" in name for name, _ in plain.model.named_parameters()))
            zero = TextModel.load(str(base), "nonexistent-adapter", 0, device="cpu", local_files_only=True)
            self.assertFalse(any("lora_" in name for name, _ in zero.model.named_parameters()))

    def test_qwen_llama_and_encoder_decoder_local_roundtrips(self):
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from transformers import (LlamaConfig, LlamaForCausalLM, Qwen2Config, Qwen2ForCausalLM,
                                  T5Config, T5ForConditionalGeneration, PreTrainedTokenizerFast)
        models = [
            LlamaForCausalLM(LlamaConfig(vocab_size=8, hidden_size=16, intermediate_size=32,
                                        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)),
            Qwen2ForCausalLM(Qwen2Config(vocab_size=8, hidden_size=16, intermediate_size=32,
                                        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)),
            T5ForConditionalGeneration(T5Config(vocab_size=8, d_model=16, d_kv=8, d_ff=32,
                                                num_layers=1, num_heads=2, decoder_start_token_id=0)),
        ]
        for model in models:
            with self.subTest(model=model.config.model_type), tempfile.TemporaryDirectory() as temp:
                model.save_pretrained(temp)
                tokenizer = PreTrainedTokenizerFast(
                    tokenizer_object=Tokenizer(WordLevel({"[PAD]": 0, "[EOS]": 1, "[UNK]": 2, "hello": 3}, unk_token="[UNK]")),
                    pad_token="[PAD]", eos_token="[EOS]", unk_token="[UNK]",
                    model_input_names=["input_ids", "attention_mask"])
                tokenizer.save_pretrained(temp)
                loaded = TextModel.load(temp, device="cpu", local_files_only=True)
                config = SSUIConfig()("text")
                config["max_new_tokens"] = 2
                config["temperature"] = 0
                self.assertIsInstance(Generate(config, loaded, "hello"), str)
