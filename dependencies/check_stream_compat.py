"""Real tiny-model generation checks without downloading weights/tokenizers."""
import threading
import torch
from transformers import GPT2Config, GPT2LMHeadModel
from transformers_stream_generator.main import init_stream_support, StreamGenerationConfig

torch.set_num_threads(1)
torch.manual_seed(7)
model = GPT2LMHeadModel(GPT2Config(vocab_size=32, n_positions=32, n_ctx=32,
    n_embd=16, n_layer=1, n_head=2, bos_token_id=1, eos_token_id=None, pad_token_id=0)).eval()
inputs = torch.tensor([[1, 3, 4], [1, 5, 6]])
expected = model.generate(inputs, max_new_tokens=4, do_sample=False)
expected_beam = model.generate(inputs[:1], max_new_tokens=4, do_sample=False, num_beams=2)
torch.manual_seed(17)
expected_sample = model.generate(inputs[:1], max_new_tokens=3, do_sample=True, top_k=4)
init_stream_support()
init_stream_support()
assert torch.equal(model.generate(inputs, max_new_tokens=4, do_sample=False), expected)
assert torch.equal(model.generate(inputs[:1], max_new_tokens=4, do_sample=False, num_beams=2), expected_beam)
tokens = list(model.generate(inputs, max_new_tokens=4, do_sample=False, do_stream=True))
assert len(tokens) == 4 and torch.equal(torch.stack(tokens, dim=1), expected[:, 3:])
cfg = StreamGenerationConfig(max_new_tokens=3, do_sample=True, do_stream=True,
    pad_token_id=0, eos_token_id=None, top_k=4)
a = list(model.generate(inputs[:1], generation_config=cfg, seed=17))
b = list(model.generate(inputs[:1], generation_config=cfg, seed=17))
assert torch.equal(torch.stack(a), torch.stack(b))
assert torch.equal(torch.stack(a, dim=1), expected_sample[:, 3:])
try:
    list(model.generate(inputs, max_new_tokens=2, do_stream=True, invalid_ssui_argument=True))
except ValueError as error:
    assert 'invalid_ssui_argument' in str(error)
else:
    raise AssertionError('Worker exception was not propagated')
stream = model.generate(inputs[:1], max_new_tokens=20, do_stream=True)
next(stream)
stream.close()
assert not any(t.name == 'ssui-token-stream' and t.is_alive() for t in threading.enumerate())
try:
    model.generate(inputs, do_stream=True, num_beams=2)
except ValueError:
    pass
else:
    raise AssertionError('Unsupported streaming beam search must fail explicitly')
print('Tiny GPT-2: normal generation, batched greedy streaming, seeded sampling, errors and cancellation passed')
