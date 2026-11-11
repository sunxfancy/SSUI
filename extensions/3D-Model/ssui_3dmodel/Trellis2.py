"""TRELLIS.2 image-to-PBR-mesh nodes using the vendored GPU pipeline."""
import os
from typing import Any

import torch
from ssui.annotation import param
from ssui.base import Image, Mesh
from ssui.config import SSUIConfig
from ssui.controller import Random, Select, Slider, Switch


class Trellis2Model:
    def __init__(self, model_path: str = "microsoft/TRELLIS.2-4B", pipeline: Any = None):
        self.model_path = model_path
        self.pipeline = pipeline

    def getModel(self):
        return self.pipeline

    @staticmethod
    def load(model_path: str = "microsoft/TRELLIS.2-4B", low_vram: bool = True) -> "Trellis2Model":
        if not torch.cuda.is_available():
            raise RuntimeError("TRELLIS.2 requires a CUDA or ROCm GPU.")
        os.environ.setdefault("ATTN_BACKEND", "sdpa")
        os.environ.setdefault("SPARSE_ATTN_BACKEND", os.environ["ATTN_BACKEND"])
        from pixal3d.pipelines import Trellis2ImageTo3DPipeline

        pipeline = Trellis2ImageTo3DPipeline.from_pretrained(model_path)
        pipeline.low_vram = low_vram
        pipeline.to(torch.device("cuda"))
        return Trellis2Model(model_path, pipeline)


@param("seed", Random(), default=42)
@param("resolution", Select(512, 1024, 1536), default=1024)
@param("export_mode", Select("vertex_colors", "pbr_texture"), default="vertex_colors")
@param("sparse_structure_steps", Slider(1, 50, 1), default=12)
@param("shape_steps", Slider(1, 50, 1), default=12)
@param("texture_steps", Slider(1, 50, 1), default=12)
@param("max_faces", Slider(10000, 1000000, 10000), default=500000)
@param("texture_size", Select(1024, 2048, 4096), default=2048)
@param("remesh", Switch(), default=False)
def GenTrellis2Model(config: SSUIConfig, model: Trellis2Model, image: Image) -> Mesh:
    if config.is_prepare():
        return Mesh()
    source = image._image if isinstance(image, Image) else image
    if source is None:
        raise ValueError("TRELLIS.2 requires a non-empty input image.")
    pipeline = model.getModel()
    resolution = int(config["resolution"])
    if resolution not in (512, 1024, 1536):
        raise ValueError("TRELLIS.2 resolution must be 512, 1024 or 1536.")
    if config["export_mode"] not in ("vertex_colors", "pbr_texture"):
        raise ValueError("Unknown TRELLIS.2 export mode.")
    meshes, (_, _, grid_size) = pipeline.run(
        source, seed=int(config["seed"]),
        pipeline_type="512" if resolution == 512 else f"{resolution}_cascade",
        sparse_structure_sampler_params={"steps": int(config["sparse_structure_steps"])},
        shape_slat_sampler_params={"steps": int(config["shape_steps"])},
        tex_slat_sampler_params={"steps": int(config["texture_steps"])},
        return_latent=True,
    )
    mesh = meshes[0]
    if config["export_mode"] == "vertex_colors":
        import numpy as np
        import trimesh

        colors = mesh.query_vertex_attrs()[:, pipeline.pbr_attr_layout["base_color"]]
        colors = (colors.clamp(0, 1) * 255).to(torch.uint8).cpu().numpy()
        vertices = mesh.vertices.cpu().numpy() @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
        return Mesh(trimesh.Trimesh(vertices, mesh.faces.cpu().numpy(), vertex_colors=colors, process=False))
    import o_voxel

    exported = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs,
        coords=mesh.coords, attr_layout=pipeline.pbr_attr_layout, grid_size=grid_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=int(config["max_faces"]), texture_size=int(config["texture_size"]),
        remesh=bool(config["remesh"]), remesh_band=1, remesh_project=0, use_tqdm=True,
    )
    return Mesh(exported)
