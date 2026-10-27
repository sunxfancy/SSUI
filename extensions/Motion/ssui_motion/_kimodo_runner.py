"""Internal Kimodo CLI wrapper with an opt-in local text-encoder override."""

import os
import json
import sys


def _write_motion_manifest(output_stem: str, fps: float, metadata: dict) -> None:
    import numpy as np
    from kimodo.skeleton import build_skeleton

    with np.load(output_stem + ".npz", allow_pickle=False) as data:
        positions = data["posed_joints"]
    if positions.ndim != 3 or not len(positions) or positions.shape[-1] != 3 or not np.isfinite(positions).all():
        raise ValueError("Kimodo generated invalid 3D joint positions")
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("Kimodo generated an invalid frame rate")
    skeleton = build_skeleton(positions.shape[1])
    manifest = {"schema": "ssui.motion.clip/v1", "fps": fps, "units": "meters", "metadata": metadata,
                "coordinate_system": "Y-up;+Z-forward", "joint_names": skeleton.bone_order_names,
                "parents": skeleton.joint_parents.tolist(), "positions": positions.tolist()}
    with open(output_stem + ".motion.json", "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, allow_nan=False)


def _configure_text_encoder_override() -> None:
    base_model = os.environ.get("SSUI_KIMODO_TEXT_ENCODER_BASE")
    if not base_model:
        return

    from kimodo.model.load_model import TEXT_ENCODER_PRESETS
    from kimodo.model.llm2vec.llm2vec import LLM2Vec

    TEXT_ENCODER_PRESETS["llm2vec"]["kwargs"]["base_model_name_or_path"] = (
        base_model
    )

    # The supported fallback is the same Llama 3 Instruct base with the MNTP
    # adapter merged. Its local config intentionally has no upstream repo name,
    # so preserve the instruction framing expected by the official encoder.
    original_prepare = LLM2Vec.prepare_for_tokenization

    def prepare_for_tokenization(self, text):
        if "Llama-3-8B-Instruct-LLM2Vec-mntp-merged" in base_model:
            return (
                "<|start_header_id|>user<|end_header_id|>\n\n"
                + text.strip()
                + "<|eot_id|>"
            )
        return original_prepare(self, text)

    LLM2Vec.prepare_for_tokenization = prepare_for_tokenization


def main() -> None:
    _configure_text_encoder_override()
    from kimodo.scripts import generate
    import torch

    original_load = generate.load_model
    metadata = {"torch": torch.__version__, "cuda": torch.version.cuda,
                "text_encoder_base": os.environ.get("SSUI_KIMODO_TEXT_ENCODER_BASE", "official"),
                "postprocessed": "--no-postprocess" not in sys.argv}
    timing = {}
    def capture_model(*args, **kwargs):
        result = original_load(*args, **kwargs)
        model = result[0] if isinstance(result, tuple) else result
        timing["fps"] = float(model.fps)
        metadata["inference_device"] = str(next(model.denoiser.parameters()).device)
        return result
    generate.load_model = capture_model
    try:
        generate.main()
    finally:
        generate.load_model = original_load
    if "--output" in sys.argv:
        _write_motion_manifest(sys.argv[sys.argv.index("--output") + 1], timing["fps"], metadata)


if __name__ == "__main__":
    main()
