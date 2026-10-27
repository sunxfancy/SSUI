from typing import Optional, List
import os
import platform
import torch
from ssui.config import SSUIConfig
from ssui.base import Mesh, Image
from ssui.annotation import param
from ssui.controller import Random, Switch, Slider, Select

WINDOWS_ARM64 = platform.system() == "Windows" and platform.machine().lower() in ("arm64", "aarch64")

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
        if not torch.cuda.is_available():
            raise RuntimeError("TRELLIS requires a CUDA or ROCm GPU.")
        os.environ.setdefault("ATTN_BACKEND", "sdpa")
        os.environ.setdefault("SPARSE_ATTN_BACKEND", os.environ["ATTN_BACKEND"])
        if WINDOWS_ARM64:
            os.environ.setdefault("SPARSE_BACKEND", "flex_gemm")
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
@param("export_mode", Select("vertex_colors", "gaussian_texture"), default="vertex_colors" if WINDOWS_ARM64 else "gaussian_texture")
def GenModel(
    config: SSUIConfig,
    model: TrellisModel,
    image: Image,
) -> Mesh:
    if config.is_prepare():
        return Mesh()

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

    source = image._image if isinstance(image, Image) else image
    if source is None:
        raise ValueError("TRELLIS requires a non-empty input image.")
    if config["export_mode"] not in ("vertex_colors", "gaussian_texture"):
        raise ValueError("Unknown TRELLIS export mode.")
    outputs = model.getModel().run(
        image=source,
        sparse_structure_sampler_params=sparse_structure_sampler_params,
        slat_sampler_params=slat_sampler_params,
        formats=["mesh", "gaussian"] if config["export_mode"] == "gaussian_texture" else ["mesh"],
        seed=config["seed"],
        preprocess_image=config["preprocess_image"],
    ) 

    if config["export_mode"] == "vertex_colors":
        import numpy as np
        import trimesh

        mesh = outputs["mesh"][0]
        if not mesh.success:
            raise RuntimeError("TRELLIS generated an empty mesh.")
        colors = None
        if mesh.vertex_attrs is not None:
            colors = (mesh.vertex_attrs[:, :3].clamp(0, 1) * 255).to(torch.uint8).cpu().numpy()
        vertices = mesh.vertices.cpu().numpy() @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
        return Mesh(trimesh.Trimesh(vertices, mesh.faces.cpu().numpy(), vertex_colors=colors, process=False))
    from trellis.utils import postprocessing_utils

    glb = postprocessing_utils.to_glb(
        outputs['gaussian'][0],
        outputs['mesh'][0],
        # Optional parameters
        simplify=0.95,          # Ratio of triangles to remove in the simplification process
        texture_size=1024,      # Size of the texture used for the GLB
    )

    return Mesh(glb)



