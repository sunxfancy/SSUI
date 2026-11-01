import unittest
from tests.utils import should_run_model_tests


@unittest.skipUnless(should_run_model_tests(), '需要 SSUI_RUN_MODEL_TESTS=1')
class TestNvdiffrastCUDA(unittest.TestCase):
    def test_rasterize_and_backward(self):
        import torch
        import nvdiffrast.torch as dr
        context = dr.RasterizeCudaContext()
        vertices = torch.tensor([[[-.7, -.7, 0, 1], [.7, -.7, 0, 1], [0, .7, 0, 1]]],
                                device='cuda', requires_grad=True)
        faces = torch.tensor([[0, 1, 2]], dtype=torch.int32, device='cuda')
        colors = torch.eye(3, device='cuda')[None].requires_grad_()
        raster, _ = dr.rasterize(context, vertices, faces, resolution=[32, 32])
        image, _ = dr.interpolate(colors, raster, faces)
        image = dr.antialias(image, raster, vertices, faces)
        image.square().sum().backward()
        self.assertGreater(float(image.abs().sum()), 0)
        self.assertTrue(torch.isfinite(vertices.grad).all())
        self.assertGreater(float(vertices.grad.abs().sum()), 0)
