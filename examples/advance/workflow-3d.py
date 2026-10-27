from ssui import workflow, Prompt, Image, Mesh
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxDenoise, FluxLatentDecode
from ssui.config import SSUIConfig
from ssui_3dmodel.Trellis import TrellisModel, GenModel
from ssui_3dmodel.Pixal3D import Pixal3DModel, GenPixal3DModel
from ssui_3dmodel.WorldClaw import WorldClawModel, GenWorldClawScene
from typing import List, Tuple

config = SSUIConfig()


@workflow
def txt2img(model: FluxModel, positive: Prompt, negative: Prompt) -> Image:
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)
    return FluxLatentDecode(config("Latent to Image"), model, latent)

@workflow
def img2mesh(model: TrellisModel, image: Image) -> Mesh:
    return GenModel(config("GenModel"), model, image)

@workflow
def img2mesh_pixal3d(model: Pixal3DModel, image: Image) -> Mesh:
    return GenPixal3DModel(config("Generate Pixal3D Model"), model, image)

@workflow
def text2world_worldclaw(prompt: Prompt) -> Mesh:
    # Runs as a deterministic local blockout by default. Set
    # SSUI_WORLDCLAW_PLANNER_URL for an agent planner that returns WorldSpec JSON.
    model = WorldClawModel.load()
    return GenWorldClawScene(config("Generate WorldClaw Scene"), model, prompt)

