"""Run the pinned upstream CLI, then emit SSUI's native motion manifest."""
import importlib
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    import ardy
    import numpy as np
    import torch
    from ardy.skeleton import build_skeleton

    loading = importlib.import_module('ardy.model.load_model')
    requested = os.environ.get('SSUI_ARDY_DEVICE', 'auto')
    if requested not in ('auto', 'cuda', 'cpu'):
        raise ValueError(f'Unsupported ARDY device: {requested}')
    device = 'cuda' if requested == 'auto' and torch.cuda.is_available() else ('cpu' if requested == 'auto' else requested)
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    # The pinned upstream CLI selects its tensor device from this probe.
    # Keep its masks/length tensors on CPU when the caller explicitly asks for it.
    if device == 'cpu':
        torch.cuda.is_available = lambda: False
    base = os.environ.get('SSUI_ARDY_TEXT_ENCODER_BASE')
    adapter = os.environ.get('SSUI_ARDY_TEXT_ENCODER_ADAPTER')
    preset = loading.TEXT_ENCODER_PRESETS['llm2vec']['kwargs']
    if base:
        preset['base_model_name_or_path'] = base
        # Match official Llama 3 Instruct framing for the previously documented
        # merged MNTP snapshot. Other overrides retain upstream tokenization.
        if 'Llama-3-8B-Instruct-LLM2Vec-mntp-merged' in base:
            from ardy.model.llm2vec import LLM2Vec
            LLM2Vec.prepare_for_tokenization = lambda self, text: '<|start_header_id|>user<|end_header_id|>\n\n' + text.strip() + '<|eot_id|>'
    if adapter:
        preset['peft_model_name_or_path'] = adapter
    import ardy.model
    original_load = ardy.model.load_model
    metadata = {'model': sys.argv[sys.argv.index('--model') + 1], 'torch': torch.__version__,
                'text_encoder_base': base or 'official', 'postprocessed': False}

    def load_model(*args, **kwargs):
        kwargs['device'] = device
        model = original_load(*args, **kwargs)
        metadata['inference_device'] = str(next(model.denoiser.parameters()).device)
        return model

    ardy.model.load_model = load_model
    cli = Path(ardy.__file__).resolve().parents[1] / 'scripts/generate.py'
    try:
        runpy.run_path(str(cli), run_name='__main__')
    finally:
        ardy.model.load_model = original_load
    stem = sys.argv[sys.argv.index('--output') + 1]
    with np.load(stem + '.npz', allow_pickle=False) as data:
        positions = data['posed_joints']
        fps = float(data['fps'])
    if positions.ndim != 3 or not len(positions) or positions.shape[-1] != 3 or not np.isfinite(positions).all():
        raise ValueError('ARDY generated invalid joint positions')
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError('ARDY generated invalid FPS')
    skeleton = build_skeleton(positions.shape[1])
    manifest = {'schema': 'ssui.motion.clip/v1', 'fps': fps, 'units': 'meters',
                'coordinate_system': 'Y-up;+Z-forward', 'metadata': metadata,
                'joint_names': skeleton.bone_order_names, 'parents': skeleton.joint_parents.tolist(),
                'positions': positions.tolist()}
    Path(stem + '.motion.json').write_text(json.dumps(manifest, allow_nan=False), encoding='utf-8')


if __name__ == '__main__':
    main()
