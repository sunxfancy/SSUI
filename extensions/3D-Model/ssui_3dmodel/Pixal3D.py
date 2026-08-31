"""SSUI nodes for TencentARC Pixal3D image-to-3D generation."""

import math
from typing import Any, Optional

import numpy as np
import torch

from ssui.annotation import param
from ssui.base import Image, Mesh
from ssui.config import SSUIConfig
from ssui.controller import Random, Slider, Switch


DEFAULT_MODEL_PATH = "TencentARC/Pixal3D"
DEFAULT_DINO_MODEL = "camenduru/dinov3-vitl16-pretrain-lvd1689m"
DEFAULT_MOGE_MODEL = "Ruicheng/moge-2-vitl"

IMAGE_COND_CONFIGS = {
    "ss": {"model_name": DEFAULT_DINO_MODEL, "image_size": 512, "grid_resolution": 16},
    "shape_512": {
        "model_name": DEFAULT_DINO_MODEL,
        "image_size": 512,
        "grid_resolution": 32,
        "use_naf_upsample": True,
        "naf_target_size": 512,
    },
    "shape_1024": {
        "model_name": DEFAULT_DINO_MODEL,
        "image_size": 1024,
        "grid_resolution": 64,
        "use_naf_upsample": True,
        "naf_target_size": 512,
    },
    "tex_1024": {
        "model_name": DEFAULT_DINO_MODEL,
        "image_size": 1024,
        "grid_resolution": 64,
        "use_naf_upsample": True,
        "naf_target_size": 1024,
    },
}


def _require_accelerator() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("Pixal3D requires a CUDA or ROCm GPU; CPU inference is not supported.")


def _build_image_cond_model(config: dict[str, Any]):
    try:
        from pixal3d.trainers.flow_matching.mixins.image_conditioned_proj import (
            DinoV3ProjFeatureExtractor,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Pixal3D runtime is incomplete. Install the 3D-Model extension's "
            "TRELLIS.2/Pixal3D accelerator dependencies before loading this model."
        ) from exc
    model = DinoV3ProjFeatureExtractor(**config)
    model.eval()
    return model


class Pixal3DModel:
    """Loaded Pixal3D pipeline and its image-conditioning backbones."""

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        pipeline: Optional[Any] = None,
        *,
        low_vram: bool = True,
    ):
        self.model_path = model_path
        self.pipeline = pipeline
        self.low_vram = low_vram

    def getModel(self):
        return self.pipeline

    @staticmethod
    def load(model_path: str = DEFAULT_MODEL_PATH, low_vram: bool = True) -> "Pixal3DModel":
        _require_accelerator()
        try:
            from pixal3d.pipelines import Pixal3DImageTo3DPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Pixal3D could not be imported. Reinstall the 3D-Model extension "
                "with its CUDA or ROCm dependencies."
            ) from exc

        pipeline = Pixal3DImageTo3DPipeline.from_pretrained(model_path)
        for name, config in IMAGE_COND_CONFIGS.items():
            setattr(pipeline, f"image_cond_model_{name}", _build_image_cond_model(config))

        pipeline.low_vram = low_vram
        if low_vram:
            pipeline._device = torch.device("cuda")
            # Download NAF weights while modules are on CPU. The pipeline moves
            # one stage at a time to CUDA during generation.
            for attr in (
                "image_cond_model_shape_512",
                "image_cond_model_shape_1024",
                "image_cond_model_tex_1024",
            ):
                module = getattr(pipeline, attr)
                if getattr(module, "use_naf_upsample", False):
                    module._load_naf()
        else:
            pipeline.cuda()
            for name in IMAGE_COND_CONFIGS:
                module = getattr(pipeline, f"image_cond_model_{name}")
                module.cuda()
                if getattr(module, "use_naf_upsample", False):
                    module._load_naf()
        return Pixal3DModel(model_path, pipeline, low_vram=low_vram)


def _distance_from_fov(camera_angle_x: float, mesh_scale: float, image_resolution: int) -> float:
    focal_length = 16.0 / math.tan(camera_angle_x / 2.0)
    f_pixels = focal_length * image_resolution / 32.0
    # Equivalent to the upstream camera fit for the lower-left canonical grid point.
    return f_pixels * -0.5 / (-image_resolution / 2.0)


