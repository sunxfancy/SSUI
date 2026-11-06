"""Text-to-mesh using the Diffusers Shap-E pipeline."""
import torch
import trimesh
import numpy as np
from ssui.annotation import param
from ssui.base import Mesh, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider


class ShapEModel:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    @staticmethod
    def load(model_path: str) -> "ShapEModel":
        from backend.diffusers_compat import preload_attention_dispatch_for_torch_24
        preload_attention_dispatch_for_torch_24()
        from diffusers import ShapEPipeline

        cuda = torch.cuda.is_available()
        pipeline = ShapEPipeline.from_pretrained(
            model_path, variant="fp16",
            torch_dtype=torch.float16 if cuda else torch.float32,
        )
        pipeline.to("cuda" if cuda else "cpu")
        return ShapEModel(pipeline)


@param("seed", Random(), default=42)
@param("num_inference_steps", Slider(1, 128, 1), default=64)
@param("guidance_scale", Slider(1, 30, 0.5), default=15.0)
def ShapETextToMesh(config: SSUIConfig, model: ShapEModel, prompt: Prompt) -> Mesh:
    if config.is_prepare():
        return Mesh()

    pipeline = model.pipeline
    device = pipeline._execution_device
    result = pipeline(
        prompt.text, num_inference_steps=config["num_inference_steps"],
        guidance_scale=config["guidance_scale"],
        generator=torch.Generator(device=device).manual_seed(config["seed"]),
        output_type="mesh",
    ).images[0]
    vertices = result.verts.detach().cpu().numpy()
    faces = result.faces.detach().cpu().numpy()
    channels = result.vertex_channels
    colors = np.stack([channels[c].detach().cpu().numpy() for c in "RGB"], axis=-1)
    mesh = trimesh.Trimesh(
        vertices=vertices, faces=faces,
        vertex_colors=(colors.clip(0, 1) * 255).astype(np.uint8),
        process=False,
    )
    # Shap-E uses Z-up; glTF/SSUI uses Y-up.
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    return Mesh(mesh)
