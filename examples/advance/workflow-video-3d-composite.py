"""Real video plus prompt and an existing or generated 3D mesh.

Blender solves the true 3D camera from tracked video features. A click in the
first uploaded frame overrides the text or vision model anchor suggestion.
"""

from ssui import workflow, Mesh, Prompt, Video
from ssui.config import SSUIConfig
from ssui_3dmodel.Pixal3D import Pixal3DModel, GenPixal3DModel
from ssui_video.QwenImage import QwenImageModel, QwenImageGenerate
from ssui_video.BlenderSceneComposite import CompositeWithBlender

config = SSUIConfig()


@workflow
def composite_existing_mesh(footage: Video, mesh: Mesh, placement: Prompt) -> Video:
    return CompositeWithBlender(config("Blender Camera Composite"), footage, mesh, placement)


@workflow
def generate_and_composite(footage: Video, object_prompt: Prompt,
                           placement: Prompt) -> Video:
    if config.is_prepare():
        image_model = QwenImageModel()
    else:
        image_model = QwenImageModel.load()
    image = QwenImageGenerate(config("Generate Asset Image"), image_model,
                              object_prompt, Prompt("background-free isolated object"))
    if config.is_prepare():
        mesh_model = Pixal3DModel()
    else:
        del image_model
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        mesh_model = Pixal3DModel.load()
    mesh = GenPixal3DModel(config("Generate 3D Asset"), mesh_model, image)
    return CompositeWithBlender(config("Blender Camera Composite"), footage, mesh, placement)