def _estimate_camera(image, mesh_scale: float, image_resolution: int) -> dict[str, float]:
    try:
        from moge.model.v2 import MoGeModel
    except ImportError as exc:
        raise RuntimeError("Automatic Pixal3D camera estimation requires MoGe-2.") from exc

    moge = MoGeModel.from_pretrained(DEFAULT_MOGE_MODEL).cuda().eval()
    image_np = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    image_tensor = torch.from_numpy(image_np).permute(2, 0, 1).cuda()
    with torch.no_grad():
        intrinsics = moge.infer(image_tensor)["intrinsics"].squeeze()
    fx = float(intrinsics[0, 0].item()) * image.width
    camera_angle_x = 2.0 * math.atan(image.width / (2.0 * fx))
    moge.cpu()
    del moge
    torch.cuda.empty_cache()
    return {
        "camera_angle_x": camera_angle_x,
        "distance": _distance_from_fov(camera_angle_x, mesh_scale, image_resolution),
        "mesh_scale": mesh_scale,
    }


@param("seed", Random(), default=42)
@param("auto_camera", Switch(), default=True)
@param("fov_degrees", Slider(5, 120, 1), default=30)
@param("resolution", Slider(1024, 1536, 512), default=1024)
@param("sparse_structure_steps", Slider(1, 50, 1), default=12)
@param("shape_steps", Slider(1, 50, 1), default=12)
@param("texture_steps", Slider(1, 50, 1), default=12)
def GenPixal3DModel(config: SSUIConfig, model: Pixal3DModel, image: Image) -> Mesh:
    """Generate a textured PBR GLB-compatible trimesh scene from one image."""
    if config.is_prepare():
        return Mesh()

    pipeline = model.getModel()
    source = image._image if isinstance(image, Image) else image
    if source is None:
        raise ValueError("Pixal3D requires a non-empty input image.")

    processed = pipeline.preprocess_image(source.convert("RGB"))
    mesh_scale = 1.0
    image_resolution = 512
    if config["auto_camera"]:
        camera_params = _estimate_camera(processed, mesh_scale, image_resolution)
    else:
        fov = math.radians(float(config["fov_degrees"]))
        camera_params = {
            "camera_angle_x": fov,
            "distance": _distance_from_fov(fov, mesh_scale, image_resolution),
            "mesh_scale": mesh_scale,
        }

    seed = int(config["seed"])
    torch.manual_seed(seed)
    mesh_list, (_, _, grid_size) = pipeline.run(
        processed,
        camera_params=camera_params,
        seed=seed,
        sparse_structure_sampler_params={
            "steps": int(config["sparse_structure_steps"]),
            "guidance_strength": 7.5,
            "guidance_rescale": 0.7,
            "rescale_t": 5.0,
        },
        shape_slat_sampler_params={
            "steps": int(config["shape_steps"]),
            "guidance_strength": 7.5,
            "guidance_rescale": 0.5,
            "rescale_t": 3.0,
        },
        tex_slat_sampler_params={
            "steps": int(config["texture_steps"]),
            "guidance_strength": 1.0,
            "guidance_rescale": 0.0,
            "rescale_t": 3.0,
        },
        preprocess_image=False,
        return_latent=True,
        pipeline_type=f"{int(config['resolution'])}_cascade",
        max_num_tokens=49152,
    )

    try:
        import o_voxel
    except ImportError as exc:
        raise RuntimeError("Pixal3D GLB export requires the TRELLIS.2 o_voxel extension.") from exc

    generated = mesh_list[0]
    glb = o_voxel.postprocess.to_glb(
        vertices=generated.vertices,
        faces=generated.faces,
        attr_volume=generated.attrs,
        coords=generated.coords,
        attr_layout=pipeline.pbr_attr_layout,
        grid_size=grid_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=1_000_000,
        texture_size=4096,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        use_tqdm=True,
    )
    glb.apply_transform(
        np.array(
            [[-1, 0, 0, 0], [0, 0, -1, 0], [0, -1, 0, 0], [0, 0, 0, 1]],
            dtype=np.float64,
        )
    )
    return Mesh(glb)
