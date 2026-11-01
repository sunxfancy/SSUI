from typing import Optional, Tuple, List
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation import GenerationConfig
from ssui.config import SSUIConfig
from ssui.annotation import param
from ssui.controller import Random, Slider

class QwenModel:
    def __init__(
        self,
        model_path: str = "",
        model: Optional[AutoModelForCausalLM] = None,
        tokenizer: Optional[AutoTokenizer] = None,
    ):
        self.model_path = model_path
        self.model = model
        self.tokenizer = tokenizer

    def getModel(self):
        return self.model, self.tokenizer

    @staticmethod
    def load(model_path: str = "Qwen/Qwen-7B-Chat"):
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            trust_remote_code=True
        ).eval()
        return QwenModel(model_path, model, tokenizer)

@param("temperature", Slider(0.0, 2.0, 0.1), default=0.7)
@param("max_length", Slider(100, 2048, 100), default=2048)
@param("top_p", Slider(0.0, 1.0, 0.1), default=0.9)
def Chat(
    config: SSUIConfig,
    model: QwenModel,
    prompt: str,
    history: Optional[List[Tuple[str, str]]] = None,
):
    if config.is_prepare():
        return "", []

    print("Chat executed")
    print("temperature:", config["temperature"])
    print("max_length:", config["max_length"])
    print("top_p:", config["top_p"])

    model_obj, tokenizer = model.getModel()

    # Set generation config
    generation_config = GenerationConfig(
        temperature=config["temperature"],
        max_length=config["max_length"],
        top_p=config["top_p"],
    )

    # Generate response
    if callable(getattr(model_obj, "chat", None)):
        response, new_history = model_obj.chat(
            tokenizer, prompt, history=history, generation_config=generation_config
        )
    else:
        messages = []
        for question, answer in history or []:
            messages.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ])
        messages.append({"role": "user", "content": prompt})
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model_obj.device)
        with torch.inference_mode():
            output = model_obj.generate(
                **inputs,
                generation_config=generation_config,
                do_sample=config["temperature"] > 0,
                pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
            )
        response = tokenizer.decode(output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        new_history = [*(history or []), (prompt, response)]

    return response, new_history
