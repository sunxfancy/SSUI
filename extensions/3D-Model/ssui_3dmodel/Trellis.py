from typing import Optional, List
import torch
from ssui.config import SSUIConfig
from ssui.base import Mesh, Image
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider

class TrellisModel:
    def __init__(
        self,
        model_path: str = "",
        model: Optional[torch.nn.Module] = None,
    ):
        self.model_path = model_path
        self.model = model

    def getModel(self):
        return self.model

    @staticmethod
    def load(model_path: str):
        if torch.version.hip:
            raise RuntimeError(
                "Legacy TRELLIS requires CUDA-only extensions in SSUI. "
                "Use the Pixal3D workflow for ROCm and run yarn probe:3d first."
            )
        from backend.util.devices import TorchDevice
        if TorchDevice.choose_torch_device().type == 'mps':
            from pathlib import Path
            import os
            root = Path(__file__).resolve().parents[3] / 'models/trellis-mac' if model_path == 'microsoft/TRELLIS-image-large' else Path(model_path)
            root = Path(os.environ.get('SSUI_TRELLIS_MODEL_DIR', root))
            if not (root / 'pipeline.json').is_file():
                raise FileNotFoundError('Mac TRELLIS requires local official weights: yarn test:trellis:smoke --download-only')
            return TrellisModel(str(root), None)
        from trellis.pipelines.trellis_image_to_3d import TrellisImageTo3DPipeline
        model = TrellisImageTo3DPipeline.from_pretrained(model_path)
        model.cuda()
        return TrellisModel(model_path, model)


@param("seed", Random(), default=42)
@param("preprocess_image", Switch(), default=True)
@param("sparse_structure_steps", Slider(1, 50, 1), default=12)
@param("sparse_structure_cfg", Slider(0, 15, 0.1), default=7.5)
@param("slat_steps", Slider(1, 50, 1), default=12)
@param("slat_cfg", Slider(0, 15, 0.1), default=3.0)
def GenModel(
    config: SSUIConfig,
    model: TrellisModel,
    image: Image,
):
    if config.is_prepare():
        return Mesh()

    if model.model is None:
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        import trimesh
        if image is None or image._image is None:
            raise ValueError('An input image is required')
        with tempfile.TemporaryDirectory(prefix='ssui-trellis-') as folder:
            root = Path(folder)
            image._image.save(root / 'input.png')
            command = [sys.executable, str(Path(__file__).with_name('trellis_mps_runner.py')),
                       '--model-dir', model.model_path, '--image', str(root / 'input.png'), '--output', str(root),
                       '--seed', str(config['seed']), '--structure-steps', str(config['sparse_structure_steps']),
                       '--slat-steps', str(config['slat_steps']), '--structure-cfg', str(config['sparse_structure_cfg']),
                       '--slat-cfg', str(config['slat_cfg'])]
            if not config['preprocess_image']:
                command.append('--no-preprocess')
            subprocess.run(command, check=True)
            return Mesh(trimesh.load(root / 'mesh.glb', force='mesh', process=False))

    from trellis.utils import postprocessing_utils
    print("GenModel executed")
    print("seed:", config["seed"])
    print("preprocess_image:", config["preprocess_image"])
    print("sparse_structure_steps:", config["sparse_structure_steps"])
    print("sparse_structure_cfg:", config["sparse_structure_cfg"])
    print("slat_steps:", config["slat_steps"])
    print("slat_cfg:", config["slat_cfg"])

    # 构建采样器参数
    sparse_structure_sampler_params = {
        "steps": config["sparse_structure_steps"],
        "cfg_strength": config["sparse_structure_cfg"],
    }
    
    slat_sampler_params = {
        "steps": config["slat_steps"],
        "cfg_strength": config["slat_cfg"],
    }

    outputs = model.getModel().run(
        image=image._image,
        sparse_structure_sampler_params=sparse_structure_sampler_params,
        slat_sampler_params=slat_sampler_params,
        formats=["mesh", "gaussian"],
        seed=config["seed"],
        preprocess_image=config["preprocess_image"],
    ) 

    glb = postprocessing_utils.to_glb(
        outputs['gaussian'][0],
        outputs['mesh'][0],
        # Optional parameters
        simplify=0.95,          # Ratio of triangles to remove in the simplification process
        texture_size=1024,      # Size of the texture used for the GLB
    )

    return Mesh(glb)



