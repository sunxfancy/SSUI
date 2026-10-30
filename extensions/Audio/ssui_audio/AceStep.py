"""ACE-Step 1.5 adapter. Install the official upstream package separately."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import importlib.util

from ssui.base import Audio


class AceStepModel:
    def __init__(self, dit_handler, project_root: str):
        self.dit_handler = dit_handler
        self.project_root = project_root

    @staticmethod
    def load(project_root: str, config_path: str = "acestep-v15-turbo", device: str | None = None) -> "AceStepModel":
        # A source checkout and its optional dependency overlay can live in
        # .build without changing SSUI's shared ROCm virtual environment.
        source = os.environ.get("SSUI_ACE_STEP_SOURCE", project_root)
        overlay = os.environ.get("SSUI_ACE_STEP_DEPS", os.path.join(source, ".deps"))
        vector_source = os.environ.get(
            "SSUI_ACE_STEP_VECTOR_SOURCE",
            os.path.join(os.path.dirname(project_root), "vector-quantize-pytorch"),
        )
        # Use packages in shared Python first. Retain the isolated source and
        # dependency overlay as fallbacks for machines without shared setup.
        fallback = []
        if importlib.util.find_spec("vector_quantize_pytorch") is None:
            fallback.append(vector_source)
        if any(importlib.util.find_spec(name) is None for name in ("loguru", "xxhash", "einx")):
            fallback.append(overlay)
        for candidate in (*fallback, source):
            if candidate and os.path.isdir(candidate) and candidate not in sys.path:
                sys.path.insert(0, candidate)
        try:
            import torch
            from acestep.handler import AceStepHandler
        except ImportError as exc:
            raise RuntimeError("ACE-Step 1.5 requires its official source/package and dependencies; set SSUI_ACE_STEP_SOURCE and SSUI_ACE_STEP_DEPS") from exc
        if not os.path.isdir(project_root):
            raise FileNotFoundError(f"ACE-Step project_root does not exist: {project_root}")
        os.environ.setdefault("ACESTEP_CHECKPOINTS_DIR", os.path.join(project_root, "checkpoints"))
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        handler = AceStepHandler()
        status, success = handler.initialize_service(project_root=project_root, config_path=config_path, device=device)
        if not success:
            raise RuntimeError(f"ACE-Step model initialization failed: {status}")
        return AceStepModel(handler, project_root)


def generate_ace_step(
    model: AceStepModel,
    prompt: str,
    lyrics: str = "",
    duration_seconds: float = 30.0,
    seed: int = 42,
) -> Audio:
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    if not prompt.strip() and not lyrics.strip():
        raise ValueError("ACE-Step needs a prompt or lyrics")
    if duration_seconds <= 0:
        raise ValueError("ACE-Step duration_seconds must be positive")
    params = GenerationParams(
        caption=prompt,
        lyrics=lyrics if lyrics.strip() else "[Instrumental]",
        instrumental=not bool(lyrics.strip()),
        duration=duration_seconds,
        seed=int(seed),
        thinking=False,
        use_cot_metas=False,
        use_cot_caption=False,
        use_cot_language=False,
    )
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(seed)], audio_format="wav")
    with tempfile.TemporaryDirectory(prefix="ssui-ace-step-") as output_dir:
        result = generate_music(model.dit_handler, None, params, config, save_dir=output_dir)
        if not result.success or not result.audios:
            raise RuntimeError(f"ACE-Step generation failed: {result.error or result.status_message}")
        item = result.audios[0]
        source_path = item.get("path")
        if not source_path or not os.path.isfile(source_path):
            raise RuntimeError("ACE-Step returned no saved WAV file")
        descriptor, output_path = tempfile.mkstemp(prefix="ssui-ace-step-", suffix=".wav")
        os.close(descriptor)
        shutil.copyfile(source_path, output_path)
        return Audio(format="wav", path=output_path, sample_rate=item.get("sample_rate", 48000))
