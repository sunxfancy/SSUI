"""Portable single-image reconstruction with CPU marching cubes and vertex colors."""
from pathlib import Path
import sys

from ssui.annotation import param
from ssui.base import Image, Mesh
from ssui.config import SSUIConfig
from ssui.controller import Slider

VENDOR = Path(__file__).resolve().parents[1] / 'vendor'
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))


class TripoSRModel:
    def __init__(self, model, device):
        self.model, self.device = model, device

    @staticmethod
    def load_local(model_dir=None):
        import torch
        from omegaconf import OmegaConf
        from backend.util.devices import TorchDevice
        from tsr.system import TSR
        root = Path(model_dir) if model_dir else Path(__file__).resolve().parents[3] / 'models/triposr'
        for name in ('config.yaml', 'model.ckpt', 'dino/config.json'):
            if not (root / name).is_file():
                raise FileNotFoundError(f'Missing {root / name}; run yarn test:3d:smoke --download-only')
        cfg = OmegaConf.load(root / 'config.yaml')
        cfg.image_tokenizer.pretrained_model_name_or_path = str(root / 'dino')
        OmegaConf.resolve(cfg)
        model = TSR(cfg)
        weights = torch.load(root / 'model.ckpt', map_location='cpu', weights_only=True, mmap=True)
        model.load_state_dict(weights, assign=True)
        del weights
        device = TorchDevice.choose_torch_device()
        model.eval().requires_grad_(False).to(device=device, dtype=torch.float32)
        model.renderer.set_chunk_size(4096)
        return TripoSRModel(model, str(device))


@param('resolution', Slider(32, 256, 16), default=64)
@param('foreground_ratio', Slider(0.5, 0.95, 0.05), default=0.85)
def TripoSRImageToMesh(config: SSUIConfig, model: TripoSRModel, image: Image) -> Mesh:
    if config.is_prepare():
        return Mesh()
    import numpy as np
    import torch
    from PIL import Image as PILImage
    from tsr.utils import resize_foreground
    if image is None or image._image is None:
        raise ValueError('An input image is required')
    resolution = int(config['resolution'])
    ratio = float(config['foreground_ratio'])
    if not 32 <= resolution <= 256 or not 0 < ratio <= 1:
        raise ValueError('resolution must be 32..256 and foreground_ratio must be in (0, 1]')
    source = image._image
    if source.mode == 'RGBA' and source.getextrema()[3][0] < 255:
        if source.getextrema()[3][1] == 0:
            raise ValueError('The input image is fully transparent')
        source = resize_foreground(source, ratio)
        rgba = np.asarray(source).astype(np.float32) / 255
        source = PILImage.fromarray(np.uint8((rgba[..., :3] * rgba[..., 3:] + 0.5 * (1 - rgba[..., 3:])) * 255))
    else:
        source = source.convert('RGB')
    with torch.inference_mode():
        codes = model.model([source], device=model.device)
        if not torch.isfinite(codes.reshape(-1)).all().item():
            raise RuntimeError('TripoSR produced non-finite scene codes')
        mesh = model.model.extract_mesh(codes, has_vertex_color=True, resolution=resolution)[0]
    if len(mesh.vertices) == 0 or len(mesh.faces) == 0 or not np.isfinite(mesh.vertices).all():
        raise RuntimeError('TripoSR produced an empty or non-finite mesh')
    return Mesh(mesh)
