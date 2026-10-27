"""Actual MPS sparse operators, checked against dense PyTorch references."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class TrellisRuntimeTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('SSUI_RUN_3D_RUNTIME_TESTS') == '1', 'opt-in real TRELLIS operators')
    def test_torch_sparse_backend(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import torch
import torch.nn.functional as F
from trellis.modules.sparse import SparseTensor, SparseConv3d
from trellis.modules.sparse.attention import sparse_scaled_dot_product_attention, sparse_windowed_scaled_dot_product_self_attention
assert torch.backends.mps.is_available(), 'This check requires real MPS hardware'
torch.manual_seed(71)
device = 'mps'
coords = torch.tensor([[0,0,0,0],[0,1,0,0],[0,1,1,0],[0,2,2,1],[1,0,1,0],[1,1,1,0]], dtype=torch.int32)
feats = torch.randn(len(coords), 3)
x = SparseTensor(feats.to(device), coords.to(device))
conv = SparseConv3d(3, 5, 3).to(device)
dense = torch.zeros(2,3,3,3,2)
for c, f in zip(coords, feats): dense[c[0],:,c[1],c[2],c[3]] = f
weight = conv.conv.weight.detach().cpu().permute(0,4,1,2,3).contiguous()
expected = F.conv3d(dense,weight,conv.conv.bias.detach().cpu(),padding=1)
expected = torch.stack([expected[c[0],:,c[1],c[2],c[3]] for c in coords])
actual = conv(x)
assert actual.feats.device.type == 'mps'
torch.testing.assert_close(actual.feats.cpu(), expected, rtol=1e-4, atol=1e-5)
torch.testing.assert_close(conv(x).feats, actual.feats)
qkv = torch.randn(len(coords),3,2,8)
sparse = x.replace(qkv.to(device))
result = sparse_scaled_dot_product_attention(sparse)
reference = []
for part in (qkv[:4],qkv[4:]):
    q,k,v = [t.transpose(0,1).unsqueeze(0) for t in part.unbind(1)]
    reference.append(F.scaled_dot_product_attention(q,k,v).squeeze(0).transpose(0,1))
torch.testing.assert_close(result.feats.cpu(),torch.cat(reference),rtol=1e-4,atol=1e-5)
windowed = sparse_windowed_scaled_dot_product_self_attention(sparse, window_size=4)
torch.testing.assert_close(windowed.feats,result.feats,rtol=1e-4,atol=1e-5)
from trellis.modules.sparse.attention.sdpa import packed_attention
lengths = [2,3,5,7,2,4,6,8]
q,k,v = [torch.randn(sum(lengths),2,8) for _ in range(3)]
expected_windows = []
start = 0
for size in lengths:
    expected_windows.append(F.scaled_dot_product_attention(q[start:start+size].transpose(0,1)[None], k[start:start+size].transpose(0,1)[None], v[start:start+size].transpose(0,1)[None])[0].transpose(0,1))
    start += size
actual_windows = packed_attention(q.to('mps'),k.to('mps'),v.to('mps'),lengths,lengths)
torch.testing.assert_close(actual_windows.cpu(),torch.cat(expected_windows),rtol=1e-4,atol=1e-5)
from trellis.models.structured_latent_flow import SLatFlowModel
flow = SLatFlowModel(resolution=4,in_channels=3,model_channels=24,cond_channels=8,out_channels=3,num_blocks=1,num_heads=2,patch_size=2,num_io_res_blocks=1,io_block_channels=[12]).eval()
with torch.no_grad():
    flow.out_layer.weight.normal_(std=0.05)
    condition = torch.randn(2,5,8)
    t = torch.tensor([0.5,0.5])
    expected_flow = flow(SparseTensor(feats,coords),t,condition).feats
    flow.to('mps')
    with torch.inference_mode():
        actual_flow = flow(SparseTensor(feats.to('mps'),coords.to('mps')),t.to('mps'),condition.to('mps')).feats
    torch.testing.assert_close(actual_flow.cpu(),expected_flow,rtol=1e-3,atol=1e-4)
from trellis.representations.mesh.utils_cube import construct_voxel_grid, cubes_to_verts
vertices_cpu, cubes_cpu = construct_voxel_grid(coords[:4,1:])
vertices_mps, cubes_mps = construct_voxel_grid(coords[:4,1:].to('mps'))
torch.testing.assert_close(vertices_mps.cpu(),vertices_cpu)
values = torch.randn(4,8,3)
expected_attrs = cubes_to_verts(len(vertices_cpu),cubes_cpu,values)
actual_attrs = cubes_to_verts(len(vertices_mps),cubes_mps,values.to('mps'))
torch.testing.assert_close(actual_attrs.cpu(),expected_attrs)
from trellis.representations.mesh.cube2mesh import SparseFeatures2Mesh
cube_feats = torch.zeros(1,53)
cube_feats[0,:8] = torch.tensor([-1.,1.,1.,1.,1.,1.,1.,1.])
cube_coords = torch.tensor([[0,1,1,1]],dtype=torch.int32)
with torch.no_grad():
    reference_mesh = SparseFeatures2Mesh(device='cpu',res=4,use_color=False)(SparseTensor(cube_feats.clone(),cube_coords),training=False)
    actual_mesh = SparseFeatures2Mesh(device='mps',res=4,use_color=False)(SparseTensor(cube_feats.to('mps'),cube_coords.to('mps')),training=False)
assert reference_mesh.success and actual_mesh.success
torch.testing.assert_close(actual_mesh.vertices.cpu(),reference_mesh.vertices,rtol=1e-4,atol=1e-5)
torch.testing.assert_close(actual_mesh.faces.cpu(),reference_mesh.faces)
from ss_executor.loader import SSLoader
loader=SSLoader()
loader.load('examples/advance/workflow-trellis-mac.py')
loader.Execute()
loader.GetConfig('img2mesh_trellis')
print('Real MPS sparse convolution, cached topology, batch-isolated and windowed attention passed')
'''
        env = dict(os.environ, SPARSE_BACKEND='torch', SPARSE_ATTN_BACKEND='sdpa', ATTN_BACKEND='sdpa', PYTORCH_ENABLE_MPS_FALLBACK='0')
        env['PYTHONPATH'] = os.pathsep.join(map(str,[root,root/'extensions/3D-Model',root/'extensions/3D-Model/vendor']))
        result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)

    @unittest.skipUnless(os.environ.get('SSUI_RUN_3D_RUNTIME_TESTS') == '1', 'opt-in real TRELLIS operators')
    def test_gpu_topology(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, 'scripts/trellis_topology_benchmark.py', '--check-only'],
                                cwd=root, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
