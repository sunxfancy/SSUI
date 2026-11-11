"""Text to editable indoor scene through an isolated SceneSmith runtime."""
from ssui import Mesh, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_3dmodel.SceneSmith import GenSceneSmithScene, SceneSmithModel

config = SSUIConfig()


@workflow
def scenesmith_scene(prompt: Prompt) -> Mesh:
    return GenSceneSmithScene(config("SceneSmith Scene"), SceneSmithModel.load_local(), prompt)
