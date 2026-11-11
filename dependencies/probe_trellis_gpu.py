"""Verify the TRELLIS FlexGEMM checkpoint adapter and sparse attention on a GPU."""
import os, sys, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'extensions/3D-Model/vendor'))
os.environ['SPARSE_BACKEND'] = 'flex_gemm'
os.environ['ATTN_BACKEND'] = os.environ['SPARSE_ATTN_BACKEND'] = 'sdpa'
import torch
from trellis.modules.sparse import SparseTensor, SparseConv3d
from trellis.modules.sparse.attention.full_attn import sparse_scaled_dot_product_attention
from trellis.modules.sparse.attention.windowed_attn import sparse_windowed_scaled_dot_product_self_attention
from flex_gemm.kernels.triton.spconv import config
config.allow_tf32 = False
torch.manual_seed(7)
coords = torch.cartesian_prod(torch.arange(1), torch.arange(4), torch.arange(4), torch.arange(4)).cuda().int()
feats = torch.randn(64, 8, device='cuda')
conv = SparseConv3d(8, 8, 3).cuda()
state = {'conv.weight': torch.randn(8, 3, 3, 3, 8, device='cuda'), 'conv.bias': torch.randn(8, device='cuda')}
conv.load_state_dict(state, strict=True)
expected = torch.nn.functional.conv3d(feats.reshape(1,4,4,4,8).permute(0,4,1,2,3).cpu().double(),
    state['conv.weight'].permute(0,4,1,2,3).cpu().double(), state['conv.bias'].cpu().double(), padding=1)
expected = expected.permute(0,2,3,4,1).reshape(64,8).to(feats)
with torch.no_grad():
    torch.testing.assert_close(conv(SparseTensor(feats,coords)).feats, expected, rtol=2e-3, atol=2e-3)
print('checkpoint_convolution: passed', flush=True)
qkv = torch.randn(64,3,2,16,device='cuda')
sparse = SparseTensor(qkv, coords)
q,k,v = qkv.unbind(1)
reference = torch.nn.functional.scaled_dot_product_attention(q.transpose(0,1)[None], k.transpose(0,1)[None], v.transpose(0,1)[None])[0].transpose(0,1)
torch.testing.assert_close(sparse_scaled_dot_product_attention(sparse).feats, reference)
actual = sparse_windowed_scaled_dot_product_self_attention(sparse,2).feats
reference = torch.empty_like(actual)
windows = coords[:,1:] // 2
for cell in windows.unique(dim=0):
    mask = (windows == cell).all(-1)
    q,k,v = qkv[mask].unbind(1)
    reference[mask] = torch.nn.functional.scaled_dot_product_attention(q.transpose(0,1)[None],k.transpose(0,1)[None],v.transpose(0,1)[None])[0].transpose(0,1)
torch.testing.assert_close(actual,reference)
print('full_and_window_attention: passed', flush=True)
from trellis.modules.sparse import SparseSubdivide
from trellis.pipelines.samplers.flow_euler import FlowEulerSampler
base = SparseTensor(feats, coords)
# The latent flow may have coarser-resolution caches before mesh subdivision.
base._spatial_cache[str(tuple(s * 2 for s in base._scale))] = {'layout': [slice(0, 1)]}
subdivided = SparseSubdivide()(base)
assert len(subdivided.feats) == 512 and subdivided.layout == [slice(0, 512)]
sampler = FlowEulerSampler(sigma_min=0.0)
result = sampler.sample(lambda x, t, c: x.replace(torch.zeros_like(x.feats)), base, steps=2, verbose=False)
torch.testing.assert_close(result.samples.feats, base.feats)
print('subdivision_cache_and_sampler: passed', flush=True)
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True)
args = parser.parse_args()
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps({'status':'passed','checks':['checkpoint_convolution','full_attention','window_attention','subdivision_cache','numpy2_sampler'],'gpu':torch.cuda.get_device_name(0)},indent=2)+'\n')
