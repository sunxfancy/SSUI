"""Numerical tests executed in the independent Kimodo environment."""
import gc
import tempfile
from pathlib import Path
import torch
from safetensors.torch import save_file
from transformers import AutoTokenizer, LlamaConfig
from peft import LoraConfig, get_peft_model
from kimodo.model.llm2vec.models.bidirectional_llama import LlamaBiModel
from kimodo.model.llm2vec.llm2vec import LLM2Vec
from _kimodo_streaming import build_streaming_encoder


def check(root):
    assert torch.backends.mps.is_available()
    torch.manual_seed(19)
    # Tiny, nonzero LoRA model: same official forward/tokenization as 8B,
    # enough to compare CPU, ordinary MPS and streamed MPS without 16GB weights.
    with tempfile.TemporaryDirectory(prefix='kimodo-stream-test-') as temp:
        base, adapter = Path(temp)/'base',Path(temp)/'adapter'
        base.mkdir()
        config=LlamaConfig(vocab_size=128256,hidden_size=32,intermediate_size=64,
                           num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,
                           max_position_embeddings=256,use_cache=False)
        config._attn_implementation='sdpa'
        config._name_or_path='meta-llama/Meta-Llama-3-8B-Instruct'
        model=LlamaBiModel(config).eval()
        config.save_pretrained(base)
        save_file(model.state_dict(),str(base/'model.safetensors'))
        tokenizer=AutoTokenizer.from_pretrained(root/'models/kimodo-mac/text-base')
        tokenizer.pad_token=tokenizer.eos_token
        tokenizer.padding_side='left'
        tokenizer.save_pretrained(base)
        model=get_peft_model(model,LoraConfig(r=4,lora_alpha=8,lora_dropout=0.,target_modules=['q_proj','v_proj']))
        with torch.no_grad():
            for name,p in model.named_parameters():
                if 'lora_B' in name: p.normal_(std=.03)
        model.save_pretrained(adapter,save_embedding_layers=False)
        ordinary=LLM2Vec(model,tokenizer).eval()
        prompts=['A person walks forward.','A person raises both arms.']
        with torch.inference_mode():
            cpu=ordinary.encode(prompts,batch_size=1,show_progress_bar=False,device='cpu')
            mps=ordinary.encode(prompts,batch_size=1,show_progress_bar=False,device='mps')
            streamed=build_streaming_encoder(base,adapter,dtype=torch.float32)
            result=streamed.encode(prompts,batch_size=1,show_progress_bar=False,device='mps')
        torch.testing.assert_close(mps,cpu,rtol=1e-4,atol=1e-5)
        torch.testing.assert_close(result,mps,rtol=1e-5,atol=1e-6)
        assert all(p.device.type=='meta' for p in streamed.model.parameters())
        print('Streaming exact-shape output; max vs regular MPS:',float((result-mps).abs().max()),flush=True)
        with torch.no_grad():
            for name,p in model.named_parameters():
                if 'lora_' not in name: p.data=p.data.to(torch.bfloat16)
        with torch.inference_mode():
            bf16=ordinary.encode(prompts,batch_size=1,show_progress_bar=False,device='mps')
            streamed_bf16=build_streaming_encoder(base,adapter,dtype=torch.bfloat16)
            actual_bf16=streamed_bf16.encode(prompts,batch_size=1,show_progress_bar=False,device='mps')
        torch.testing.assert_close(actual_bf16,bf16,rtol=0,atol=0)
        print('BF16 streamed encoder exactly matches regular MPS',flush=True)
        del ordinary,streamed,streamed_bf16,model
    gc.collect()
    torch.mps.empty_cache()
    # Official trained root-stage transformer, identical input on CPU/MPS.
    import os
    from _kimodo_mps import load_motion_model
    os.environ['CHECKPOINT_DIR']=str(root/'models/kimodo-mac')
    model=load_motion_model('Kimodo-SOMA-RP-v1.1',['test'],torch.zeros(1,1,4096),[1],device='cpu')
    block=model.denoiser.model.root_model if hasattr(model.denoiser,'model') else model.denoiser.denoiser.root_model
    block.float()
    dim=block.input_linear.in_features
    inputs=[torch.randn(1,12,dim),torch.ones(1,12,dtype=torch.bool),torch.randn(1,1,4096),
            torch.ones(1,1,dtype=torch.bool),torch.tensor([10]),torch.zeros(1)]
    with torch.inference_mode():
        expected=block(*inputs)
        block.to('mps')
        actual=block(*[x.to('mps') for x in inputs]).cpu()
    torch.testing.assert_close(actual,expected,rtol=2e-3,atol=2e-4)
    print('Real trained Kimodo root block CPU/MPS max error:',float((actual-expected).abs().max()),flush=True)
