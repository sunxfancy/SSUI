"""TRELLIS real-weight MPS smoke; feature computation stays on the GPU."""
import argparse
import hashlib
import urllib.request
import gc
import json
import os
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'vendor'))
os.environ.setdefault('SPARSE_BACKEND', 'torch')
os.environ.setdefault('SPARSE_ATTN_BACKEND', 'sdpa')
os.environ.setdefault('ATTN_BACKEND', 'sdpa')

REVISION = '25e0d31ffbebe4b5a97464dd851910efc3002d96'
CHECKSUMS = {
 'ckpts/slat_dec_mesh_swin8_B_64l8m256c_fp16.safetensors': '3e87aba94b5786407eb06d0502c1ed0885a0027a3f2b8537bfe15b0a92c01859',
 'ckpts/slat_flow_img_dit_L_64l8p2_fp16.safetensors': '693fb2a58ad497bd222007301eeec49d14d60f8c12d2f2f00c221fa747b4c66c',
 'ckpts/ss_dec_conv3d_16l8_fp16.safetensors': '1c76d4a40519aa2d711cc263a8404105231ac26db31d946bed48b84fee79009a',
 'ckpts/ss_flow_img_dit_L_16l8_fp16.safetensors': '96dc6bfd4136fd950af564dd16b4ae533c9ba6af8f26c670646b2a9f2789b1db',
 'dinov2_vitl14_reg4_pretrain.pth': '36e4deffbaef061a2576705b0c36f93621e2ae20bf6274694821b0b492551b51',
}


