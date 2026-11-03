"""Launch the pinned LTX runtime, requiring GPU execution on Apple Silicon."""
import os
import argparse
import runpy
import sys
import json
from pathlib import Path
from contextlib import contextmanager, nullcontext
from unittest.mock import patch


def _encode_mps_without_cache(self, prompts):
    """Match the pinned LTX encoder contract, without generation KV caches."""
    import torch
    if not prompts:
        return []
    tokenized = [self.tokenizer.tokenize_with_weights(t)["gemma"] for t in prompts]
    ids = torch.tensor([[t for t, _ in pairs] for pairs in tokenized], device="mps")
    mask = torch.tensor([[w for _, w in pairs] for pairs in tokenized], device="mps")
    outputs = self.model.model(input_ids=ids, attention_mask=mask,
                               output_hidden_states=True, use_cache=False)
    return [(tuple(h[i:i + 1] for h in outputs.hidden_states), mask[i:i + 1])
            for i in range(len(prompts))]


def _dispose_gemma_offload(self):
    from accelerate.hooks import remove_hook_from_module
    from ltx_core.model.disposable import Disposable
    remove_hook_from_module(self.model.model.language_model.embed_tokens)
    Disposable.dispose(self)


def _teardown_text_streaming(self):
    # The caller retains its `text_encoder` local after leaving the context.
    # Upstream cleanup returns buffers to the pools but keeps the pools alive.
    type(self).teardown(self)
    self._provider = None


def _offload_gemma_embedding(encoder):
    """Unified Gemma encode does not use lm_head; share its CPU weight with offload."""
    import torch
    from accelerate import cpu_offload
    from types import MethodType
    if getattr(getattr(encoder.model, "config", None), "model_type", None) != "gemma4_unified":
        return
    embedding = encoder.model.model.language_model.embed_tokens
    host_weight = embedding.weight.detach().to("cpu")
    # Both originally reference the same GPU allocation. Release both references.
    encoder.model.lm_head.weight = torch.nn.Parameter(host_weight, requires_grad=False)
    cpu_offload(embedding, execution_device=torch.device("mps"),
                state_dict={"weight": host_weight})
    encoder.encode = MethodType(_encode_mps_without_cache, encoder)
    encoder.dispose = MethodType(_dispose_gemma_offload, encoder)
    torch.mps.synchronize()
    torch.mps.empty_cache()
    print(f"Gemma embedding offload: {host_weight.nbytes / 1024**3:.2f} GiB; MPS lookup, no KV cache", flush=True)


def _dispose_sequential_offload(self):
    from accelerate.hooks import remove_hook_from_module
    from ltx_core.model.disposable import Disposable
    remove_hook_from_module(self, recurse=True)
    Disposable.dispose(self)


def _chunk_feature_projection(self, hidden_states, attention_mask, padding_side="left"):
    """V2 normalization/projection is independent per token; bound activation size."""
    import torch
    from ltx_core.text_encoders.gemma.feature_extractor import FeatureExtractorV2
    video, audio = [], []
    for start in range(0, attention_mask.shape[1], 64):
        chunk = (tuple(h[:, start:start + 64] for h in hidden_states)
                 if isinstance(hidden_states, (tuple, list)) else hidden_states[:, start:start + 64])
        v, a = FeatureExtractorV2.forward(self, chunk, attention_mask[:, start:start + 64], padding_side)
        video.append(v)
        if a is not None:
            audio.append(a)
    return torch.cat(video, dim=1), torch.cat(audio, dim=1) if audio else None


def _build_mps_embeddings_processor(self):
    import torch
    from accelerate import cpu_offload
    from types import MethodType
    model = self._embeddings_processor_builder.build(device=torch.device("cpu"), dtype=self._dtype).eval()
    from ltx_core.text_encoders.gemma.feature_extractor import FeatureExtractorV2
    feature = getattr(model, "feature_extractor", model)
    if isinstance(feature, FeatureExtractorV2):
        feature.forward = MethodType(_chunk_feature_projection, feature)
    cpu_offload(model, execution_device=torch.device("mps"), offload_buffers=True)
    model.dispose = MethodType(_dispose_sequential_offload, model)
    print("LTX embeddings processor: CPU checkpoint storage, sequential MPS computation", flush=True)
    return model


