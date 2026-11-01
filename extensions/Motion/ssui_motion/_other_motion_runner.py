"""Minimal native inference adapters; no Gradio, FBX SDK or FlashAttention."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def msflow(args, models, device):
    import numpy as np
    import torch
    from omegaconf import OmegaConf
    from models.MMDiT_xyz import build_model
    from utils.raw_joint_utils import load_raw_joint_mean_std
    source = Path(sys.modules['models.MMDiT_xyz'].__file__).resolve().parents[1]
    os.chdir(source)
    run_dir = models / 'checkpoints/t2m/MMDiT_xyz_pretrained'
    saved = OmegaConf.to_container(OmegaConf.load(run_dir / 'config.yaml'), resolve=True)
    # Match the official XYZ demo's configuration resolution without importing
    # its video renderer (matplotlib / ffmpeg are unnecessary for SSUI playback).
    kwargs = {key: saved[key] for key in ('max_length', 'is_causal', 'num_frame_per_block',
              'use_single_token_refiner', 'noise_scale', 'flow_output_type', 'flow_t_sampler',
              'patch_size', 'stride_size', 'raw_joint_count', 'raw_joint_dim') if key in saved}
    kwargs.update(input_dim=66, sigma_min=0.01, sampler='myheun2')
    kwargs['bert_model_path'] = str(models / 'text-encoder')
    model = build_model(**kwargs)
    checkpoint = torch.load(run_dir / 'model/latest.tar', map_location='cpu', weights_only=False)
    missing, unexpected = model.load_state_dict(checkpoint['ema_model'], strict=False)
    if unexpected or any(not key.startswith('clip_model.') for key in missing):
        raise RuntimeError(f'MSFlow checkpoint mismatch: missing={missing}, unexpected={unexpected}')
    mean, std = load_raw_joint_mean_std('t2m', normalization=saved.get('raw_normalization', 'shared_xyz'))
    model.eval().to(device)
    torch.manual_seed(args.seed)
    with torch.no_grad():
        generated = model.generate([args.prompt], torch.tensor([round(args.duration * 20)], device=device), cond_scale=3.0)
    positions = generated.detach().cpu().numpy().reshape(-1, 22, 3) * std + mean
    names = ['pelvis', 'left_hip', 'right_hip', 'spine1', 'left_knee', 'right_knee', 'spine2',
             'left_ankle', 'right_ankle', 'spine3', 'left_foot', 'right_foot', 'neck',
             'left_collar', 'right_collar', 'head', 'left_shoulder', 'right_shoulder',
             'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist']
    parents = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]
    return positions, names, parents, 20, {'posed_joints': positions}, 'MSFlow-MMDiT-XYZ'


def hy_motion(args, models, device):
    import numpy as np
    import torch
    import yaml
    import hymotion.pipeline.motion_diffusion as module
    from hymotion.utils.loaders import load_object
    from hymotion.network.text_encoders import text_encoder
    os.chdir(Path(module.__file__).resolve().parents[2])
    text_encoder.LLM_ENCODER_LAYOUT['qwen3']['module_path'] = str(models / 'qwen')
    text_encoder.SENTENCE_EMB_LAYOUT['clipl']['module_path'] = str(models / 'clip')
    folder = models / 'motion/HY-Motion-1.0-Lite'
    checkpoint_path = folder / 'latest.ckpt'
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f'Missing trained weights: {checkpoint_path}')
    with open(folder / 'config.yml', encoding='utf-8') as stream:
        cfg = yaml.safe_load(stream)
    pipeline = load_object(cfg['train_pipeline'], cfg['train_pipeline_args'],
                           network_module=cfg['network_module'], network_module_args=cfg['network_module_args'])
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    missing, unexpected = pipeline.load_state_dict(checkpoint['model_state_dict'], strict=False)
    # The official checkpoint excludes WoodenMesh's static geometry buffers;
    # those are loaded from the pinned source assets, not learned parameters.
    static_buffers = {'body_model.v_template', 'body_model.j_template', 'body_model.skin_weights',
                      'body_model.skin_indices', 'body_model.parents'}
    if set(missing) - static_buffers or unexpected:
        raise RuntimeError(f'HY-Motion checkpoint mismatch: missing={missing}, unexpected={unexpected}')
    del checkpoint
    pipeline.text_encoder = load_object(pipeline._text_encoder_module, pipeline._text_encoder_cfg)
    pipeline.eval().to(device)
    with torch.no_grad():
        result = pipeline.generate(args.prompt, [args.seed], args.duration, cfg_scale=5.0)
    arrays = {key: value[0].detach().cpu().numpy() for key, value in result.items() if isinstance(value, torch.Tensor)}
    positions = arrays['keypoints3d']
    names = pipeline.body_model.joint_names
    parents = pipeline.body_model.parents.cpu().tolist()
    parents[0] = -1
    arrays['posed_joints'] = positions
    return positions, names, parents, pipeline.output_mesh_fps, arrays, 'HY-Motion-1.0-Lite'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', choices=['msflow', 'hy-motion'])
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--duration', type=float, default=4)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.prompt.strip() or not 2 <= args.duration <= (9 if args.engine == 'msflow' else 10):
        parser.error('A nonempty prompt and a supported duration are required')
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    import numpy as np
    import torch
    device = ('cuda' if torch.cuda.is_available() else 'cpu') if args.device == 'auto' else args.device
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable')
    key = args.engine.upper().replace('-', '_')
    models = Path(os.environ.get(f'SSUI_{key}_MODEL_DIR', ROOT / 'models' / args.engine)).resolve()
    result = (msflow if args.engine == 'msflow' else hy_motion)(args, models, device)
    positions, names, parents, fps, arrays, model = result
    if positions.ndim != 3 or positions.shape[1:] != (len(names), 3) or not len(positions) or not np.isfinite(positions).all():
        raise ValueError('Model generated invalid motion')
    if len(parents) != len(names) or not np.isfinite(fps) or fps <= 0:
        raise ValueError('Invalid skeleton metadata')
    metadata = {'model': model, 'inference_device': device, 'torch': torch.__version__, 'prompt': args.prompt, 'seed': args.seed}
    np.savez(str(output) + '.npz', **arrays, fps=fps)
    manifest = {'schema': 'ssui.motion.clip/v1', 'fps': float(fps), 'units': 'meters',
                'coordinate_system': 'Y-up;+Z-forward', 'joint_names': names, 'parents': parents,
                'positions': positions.tolist(), 'metadata': metadata}
    Path(str(output) + '.motion.json').write_text(json.dumps(manifest, allow_nan=False), encoding='utf-8')
    print(f'Saved {model}: {positions.shape} at {fps} FPS on {device}', flush=True)


if __name__ == '__main__':
    main()
