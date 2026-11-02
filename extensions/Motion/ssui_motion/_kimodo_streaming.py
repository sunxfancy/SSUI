"""Layer-streamed LLM2Vec: original Kimodo model and PEFT arithmetic on MPS.

Safetensors are memory mapped on demand. Only one transformer block plus its
LoRA adapters resides on the GPU; no quantization or replacement embeddings.
"""
import gc
from pathlib import Path

import torch
from safetensors import safe_open
from transformers import AutoConfig, AutoTokenizer
from transformers.models.llama.modeling_llama import LlamaRotaryEmbedding
from peft import LoraConfig, get_peft_model
from kimodo.model.llm2vec.llm2vec import LLM2Vec
from kimodo.model.llm2vec.models.bidirectional_llama import LlamaBiModel


class StreamingLLM2Vec(LLM2Vec):
    def to(self, device=None, *args, **kwargs):
        # The upstream encode() calls to() twice. Bulk-moving meta parameters
        # defeats streaming; hooks own placement instead.
        if device is not None and torch.device(device) != self.execution_device:
            raise ValueError('Streaming encoder device is fixed at construction')
        return self


def build_streaming_encoder(base_dir, adapter_dir, device='mps', dtype=torch.bfloat16):
    base_dir, adapter_dir = Path(base_dir), Path(adapter_dir)
    base_file = base_dir/'model.safetensors'
    adapter_file = adapter_dir/'adapter_model.safetensors'
    config = AutoConfig.from_pretrained(base_dir)
    config._name_or_path = 'meta-llama/Meta-Llama-3-8B-Instruct'
    config.use_cache = False
    config._attn_implementation = 'sdpa'
    adapter_config = LoraConfig.from_pretrained(adapter_dir)
    with torch.device('meta'):
        base_model = LlamaBiModel(config)
        model = get_peft_model(base_model, adapter_config, low_cpu_mem_usage=True)
    # Rotary frequencies are runtime buffers, not checkpoint parameters.
    base_model.rotary_emb = LlamaRotaryEmbedding(config=config, device=device)
    with safe_open(base_file,framework='pt') as source:
        base_keys = set(source.keys())
    with safe_open(adapter_file,framework='pt') as source:
        adapter_keys = set(source.keys())

    def find_key(keys, suffix):
        matches = [k for k in keys if k == suffix or k.endswith('.'+suffix)]
        if len(matches) != 1:
            raise ValueError(f'Expected one checkpoint tensor for {suffix}, found {len(matches)}')
        return matches[0]

    handles = []
    for prefix, block in [('embed_tokens',base_model.embed_tokens),
                           *[(f'layers.{i}',layer) for i,layer in enumerate(base_model.layers)],
                           ('norm',base_model.norm)]:
        mapping = {}
        for key in block.state_dict():
            full = prefix+'.'+key
            if '.lora_' in full:
                mapping[key] = (True,find_key(adapter_keys,full.replace('.default.','.')))
            else:
                mapping[key] = (False,find_key(base_keys,full.replace('.base_layer.','.')))
        def load(module, inputs, mapping=mapping, prefix=prefix):
            state = {}
            with safe_open(base_file,framework='pt') as source, safe_open(adapter_file,framework='pt') as adapter:
                for name,(is_adapter,key) in mapping.items():
                    tensor = (adapter if is_adapter else source).get_tensor(key)
                    # PEFT promotes adapter weights to fp32 during normal load.
                    state[name] = tensor.to(device=device,dtype=torch.float32 if is_adapter else dtype)
            module.load_state_dict(state,strict=True,assign=True)
            print('LLM2Vec GPU block:',prefix,flush=True)
        def unload(module, inputs, output):
            module.to_empty(device='meta')
            if str(device).startswith('mps'):
                torch.mps.empty_cache()
        handles.append(block.register_forward_pre_hook(load))
        handles.append(block.register_forward_hook(unload,always_call=True))
    tokenizer = AutoTokenizer.from_pretrained(base_dir)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = 'left'
    encoder = StreamingLLM2Vec(model=model,tokenizer=tokenizer)
    encoder.execution_device = torch.device(device)
    encoder._stream_handles = handles
    encoder.eval()
    return encoder


def encode_streamed(texts, base_dir, adapter_dir, device='mps'):
    encoder = build_streaming_encoder(base_dir,adapter_dir,device)
    with torch.inference_mode():
        result = encoder.encode(texts,batch_size=1,show_progress_bar=False,device=device).float()
    del encoder
    gc.collect()
    if device == 'mps':
        torch.mps.empty_cache()
    return result[:,None,:], [1]*len(texts)
