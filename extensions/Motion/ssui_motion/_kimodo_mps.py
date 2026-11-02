"""SSUI's memory-bounded MPS entry point for the pinned Kimodo release."""
import argparse
import gc
import json
import os
from pathlib import Path
import time
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]


def model_root():
    return Path(os.environ.get('SSUI_KIMODO_MODEL_DIR',ROOT/'models/kimodo-mac')).resolve()


class CachedEncoder:
    def __init__(self,texts,features,lengths,device):
        self.texts, self.features, self.lengths, self.device = texts,features,lengths,device

    def __call__(self,texts):
        if texts != self.texts:
            raise ValueError('Cached Kimodo embedding does not match requested text')
        return self.features.to(self.device),self.lengths


def load_motion_model(name,texts,features,lengths,device='mps'):
    from kimodo import load_model
    # Instantiate in host memory only to convert float64 statistics/schedule
    # buffers before placement. All learned model inference runs on the GPU.
    model=load_model(name,device='cpu',text_encoder=CachedEncoder(texts,features,lengths,device))
    if device=='mps': model.float()
    model.to(device)
    model.device=device
    return model


def generate_motion(prompt, features, lengths, output, model_name='Kimodo-SOMA-RP-v1.1',
                    duration=2.,steps=20,seed=42,export_bvh=False,device='mps'):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    model=load_motion_model(model_name,[prompt],features,lengths,device)
    assert all(p.device.type==torch.device(device).type for p in model.denoiser.parameters())
    torch.manual_seed(seed)
    with torch.inference_mode():
        result=model([prompt],[int(duration*model.fps)],num_denoising_steps=steps,
                     num_samples=1,multi_prompt=True,post_processing=False,return_numpy=True)
    motion={k:(v[0] if isinstance(v,np.ndarray) and v.ndim and v.shape[0]==1 else v) for k,v in result.items()}
    for value in motion.values():
        if isinstance(value,np.ndarray) and np.issubdtype(value.dtype,np.number) and not np.isfinite(value).all():
            raise RuntimeError('Kimodo produced nonfinite motion values')
    from kimodo.exports.motion_io import save_kimodo_npz
    save_kimodo_npz(str(output)+'.npz',motion)
    skeleton=model.output_skeleton
    if export_bvh:
        if 'somaskel' not in skeleton.name:
            raise ValueError('BVH export requires a SOMA model')
        from kimodo.exports.bvh import save_motion_bvh
        from kimodo.skeleton import global_rots_to_local_rots
        rotation=torch.from_numpy(result['global_rot_mats'][0]).to(device)
        position=torch.from_numpy(result['posed_joints'][0]).to(device)
        save_motion_bvh(str(output)+'.bvh',global_rots_to_local_rots(rotation,skeleton),
                        position[:,skeleton.root_idx,:],skeleton=skeleton,fps=model.fps,standard_tpose=False)
    report=dict(device=device,torch=torch.__version__,seconds=time.monotonic()-started,prompt=prompt,
                duration=duration,steps=steps,seed=seed,fps=model.fps,
                shapes={k:list(v.shape) for k,v in motion.items() if isinstance(v,np.ndarray)})
    Path(str(output)+'_report.json').write_text(json.dumps(report,indent=2)+'\n')
    # Rendering metadata contains no learned parameters.
    Path(str(output)+'_skeleton.json').write_text(json.dumps(dict(parents=skeleton.joint_parents.cpu().tolist(),fps=model.fps)))
    print(json.dumps(report,indent=2),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prompt')
    parser.add_argument('--model',default='Kimodo-SOMA-RP-v1.1')
    parser.add_argument('--duration',type=float,default=2.)
    parser.add_argument('--diffusion_steps',type=int,default=20)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--output',required=True)
    parser.add_argument('--no-postprocess',action='store_true')
    parser.add_argument('--bvh',action='store_true')
    args=parser.parse_args()
    if not torch.backends.mps.is_available(): raise RuntimeError('MPS is unavailable')
    if not 0 < args.duration <= 20 or args.diffusion_steps < 1:
        parser.error('duration must be in (0,20] and diffusion_steps positive')
    root=model_root()
    base=Path(os.environ.get('SSUI_KIMODO_TEXT_ENCODER_BASE',root/'text-base'))
    adapter=Path(os.environ.get('SSUI_KIMODO_TEXT_ENCODER_ADAPTER',root/'text-adapter'))
    if not (base/'model.safetensors').is_file() or not (adapter/'adapter_model.safetensors').is_file():
        raise RuntimeError('Missing local LLM2Vec safetensors. Run yarn test:kimodo:smoke --download-only; see Motion/Readme.md for encoder provenance.')
    os.environ['CHECKPOINT_DIR']=str(root)
    from _kimodo_streaming import encode_streamed
    text_device=os.environ.get('TEXT_ENCODER_DEVICE','mps')
    if text_device=='auto': text_device='mps'
    features,lengths=encode_streamed([args.prompt],base,adapter,device=text_device)
    generate_motion(args.prompt,features,lengths,args.output,args.model,args.duration,args.diffusion_steps,args.seed,args.bvh)


if __name__=='__main__': main()
