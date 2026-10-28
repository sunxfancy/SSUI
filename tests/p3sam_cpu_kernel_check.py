"""Run with the isolated Linux P3-SAM Python, not the SSUI Python."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extensions/3D-Model/ssui_3dmodel"))
from p3sam_cpu import configure_cpu

configure_cpu()
import torch
import spconv.pytorch as spconv

torch.manual_seed(7)
indices = torch.tensor([[0, x, y, z] for x in range(3) for y in range(3) for z in range(3)], dtype=torch.int32)
features = torch.randn(len(indices), 2)
layer = spconv.SubMConv3d(2, 3, 3, bias=True).eval()
original_bias = layer.bias
tensor = spconv.SparseConvTensor(features, indices, [3, 3, 3], 1)
with torch.no_grad():
    actual = layer(tensor).features
    dense = torch.zeros(1, 2, 3, 3, 3)
    dense[0, :, indices[:, 1], indices[:, 2], indices[:, 3]] = features.T
    expected = torch.nn.functional.conv3d(dense, layer.weight.permute(0, 4, 1, 2, 3), layer.bias, padding=1)
    expected = expected[0, :, indices[:, 1], indices[:, 2], indices[:, 3]].T
    torch.testing.assert_close(actual, expected, atol=1e-5, rtol=1e-5)
assert layer.bias is original_bias
print("CPU sparse convolution plus bias matches dense reference; checkpoint parameter preserved")
