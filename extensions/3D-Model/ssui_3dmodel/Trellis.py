from typing import Optional, List
import torch
from ssui.config import SSUIConfig
from ssui.base import Model3D, Image
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider
from trellis.pipelines.trellis_image_to_3d import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils

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
        return Model3D()

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
        image=image,
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

    return Model3D(glb)



