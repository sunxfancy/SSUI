"""Check decoder-sized sparse linear outputs against independent references."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions/3D-Model/vendor'))
import torch
from pixal3d.modules.sparse import VarLenTensor, SparseLinear
from pixal3d.modules.sparse.linear import apply_rowwise

torch.manual_seed(7)
with torch.no_grad():
    for dtype in (torch.float32, torch.float16, torch.bfloat16):
        count = 2000003
        layer = SparseLinear(32, 7).to(device='cuda', dtype=dtype)
        layer.weight.fill_(1)
        layer.bias.fill_(2)
        feats = torch.ones((count, 32), device='cuda', dtype=dtype)
        actual = layer(VarLenTensor(feats)).feats
        torch.testing.assert_close(actual, torch.full_like(actual, 34), rtol=0, atol=0)
        # Vary every row; independently compute a small CPU reference around
        # chunk boundaries and the two observed native-GEMM failure boundaries.
        feats[:, 0] = torch.arange(count, device='cuda').remainder(13).to(dtype)
        layer.weight.normal_(std=.1)
        layer.bias.normal_(std=.1)
        actual = layer(VarLenTensor(feats)).feats
        rows = torch.tensor([0, 65535, 65536, 524287, 524288, 1048575, 1048576, count-1], device='cuda')
        expected = torch.nn.functional.linear(feats[rows].cpu().float(), layer.weight.cpu().float(), layer.bias.cpu().float())
        tolerance = {torch.float32: 2e-5, torch.float16: 2e-3, torch.bfloat16: 2e-2}[dtype]
        torch.testing.assert_close(actual[rows].cpu().float(), expected, rtol=tolerance, atol=tolerance)
        assert torch.isfinite(actual).all()
        mlp = torch.nn.Sequential(torch.nn.Linear(32, 16), torch.nn.SiLU(), torch.nn.Linear(16, 7)).to(device='cuda', dtype=dtype)
        mlp_actual = apply_rowwise(mlp, feats)
        reference_mlp = mlp.cpu().float()
        mlp_expected = reference_mlp(feats[rows].cpu().float())
        torch.testing.assert_close(mlp_actual[rows].cpu().float(), mlp_expected, rtol=tolerance, atol=tolerance)
        assert torch.isfinite(mlp_actual).all()
        print(f'PASS {dtype}: {count} rows, exact constant and varied CPU-reference checks', flush=True)