def _needed_non_block_keys(model, keys):
    expected = set(model.state_dict())
    return [(source, target) for source, target in keys if target in expected]


@contextmanager
def _bounded_disk_streaming():
    """Use one host and one MPS slot; pinned LTX otherwise allocates six slots."""
    from ltx_core.block_streaming import builder
    from ltx_pipelines.utils.blocks.prompt_encoder import PromptEncoder

    original_build = builder.StreamingModelBuilder.build
    original_load = builder.StreamingModelBuilder._load_non_block_weights

    def load_non_block(self, model, keys, device, dtype, loras):
        if device.type == "mps":
            needed = _needed_non_block_keys(model, keys)
            print(f"LTX non-block weights: keeping {len(needed)}/{len(keys)} model keys", flush=True)
            keys = needed
        return original_load(self, model, keys, device, dtype, loras)

    def build(self, device=None, dtype=None, **kwargs):
        if device is not None and device.type == "mps":
            kwargs.update(cpu_slots_count=1, gpu_slots_count=1)
        result = original_build(self, device=device, dtype=dtype, **kwargs)
        if device is not None and device.type == "mps" and self.blocks_prefix == "model.model.language_model.layers":
            _offload_gemma_embedding(result._model)
            from types import MethodType
            result.teardown = MethodType(_teardown_text_streaming, result)
            import torch
            for index, block in enumerate(result._blocks):
                if index % 10 == 0:
                    def progress(module, inputs, index=index):
                        print(f"Gemma block {index}: MPS tensors={torch.mps.current_allocated_memory() / 1024**3:.2f} GiB, "
                              f"driver={torch.mps.driver_allocated_memory() / 1024**3:.2f} GiB", flush=True)
                    result._hooks.append(block.register_forward_pre_hook(progress))
        return result

    with patch.object(builder, "_PREFETCH_DEPTH", 0), \
         patch.object(builder.StreamingModelBuilder, "build", build), \
         patch.object(builder.StreamingModelBuilder, "_load_non_block_weights", load_non_block), \
         patch.object(PromptEncoder, "_build_embeddings_processor", _build_mps_embeddings_processor):
        yield


def main():
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--module", choices=("distilled", "ti2vid_one_stage"), required=True)
    parser.add_argument("--execution-report", type=Path)
    args, remaining = parser.parse_known_args()
    import torch
    from ltx_pipelines.utils.helpers import get_device

    device = get_device()
    if device.type == "cpu":
        raise RuntimeError("LTX requires MPS or CUDA; CPU fallback is disabled")
    if device.type == "mps" and "--quantization" in remaining:
        raise ValueError("LTX MPS requires unquantized BF16 weights; select quantization=none")
    if device.type == "mps":
        torch.set_num_threads(4)
        torch.mps.set_per_process_memory_fraction(0.35)
    print(f"LTX computation device: {device}; torch {torch.__version__}", flush=True)
    observed = {}
    def check_device(module, inputs, output):
        if isinstance(module, (torch.nn.Linear, torch.nn.Embedding, torch.nn.Conv1d, torch.nn.Conv2d, torch.nn.Conv3d)):
            if isinstance(output, torch.Tensor):
                if output.device.type != device.type:
                    raise RuntimeError(f"{type(module).__name__} computed on {output.device}, expected {device}")
                name = type(module).__name__
                observed[name] = observed.get(name, 0) + 1
    hook = torch.nn.modules.module.register_module_forward_hook(check_device) if args.execution_report else None
    sys.argv = ["ltx_pipelines." + args.module, *remaining]
    try:
        with _bounded_disk_streaming() if device.type == "mps" and "disk" in remaining else nullcontext():
            runpy.run_module(sys.argv[0], run_name="__main__")
    finally:
        if hook is not None:
            hook.remove()
    if args.execution_report:
        if not observed:
            raise RuntimeError("No GPU model execution observed")
        args.execution_report.write_text(json.dumps({"device": str(device), "torch": torch.__version__,
                                                     "observed_layers": observed}, indent=2))


if __name__ == "__main__":
    main()