def prepare_weights(root, download=False):
    if download:
        from huggingface_hub import snapshot_download
        files = [name for name in CHECKSUMS if name.startswith('ckpts/')]
        files += [name.replace('.safetensors', '.json') for name in files]
        snapshot_download('microsoft/TRELLIS-image-large', revision=REVISION,
                          local_dir=root, allow_patterns=files+['pipeline.json'], max_workers=2)
        target = root/'dinov2_vitl14_reg4_pretrain.pth'
        if not target.exists():
            temporary = target.with_suffix('.download')
            urllib.request.urlretrieve('https://dl.fbaipublicfiles.com/dinov2/dinov2_vitl14/dinov2_vitl14_reg4_pretrain.pth', temporary)
            temporary.replace(target)
    for name, expected in CHECKSUMS.items():
        digest = hashlib.sha256()
        with (root/name).open('rb') as stream:
            for chunk in iter(lambda: stream.read(8*1024*1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f'Checksum mismatch: {name}')
    print('All TRELLIS and DINOv2 checkpoint hashes verified', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,default=ROOT/'tests/fixtures/3d/chair.png')
    parser.add_argument('--output',type=Path,default=ROOT/'output/trellis-mac')
    parser.add_argument('--steps',type=int,default=8)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--model-dir',type=Path,default=ROOT/'models/trellis-mac')
    parser.add_argument('--structure-steps',type=int)
    parser.add_argument('--slat-steps',type=int)
    parser.add_argument('--structure-cfg',type=float,default=5.0)
    parser.add_argument('--slat-cfg',type=float,default=5.0)
    parser.add_argument('--no-preprocess',action='store_true')
    parser.add_argument('--download-only', action='store_true')
    parser.add_argument('--workflow',action='store_true')
    parser.add_argument('--stage',choices=['encode','structure','slat','mesh','all'],default='all')
    args=parser.parse_args()
    if args.steps<1: parser.error('steps must be positive')
    args.output.mkdir(parents=True,exist_ok=True)
    prepare_weights(args.model_dir, args.download_only)
    if args.download_only: return
    if args.workflow:
        import trimesh
        from ss_executor.loader import SSLoader
        from ssui.base import Image as SSImage
        from PIL import Image
        from backend.util.devices import TorchDevice
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        TorchDevice.config.device = 'mps'
        os.environ['SSUI_TRELLIS_MODEL_DIR'] = str(args.model_dir.resolve())
        loader = SSLoader()
        loader.load(str(ROOT/'examples/advance/workflow-trellis-mac.py'))
        loader.Execute()
        loader.GetConfig('img2mesh_trellis')
        loader.config.set_prepared(False)
        config = loader.config('Generate TRELLIS Mesh')
        for key, value in {'seed':args.seed,'sparse_structure_steps':args.structure_steps or args.steps,
                           'slat_steps':args.slat_steps or args.steps,'sparse_structure_cfg':args.structure_cfg,
                           'slat_cfg':args.slat_cfg,'preprocess_image':not args.no_preprocess}.items():
            config[key] = value
        fn = next(fn for fn, _, _ in loader.callables if fn.__name__ == 'img2mesh_trellis')
        started = time.monotonic()
        mesh = fn(SSImage(Image.open(args.image)))._model
        mesh.export(args.output/'mesh.glb')
        reloaded = trimesh.load(args.output/'mesh.glb',force='mesh',process=False)
        if len(reloaded.faces) != len(mesh.faces): raise RuntimeError('GLB round-trip failed')
        (args.output/'workflow_report.json').write_text(json.dumps({'seconds':time.monotonic()-started,
            'vertices':len(mesh.vertices),'faces':len(mesh.faces),'device':'mps','workflow':'img2mesh_trellis'},indent=2))
        print('SSUI TRELLIS workflow complete', flush=True)
        return
    import torch
    import numpy as np
    from PIL import Image
    from trellis import models
    from trellis.pipelines.trellis_image_to_3d import TrellisImageTo3DPipeline
    from trellis.pipelines import samplers
    from trellis.modules.sparse import SparseTensor
    torch.set_num_threads(4)
    torch.manual_seed(args.seed)
    if not torch.backends.mps.is_available(): raise RuntimeError('MPS required')
    root=args.model_dir
    config=json.loads((root/'pipeline.json').read_text())['args']
    pipe=TrellisImageTo3DPipeline()
    pipe.models={}
    pipe.rembg_session=None
    for name in ('sparse_structure_sampler','slat_sampler'):
        settings=config[name]
        setattr(pipe,name,getattr(samplers,settings['name'])(**settings['args']))
        setattr(pipe,name+'_params',settings['params'])
    pipe.slat_normalization=config['slat_normalization']
    stages=('encode','structure','slat','mesh') if args.stage=='all' else (args.stage,)
    for stage in stages:
        started=time.monotonic()
        print('Starting',stage,flush=True)
        with torch.inference_mode():
            if stage=='encode':
                from dinov2.hub.backbones import dinov2_vitl14_reg
                model=dinov2_vitl14_reg(pretrained=False).eval()
                model.load_state_dict(torch.load(root/'dinov2_vitl14_reg4_pretrain.pth',map_location='cpu',mmap=True,weights_only=True),assign=True)
                model.to('mps')
                image=Image.open(args.image)
                image=image.convert('RGB').resize((518,518)) if args.no_preprocess else pipe.preprocess_image(image)
                image.save(args.output/'input.png')
                pixels=torch.from_numpy(np.array(image.convert('RGB')).astype(np.float32)/255).permute(2,0,1)[None].to('mps')
                pixels=(pixels-torch.tensor([.485,.456,.406],device='mps')[None,:,None,None])/torch.tensor([.229,.224,.225],device='mps')[None,:,None,None]
                features=model(pixels,is_training=True)['x_prenorm']
                features=torch.nn.functional.layer_norm(features,features.shape[-1:])
                torch.save(features.cpu(),args.output/'condition.pt')
                del model,pixels,features
            elif stage=='structure':
                cond=torch.load(args.output/'condition.pt',weights_only=True).to('mps')
                for name in ('sparse_structure_flow_model','sparse_structure_decoder'):
                    pipe.models[name]=models.from_pretrained(str(root/config['models'][name])).eval().to('mps')
                coords=pipe.sample_sparse_structure({'cond':cond,'neg_cond':torch.zeros_like(cond)},1,{'steps':args.structure_steps or args.steps,'cfg_strength':args.structure_cfg})
                if not len(coords): raise RuntimeError('No occupied voxels')
                torch.save(coords.cpu(),args.output/'coords.pt')
                print('Occupied voxels:',len(coords),flush=True)
                del coords,cond
            elif stage=='slat':
                cond=torch.load(args.output/'condition.pt',weights_only=True).to('mps')
                coords=torch.load(args.output/'coords.pt',weights_only=True).to('mps')
                pipe.models['slat_flow_model']=models.from_pretrained(str(root/config['models']['slat_flow_model'])).eval().to('mps')
                result=pipe.sample_slat({'cond':cond,'neg_cond':torch.zeros_like(cond)},coords,{'steps':args.slat_steps or args.steps,'cfg_strength':args.slat_cfg})
                if not torch.isfinite(result.feats.reshape(-1)).all().item(): raise RuntimeError('Invalid SLAT')
                torch.save({'feats':result.feats.cpu(),'coords':result.coords.cpu()},args.output/'slat.pt')
                del cond,coords,result
            else:
                import trimesh
                data=torch.load(args.output/'slat.pt',weights_only=True)
                slat=SparseTensor(data['feats'].to('mps'),data['coords'].to('mps'))
                pipe.models['slat_decoder_mesh']=models.from_pretrained(str(root/config['models']['slat_decoder_mesh'])).eval().to('mps')
                result=pipe.decode_slat(slat,formats=['mesh'])['mesh'][0]
                if not result.success: raise RuntimeError('Empty mesh')
                mesh=trimesh.Trimesh(result.vertices.cpu().numpy(),result.faces.cpu().numpy(),process=False)
                if result.vertex_attrs is not None:
                    mesh.visual.vertex_colors=(result.vertex_attrs[:,:3].clamp(0,1).cpu().numpy()*255).astype(np.uint8)
                mesh.export(args.output/'mesh.glb')
                print('Mesh vertices/faces:',len(mesh.vertices),len(mesh.faces),flush=True)
                del data,slat,result,mesh
        pipe.models.clear()
        gc.collect()
        torch.mps.empty_cache()
        (args.output/f'{stage}_report.json').write_text(json.dumps({'seconds':time.monotonic()-started,'steps':args.steps,'device':'mps'},indent=2))
        print(stage,'complete',flush=True)

if __name__=='__main__': main()
