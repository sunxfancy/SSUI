"""Select the local openai/shap-e snapshot as the model input."""
from ssui import workflow, Prompt, Mesh
from ssui.config import SSUIConfig
from ssui_3dmodel.ShapE import ShapEModel, ShapETextToMesh

config = SSUIConfig()


@workflow
def text_to_mesh(model: ShapEModel, prompt: Prompt) -> Mesh:
    return ShapETextToMesh(config("Generate 3D mesh"), model, prompt)
