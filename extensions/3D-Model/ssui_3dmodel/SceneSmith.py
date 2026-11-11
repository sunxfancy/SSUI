"""SSUI workflow entry for the native 3D scene layout backend."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from backend.scenesmith import STAGES, asset_catalog, generate_scene, plan_with_local_llm
from ssui.annotation import param
from ssui.base import Mesh, Prompt
from ssui.config import SSUIConfig
from ssui.controller import Input, Select


ROOT = Path(__file__).resolve().parents[3]


class SceneSmithModel:
    def __init__(self, asset_dir=None, spec_path=None, planner_model=None, planner_python=None,
                 stop_stage="manipuland", resume_from=None):
        self.asset_dir = asset_dir or os.environ.get("SSUI_SCENE_ASSETS")
        self.spec_path = spec_path or os.environ.get("SSUI_SCENE_SPEC")
        self.planner_model = planner_model or os.environ.get("SSUI_SCENE_PLANNER_MODEL")
        self.planner_python = planner_python or os.environ.get("SSUI_SCENE_PLANNER_PYTHON")
        self.stop_stage = stop_stage
        self.resume_from = resume_from

    @classmethod
    def load_local(cls, asset_dir=None, spec_path=None, planner_model=None, planner_python=None,
                   stop_stage="manipuland", resume_from=None):
        return cls(asset_dir, spec_path, planner_model, planner_python, stop_stage, resume_from)

    def generate(self, prompt: str) -> Mesh:
        if not prompt.strip():
            raise ValueError("Scene prompt must be nonempty")
        if not self.asset_dir:
            raise ValueError("Set SSUI_SCENE_ASSETS to a GLB asset directory")
        spec = json.loads(Path(self.spec_path).read_text(encoding="utf-8")) if self.spec_path else None
        output = ROOT / "output/scenesmith"
        output.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="scene_", dir=output))
        if spec is None and self.planner_model:
            if not self.planner_python:
                raise ValueError("Set SSUI_SCENE_PLANNER_PYTHON for the local Qwen runtime")
            spec = plan_with_local_llm(prompt, asset_catalog(self.asset_dir), work,
                                       self.planner_python, self.planner_model)
        return Mesh(path=str(generate_scene(prompt, self.asset_dir, work, spec,
                                            stop_stage=self.stop_stage, resume_from=self.resume_from)))


@param("asset_dir", Input("GLB asset directory"), default="")
@param("spec_path", Input("Optional scene JSON path"), default="")
@param("planner_model", Input("Optional local Qwen model directory"), default="")
@param("stop_stage", Select(*STAGES), default="manipuland")
@param("resume_from", Input("Optional prior stage scene.json"), default="")
def GenSceneSmithScene(config: SSUIConfig, model: SceneSmithModel, prompt: Prompt) -> Mesh:
    if config.is_prepare():
        return Mesh()
    text = prompt.text if isinstance(prompt, Prompt) else str(prompt)
    asset_dir = config["asset_dir"] or model.asset_dir
    spec_path = config["spec_path"] or model.spec_path
    planner_model = config["planner_model"] or model.planner_model
    stop_stage = config["stop_stage"] or model.stop_stage
    resume_from = config["resume_from"] or model.resume_from
    return SceneSmithModel.load_local(asset_dir, spec_path, planner_model, model.planner_python,
                                      stop_stage, resume_from).generate(text)
