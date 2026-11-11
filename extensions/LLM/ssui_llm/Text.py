"""Text generation on SSUI's shared PyTorch/Transformers runtime."""

import math
from typing import List, Optional, Tuple

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForSeq2SeqLM, AutoTokenizer

from backend.util.devices import TorchDevice
from ssui.annotation import param
from ssui.config import SSUIConfig
from ssui.controller import Slider


class TextModel:
    def __init__(self, model_path: str = "", model=None, tokenizer=None):
        self.model_path = model_path
        self.model = model
        self.tokenizer = tokenizer

    def getModel(self):
        return self.model, self.tokenizer

    @staticmethod
    def load(model_path: str, lora_path: str = "", lora_weight: float = 1.0,
             device: str = "auto", local_files_only: bool = False):
        """Load a native Transformers text model and optional PEFT LoRA directory.

        Paths may be local directories or Hugging Face repository IDs. No custom
        repository code, separate service, or alternate Torch build is loaded.
        Each load owns its model; applying a LoRA cannot mutate another node.
        """
        if not math.isfinite(lora_weight):
            raise ValueError("LoRA weight must be finite")
        selected = TorchDevice.choose_torch_device() if device == "auto" else torch.device(device)
        options = dict(trust_remote_code=False, local_files_only=local_files_only)
        tokenizer = AutoTokenizer.from_pretrained(model_path, **options)
        model_config = AutoConfig.from_pretrained(model_path, **options)
        model_class = AutoModelForSeq2SeqLM if model_config.is_encoder_decoder else AutoModelForCausalLM
        model = model_class.from_pretrained(
            model_path, config=model_config, torch_dtype=TorchDevice.choose_torch_dtype(selected), **options
        )
        if lora_path and lora_weight != 0:
            from peft import PeftConfig, PeftModel
            from peft.tuners.lora import LoraLayer

            adapter_config = PeftConfig.from_pretrained(lora_path, **options)
            if adapter_config.peft_type != "LORA":
                raise ValueError("TextModel requires a PEFT LoRA adapter")
            if adapter_config.use_dora and lora_weight != 1:
                raise ValueError("DoRA adapters currently require lora_weight=1")
            model = PeftModel.from_pretrained(
                model, lora_path, config=adapter_config, is_trainable=False,
                adapter_name="source", **options
            )
            if lora_weight != 1:
                # Scale the adapter update without duplicating or merging weights.
                for layer in model.modules():
                    if isinstance(layer, LoraLayer):
                        layer.set_scale("source", lora_weight)
        model.to(selected).eval()
        return TextModel(model_path, model, tokenizer)


def _generate(model, text, max_new_tokens, temperature, top_p, *, templated=False):
    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    if not math.isfinite(temperature) or temperature < 0:
        raise ValueError("temperature must be finite and non-negative")
    if not 0 < top_p <= 1:
        raise ValueError("top_p must be in (0, 1]")
    obj, tokenizer = model.getModel()
    inputs = tokenizer(text, return_tensors="pt", add_special_tokens=not templated).to(obj.device)
    options = dict(max_new_tokens=max_new_tokens, do_sample=temperature > 0,
                   pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    if temperature > 0:
        options.update(temperature=temperature, top_p=top_p)
    with torch.inference_mode():
        output = obj.generate(**inputs, **options)
    start = 0 if getattr(getattr(obj, "config", None), "is_encoder_decoder", False) else inputs["input_ids"].shape[1]
    return tokenizer.decode(output[0, start:], skip_special_tokens=True)


@param("temperature", Slider(0.0, 2.0, 0.1), default=0.7)
@param("max_new_tokens", Slider(1, 8192, 1), default=512)
@param("top_p", Slider(0.01, 1.0, 0.01), default=0.9)
def Generate(config: SSUIConfig, model: TextModel, prompt: str) -> str:
    """Plain continuation for base models, code and completion tasks."""
    if config.is_prepare():
        return ""
    return _generate(model, prompt, config["max_new_tokens"], config["temperature"], config["top_p"])


@param("temperature", Slider(0.0, 2.0, 0.1), default=0.7)
@param("max_new_tokens", Slider(1, 8192, 1), default=512)
@param("top_p", Slider(0.01, 1.0, 0.01), default=0.9)
def Chat(config: SSUIConfig, model: TextModel, prompt: str,
         history: Optional[List[Tuple[str, str]]] = None,
         system_prompt: str = "") -> Tuple[str, List[Tuple[str, str]]]:
    if config.is_prepare():
        return "", []
    _, tokenizer = model.getModel()
    if not tokenizer.chat_template:
        raise ValueError("This tokenizer has no chat template; use Generate for plain text completion")
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for question, answer in history or []:
        messages.extend([{"role": "user", "content": question},
                         {"role": "assistant", "content": answer}])
    messages.append({"role": "user", "content": prompt})
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    response = _generate(model, text, config["max_new_tokens"], config["temperature"], config["top_p"], templated=True)
    return response, [*(history or []), (prompt, response)]
