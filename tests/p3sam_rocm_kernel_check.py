"""Numerical checks using native Windows ROCm dependency builds."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "extensions/3D-Model/ssui_3dmodel"))
from p3sam_rocm import configure_rocm

configure_rocm()
import torch
import torch.nn.functional as F
import spconv.pytorch as spconv
import torch_scatter
import flex_gemm.kernels.cuda
import flash_attn

torch.manual_seed(42)
torch.cuda.reset_peak_memory_stats()
start = time.monotonic()
indices = torch.tensor([[b, x, y, z] for b in range(2) for x in range(4) for y in range(4)
                        for z in range(4) if (x + 2*y + z) % 3], dtype=torch.int32, device="cuda")
features = torch.randn(len(indices), 2, device="cuda")
layer = spconv.SubMConv3d(2, 3, 3, bias=True, indice_key="test").cuda().eval()
with torch.no_grad():
    layer.weight.normal_(0, .1)
    layer.bias.normal_(0, .1)
    sparse = spconv.SparseConvTensor(features, indices, [4, 4, 4], 2)
    actual = layer(sparse).features
    dense = torch.zeros(2, 2, 4, 4, 4, device="cuda")
    dense[indices[:, 0], :, indices[:, 1], indices[:, 2], indices[:, 3]] = features
    reference = F.conv3d(dense, layer.weight.permute(0, 4, 1, 2, 3), layer.bias, padding=1)
    expected = reference[indices[:, 0], :, indices[:, 1], indices[:, 2], indices[:, 3]]
    torch.testing.assert_close(actual, expected, atol=1e-5, rtol=1e-4)
    conv_error = (actual - expected).abs().max().item()
    torch.testing.assert_close(layer(sparse).features, expected, atol=1e-5, rtol=1e-4)
    values = torch.randn(13, 4, device="cuda")
    pointers = torch.tensor([0, 2, 6, 13], device="cuda")
    for reduction in ("sum", "mean", "min", "max"):
        output = torch_scatter.segment_csr(values, pointers, reduce=reduction)
        chunks = [values[:2], values[2:6], values[6:]]
        expected = torch.stack([getattr(c, reduction)(0) if reduction in ("sum", "mean")
                                else getattr(c, reduction)(0).values for c in chunks])
        torch.testing.assert_close(output, expected)
        assert output.is_cuda
    qkv = torch.randn(22, 3, 2, 8, dtype=torch.float16, device="cuda")
    boundaries = torch.tensor([0, 5, 14, 22], dtype=torch.int32, device="cuda")
    output = flash_attn.flash_attn_varlen_qkvpacked_func(qkv, boundaries, 9)
    reference = []
    for a, b in ((0,5), (5,14), (14,22)):
        q,k,v = qkv[a:b].float().permute(1,2,0,3).unbind(0)
        reference.append(((q @ k.transpose(-2,-1) / 8**.5).softmax(-1) @ v).transpose(0,1))
    expected = torch.cat(reference)
    torch.testing.assert_close(output.float(), expected, atol=2e-3, rtol=2e-3)
    attention_error = (output.float() - expected).abs().max().item()
torch.cuda.synchronize()
report = {"torch": torch.__version__, "hip": torch.version.hip,
    "device": torch.cuda.get_device_name(0), "conv_max_abs_error": conv_error,
    "attention_max_abs_error": attention_error,
    "scatter": str(Path(torch_scatter.__file__).resolve()),
    "sparse_kernel": str(Path(flex_gemm.kernels.cuda.__file__).resolve()),
    "peak_gpu_bytes": torch.cuda.max_memory_allocated(), "seconds": time.monotonic()-start,
    "checks": ["sparse conv matches dense GPU reference", "neighbour cache reuse", "GPU CSR sum/mean/min/max", "GPU variable-length attention"]}
destination = ROOT / "output/retopology-rocm-validation"
destination.mkdir(parents=True, exist_ok=True)
(destination / "kernel-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
