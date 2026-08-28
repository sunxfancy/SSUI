from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from PIL import Image as PILImage

from ssui import SkeletonAnimation, Video

from .bvh import export_bvh


def _output_root(animation: SkeletonAnimation) -> Path:
    if animation.source:
        source = Path(animation.source).expanduser().resolve()
        if source.parent.name.lower() == "input":
            return source.parent.parent / "output"
    return Path.cwd() / "output"


def _blender_executable(explicit: str | None) -> str | None:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Blender executable not found: {path}")
        return str(path.resolve())
    configured = os.environ.get("BLENDER_EXECUTABLE")
    if configured:
        return _blender_executable(configured)
    command = shutil.which("blender") or shutil.which("blender.exe")
    if command:
        return command
    candidates = []
    if sys.platform == "darwin":
        candidates.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
    elif os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidates.extend(sorted(
            (program_files / "Blender Foundation").glob("Blender */blender.exe"),
            reverse=True,
        ))
    return str(candidates[0]) if candidates else None


def _run_blender(arguments: list[str], explicit: str | None) -> None:
    executable = _blender_executable(explicit)
    if executable:
        subprocess.run([executable, *arguments], check=True)
        return
    if os.name != "nt":
        raise RuntimeError(
            "Blender was not found. Add it to PATH or set BLENDER_EXECUTABLE."
        )

    helper = Path(__file__).resolve().parent.parent / "blender" / "run_msix_blender.ps1"
    if not helper.is_file():
        raise RuntimeError("The Blender MSIX launcher is missing from the Motion extension")
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("PowerShell is required to launch Microsoft Store Blender")
    subprocess.run([
        powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper),
        "-Arguments", subprocess.list2cmdline(arguments), "-Wait",
    ], check=True)


def render_blender_comparison(
    animation: SkeletonAnimation,
    output_dir: str | Path | None = None,
    blender_executable: str | None = None,
) -> Video:
    """Render source landmarks beside Blender's imported BVH reconstruction."""

    if not animation.frames:
        raise ValueError("Skeleton animation has no frames")
    root = Path(output_dir).expanduser().resolve() if output_dir else (
        _output_root(animation) / f"blender_comparison_{uuid.uuid4().hex}"
    )
    root.mkdir(parents=True, exist_ok=True)
    bvh_path = root / "motion.bvh"
    export = export_bvh(animation, bvh_path)
    retarget_path = bvh_path.with_suffix(".retarget.json")
    script = Path(__file__).resolve().parent.parent / "blender" / "reconstruct_and_compare.py"
    arguments = [
        "--background", "--factory-startup", "--python", str(script), "--",
        "--bvh", str(bvh_path), "--retarget", str(retarget_path),
        "--output-dir", str(root), "--render",
    ]
    _run_blender(arguments, blender_executable)

    scene_path = root / "pose-comparison.blend"
    report_path = root / "blender-comparison.json"
    frame_paths = sorted((root / "frames").glob("pose-comparison-*.png"))
    if not scene_path.is_file() or not report_path.is_file() or not frame_paths:
        raise RuntimeError(f"Blender did not produce complete comparison artifacts in {root}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    frames = []
    for path in frame_paths:
        with PILImage.open(path) as image:
            frames.append(image.convert("RGB").copy())
    return Video(
        "mp4", frames=frames, fps=animation.fps,
        metadata={
            "kind": "blender_comparison",
            "scene_path": str(scene_path),
            "report_path": str(report_path),
            "bvh_path": str(bvh_path),
            "retarget_path": str(retarget_path),
            "blender_version": report.get("blender_version"),
            "comparison_rmse": report.get("rmse"),
            "comparison_max_error": report.get("max_error"),
            "source_retarget_rmse": export.report.get("rmse"),
        },
    )
