"""Small real-weight Kimodo MPS generation with separate text/motion stages."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CHILD = ROOT/'.venv/kimodo/bin/python'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workflow',action='store_true')
    parser.add_argument('--download-only',action='store_true')
    parser.add_argument('--stage',choices=['encode','motion','all','probe','check'],default='all')
    parser.add_argument('--prompt',default='A person walks forward at a relaxed pace.')
    parser.add_argument('--duration',type=float,default=2.)
    parser.add_argument('--steps',type=int,default=20)
    parser.add_argument('--output',type=Path,default=ROOT/'output/kimodo-mac')
    parser.add_argument('--models',type=Path,default=ROOT/'models/kimodo-mac')
    args=parser.parse_args()
    if args.workflow:
        sys.path[:0]=[str(ROOT),str(ROOT/'extensions/Motion')]
        from ss_executor.loader import SSLoader
        from ssui.base import MotionClip, Prompt
        import shutil
        import numpy as np
        os.environ['SSUI_KIMODO_MODEL_DIR']=str(args.models.resolve())
        os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='0'
        loader=SSLoader()
        loader.load(str(ROOT/'examples/advance/workflow-motion.py'))
        loader.Execute()
        loader.GetConfig('txt2motion_kimodo')
        loader.config.set_prepared(False)
        config=loader.config('Kimodo Text To Motion')
        for key,value in dict(device='mps',text_encoder_device='mps',duration=args.duration,
                              diffusion_steps=args.steps,seed=42,export_bvh=True).items(): config[key]=value
        fn=next(fn for fn,_,_ in loader.callables if fn.__name__=='txt2motion_kimodo')
        started=time.monotonic()
        clip=fn(Prompt(args.prompt))
        result=Path(clip.npz_path if isinstance(clip,MotionClip) else clip)
        with np.load(result,allow_pickle=False) as data:
            assert data['posed_joints'].shape[0]==round(args.duration*30)
            assert np.isfinite(data['posed_joints']).all()
        args.output.mkdir(parents=True,exist_ok=True)
        stem=str(result.with_suffix(''))
        for suffix in ('.npz','.bvh','_report.json','_skeleton.json'):
            shutil.copy2(stem+suffix,args.output/('motion'+suffix))
        (args.output/'workflow_report.json').write_text(json.dumps(dict(seconds=time.monotonic()-started,
                   workflow='txt2motion_kimodo',device='mps',source=str(result)),indent=2)+'\n')
        print('SSUI Kimodo workflow passed:',result,flush=True)
        return
    if Path(sys.prefix).resolve() != CHILD.parent.parent.resolve():
        env = dict(os.environ,PYTORCH_ENABLE_MPS_FALLBACK='0')
        raise SystemExit(subprocess.call([str(CHILD),__file__,*sys.argv[1:]],env=env))
    sys.path.insert(0,str(ROOT/'extensions/Motion/ssui_motion'))
    if args.download_only:
        from _kimodo_weights import download_weights
        download_weights(args.models)
        return
    import torch
    from safetensors import safe_open
    if args.stage=='check':
        from kimodo_runtime_check import check
        check(ROOT)
        return
    if args.stage=='probe':
        print('Torch',torch.__version__,'MPS',torch.backends.mps.is_available())
        for path in [args.models/'text-base/model.safetensors',args.models/'text-adapter/adapter_model.safetensors']:
            if path.exists():
                with safe_open(path,framework='pt') as f: print(path.name, list(f.keys())[:8])
        return
    assert torch.backends.mps.is_available()
    if args.duration <= 0 or args.steps < 1: parser.error('duration and steps must be positive')
    args.output.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'extensions/Motion/ssui_motion'))
    if args.stage in ('all','encode'):
        from _kimodo_streaming import encode_streamed
        start=time.monotonic()
        feats,lengths=encode_streamed([args.prompt],args.models/'text-base',args.models/'text-adapter')
        assert torch.isfinite(feats).all()
        torch.save(dict(prompt=args.prompt,features=feats,lengths=lengths),args.output/'text.pt')
        print('Text encoded',tuple(feats.shape),'seconds',time.monotonic()-start,flush=True)
    if args.stage in ('all','motion'):
        from _kimodo_mps import generate_motion
        saved=torch.load(args.output/'text.pt',weights_only=True)
        if saved['prompt']!=args.prompt: raise ValueError('Saved embedding prompt does not match')
        os.environ['CHECKPOINT_DIR']=str(args.models)
        generate_motion(args.prompt,saved['features'],saved['lengths'],args.output/'motion',
                        duration=args.duration,steps=args.steps,export_bvh=True)



if __name__=='__main__': main()
