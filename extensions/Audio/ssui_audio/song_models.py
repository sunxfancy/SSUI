"""Optional adapters for full-song models.

The heavyweight upstream projects and checkpoints are deliberately installed by
the user, outside SSUI's shared environment.  Importing this module is cheap.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import os
import importlib.util
from pathlib import Path


def generate_song(
    model: str,
    prompt: str,
    lyrics: str,
    output_path: str | Path,
    *,
    source_dir: str | Path | None = None,
    checkpoint_dir: str | Path | None = None,
    vae_dir: str | Path | None = None,
    dependency_dir: str | Path | None = None,
    duration_seconds: int = 95,
    device: str = "cuda",
    python_executable: str | Path = sys.executable,
) -> dict[str, str]:
    """Generate one song, returning its output path and model name.

    YuE2 must be installed into the selected Python environment. HeartMuLa and
    DiffRhythm use the official upstream scripts from ``source_dir`` and can
    use a separate ``python_executable``. DiffRhythm lyrics must be LRC text.
    """
    key = model.lower().replace("-", "").replace("_", "")
    if key not in {"yue2", "heartmula", "diffrhythm"}:
        raise ValueError(f"Unsupported song model: {model}")
    if not prompt.strip():
        raise ValueError("A style prompt is required")
    if not lyrics.strip():
        raise ValueError("Lyrics are required for song generation")
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    if key == "yue2":
        if destination.suffix.lower() != ".flac":
            raise ValueError("YuE2 output must be a .flac file")
        if source_dir is not None:
            source = Path(source_dir).expanduser().resolve()
            package_root = source / "src" if (source / "src" / "yue2").is_dir() else source
            if not (package_root / "yue2").is_dir():
                raise FileNotFoundError(f"YuE2 source package not found in: {source}")
            # Support an isolated upstream checkout without installing into
            # SSUI's shared ROCm Python environment.
            if str(package_root) not in sys.path:
                sys.path.insert(0, str(package_root))
        try:
            import torch
            from yue2 import YuE2Pipeline
        except ImportError as exc:
            raise RuntimeError("Install the official YuE2 package in the selected Python environment") from exc
        model_id = str(checkpoint_dir) if checkpoint_dir else "m-a-p/YuE2-3B"
        is_rocm = torch.version.hip is not None
        # On Windows ROCm 7.2, upstream CUDA graph flash attention fails with
        # `mha_varlen_fwd: seqused_k must be nullopt`; its eager backend works.
        # The VAE's MIOpen conv1d path can fail with miopenStatusUnknownError.
        old_miopen = torch.backends.cudnn.enabled
        with tempfile.TemporaryDirectory(prefix="ssui-yue2-") as tmp:
            try:
                if is_rocm:
                    torch.backends.cudnn.enabled = False
                with YuE2Pipeline.from_pretrained(
                    model_id,
                    vae=str(vae_dir) if vae_dir else "m-a-p/YuE2-Vae",
                    device=device,
                    backend="torch-eager" if is_rocm else "torch",
                ) as pipe:
                    result = pipe(style=prompt, lyrics=lyrics)
                    result.save_artifacts(tmp)
            finally:
                torch.backends.cudnn.enabled = old_miopen
            generated = Path(tmp) / "audio.flac"
            if not generated.is_file():
                raise RuntimeError("YuE2 finished without audio.flac")
            shutil.copyfile(generated, destination)
    else:
        if source_dir is None:
            raise ValueError(f"{model} requires source_dir pointing to its official checkout")
        source = Path(source_dir).expanduser().resolve()
        if key == "heartmula":
            if destination.suffix.lower() != ".mp3":
                raise ValueError("HeartMuLa output must be an .mp3 file")
            if checkpoint_dir is None:
                raise ValueError("HeartMuLa requires checkpoint_dir")
            if dependency_dir is None:
                candidate = source.parent / "heart-rocm-site"
                if candidate.is_dir():
                    dependency_dir = candidate
            rocm_paths = []
            rocm_environment = {}
            if dependency_dir and Path(dependency_dir).name == "heart-rocm-site":
                repository = Path(__file__).resolve().parents[3]
                rocm_paths = [
                    Path(__file__).resolve().parent / "heart_rocm_shim",
                    source / "src",
                ]
                if importlib.util.find_spec("vector_quantize_pytorch") is None:
                    rocm_paths.append(repository / ".build" / "vector-quantize-pytorch")
                if any(importlib.util.find_spec(name) is None for name in ("loguru", "xxhash", "einx")):
                    rocm_paths.append(repository / ".build" / "ace-step-1.5" / ".deps")
                missing = [str(path) for path in rocm_paths if not path.is_dir()]
                if missing:
                    raise RuntimeError(f"HeartMuLa ROCm setup is incomplete: {missing}")
                rocm_environment["SSUI_HEARTMULA_DEPS"] = str(Path(dependency_dir).resolve())
            script = (
                Path(__file__).resolve().parent / "heart_rocm_runner.py"
                if rocm_paths else source / "examples" / "run_music_generation.py"
            )
            with tempfile.TemporaryDirectory(prefix="ssui-heartmula-") as tmp:
                lyrics_file, tags_file = Path(tmp) / "lyrics.txt", Path(tmp) / "tags.txt"
                lyrics_file.write_text(lyrics, encoding="utf-8")
                tags_file.write_text(prompt, encoding="utf-8")
                _run(script, source, python_executable, [
                    "--model_path", str(Path(checkpoint_dir).expanduser().resolve()),
                    "--version", "3B", "--lyrics", str(lyrics_file),
                    "--tags", str(tags_file), "--save_path", str(destination),
                    "--max_audio_length_ms", str(int(duration_seconds * 1000)),
                    "--mula_device", device, "--codec_device", device,
                    "--lazy_load", "true",
                ], dependency_dir=dependency_dir, extra_paths=rocm_paths, extra_environment=rocm_environment)
        else:
            if destination.suffix.lower() != ".wav":
                raise ValueError("DiffRhythm output must be a .wav file")
            if duration_seconds != 95 and not 96 <= duration_seconds <= 285:
                raise ValueError("DiffRhythm duration must be 95 or 96–285 seconds")
            if "[" not in lyrics:
                raise ValueError("DiffRhythm requires timestamped LRC lyrics")
            if dependency_dir is None:
                for name in ("diff-compat-site", "diff-site"):
                    candidate = source.parent / name
                    if candidate.is_dir():
                        dependency_dir = candidate
                        break
            diff_environment = {"PYTHONIOENCODING": "utf-8"}
            espeak_root = Path(os.environ.get("SSUI_ESPEAK_ROOT", source.parent / "espeak-ng" / "eSpeak NG"))
            espeak_library = espeak_root / "libespeak-ng.dll"
            if espeak_library.is_file():
                diff_environment.update({
                    "PHONEMIZER_ESPEAK_LIBRARY": str(espeak_library),
                    "PHONEMIZER_ESPEAK_PATH": str(espeak_root),
                    "ESPEAK_DATA_PATH": str(espeak_root),
                    "PATH": str(espeak_root) + os.pathsep + os.environ.get("PATH", ""),
                })
            script = source / "infer" / "infer.py"
            with tempfile.TemporaryDirectory(prefix="ssui-diffrhythm-") as tmp:
                lrc_file = Path(tmp) / "lyrics.lrc"
                lrc_file.write_text(lyrics, encoding="utf-8")
                _run(script, source, python_executable, [
                    "--lrc-path", str(lrc_file), "--ref-prompt", prompt,
                    "--audio-length", str(duration_seconds), "--output-dir", tmp,
                    "--chunked",
                ], dependency_dir=dependency_dir, extra_environment=diff_environment)
                generated = Path(tmp) / "output.wav"
                if not generated.is_file():
                    raise RuntimeError("DiffRhythm finished without output.wav")
                shutil.copyfile(generated, destination)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"{model} finished without a nonempty audio file")
    return {"model": model, "output_path": str(destination)}


def _run(
    script: Path,
    source: Path,
    python: str | Path,
    arguments: list[str],
    *,
    dependency_dir: str | Path | None = None,
    extra_paths: list[Path] | None = None,
    extra_environment: dict[str, str] | None = None,
) -> None:
    if not script.is_file():
        raise FileNotFoundError(f"Official inference script not found: {script}")
    environment = os.environ.copy()
    environment.update(extra_environment or {})
    if dependency_dir:
        overlay = str(Path(dependency_dir).expanduser().resolve())
        paths = [str(path) for path in extra_paths or []] + [overlay, str(source)]
        environment["PYTHONPATH"] = os.pathsep.join(filter(None, (*paths, environment.get("PYTHONPATH"))))
    subprocess.run([str(python), str(script), *arguments], cwd=source, env=environment, check=True)
