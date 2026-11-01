"""Compare native NAF neighborhood attention with a direct PyTorch reference."""
import torch
from natten.functional import na2d_qk, na2d_av

torch.manual_seed(42)
for dilation in (1, 2):
    height, width, kernel = 20, 22, 9
    def neighbors(index, length):
        lane = index % dilation
        positions = list(range(lane, length, dilation))
        center = positions.index(index)
        start = max(0, min(center - kernel // 2, len(positions) - kernel))
        return positions[start:start + kernel]
    indices = torch.tensor([
        [x * width + y for x in neighbors(i, height) for y in neighbors(j, width)]
        for i in range(height) for j in range(width)
    ], device="cuda")
    q = torch.randn(1, 2, height, width, 64, device="cuda", requires_grad=True)
    k = torch.randn_like(q, requires_grad=True)
    v = torch.randn(1, 2, height, width, 256, device="cuda", requires_grad=True)
    scores = na2d_qk(q, k, kernel_size=kernel, dilation=dilation) / 8
    actual = na2d_av(scores.softmax(-1), v, kernel_size=kernel, dilation=dilation)
    ref_scores = (q.flatten(2, 3).unsqueeze(-2) * k.flatten(2, 3)[:, :, indices]).sum(-1) / 8
    expected = (ref_scores.softmax(-1).unsqueeze(-1) * v.flatten(2, 3)[:, :, indices]).sum(-2)
    torch.testing.assert_close(actual.flatten(2, 3), expected, atol=2e-5, rtol=2e-4)
    native_grads = torch.autograd.grad(actual.square().sum(), (q, k, v), retain_graph=True)
    reference_grads = torch.autograd.grad(expected.square().sum(), (q, k, v))
    for actual_grad, expected_grad in zip(native_grads, reference_grads):
        torch.testing.assert_close(actual_grad, expected_grad, atol=5e-4, rtol=2e-3)
    print(f"PASS NATTEN QK/AV forward and gradients, kernel=9 dilation={dilation}", flush=True)
torch.cuda.synchronize()
