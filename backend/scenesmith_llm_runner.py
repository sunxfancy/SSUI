"""Run a local Qwen scene planner in the native ARM64 CUDA model environment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    catalog = request["assets"]
    prompt = (
        "Return JSON only. Use exactly the keys schema and objects. Each object has id, asset, "
        "position, rotation_deg, scale. Positions are [x,y,z] in meters with Z up. "
        "Example: assets=[\"sofa\",\"plant\"], request='plant to the left of sofa' => "
        "{\"schema\":\"ssui.scene-layout/1\",\"objects\":["
        "{\"id\":\"sofa-1\",\"asset\":\"sofa\",\"position\":[0,0,0],\"rotation_deg\":0,\"scale\":1},"
        "{\"id\":\"plant-1\",\"asset\":\"plant\",\"position\":[-2,0,0],\"rotation_deg\":0,\"scale\":1}]}. "
        "Use only IDs from available assets.\n"
        f"Available assets (use their id fields): {json.dumps(catalog, ensure_ascii=False)}\n"
        f"Request: {request['prompt']}\nJSON:"
    )
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, device_map="auto", trust_remote_code=False, local_files_only=True
    ).eval()
    if callable(getattr(model, "chat", None)):
        with torch.inference_mode():
            answer, _ = model.chat(tokenizer, prompt, history=None)
    else:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            output = model.generate(**inputs, do_sample=False, max_new_tokens=1024)
        answer = tokenizer.decode(output[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
    Path(args.output).write_text(answer, encoding="utf-8")


if __name__ == "__main__":
    main()
