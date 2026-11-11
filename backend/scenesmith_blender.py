"""Optional native Blender preview for SceneSmith GLB scenes."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


def render_scene_preview(glb: str | Path, output_dir: str | Path,
                         blender_executable: str | None = None) -> tuple[Path, Path]:
    source = Path(glb).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    preview = output / "preview.png"
    blend = output / "scene.blend"
    script = Path(__file__).with_name("scenesmith_blender_render.py")
    arguments = ["--background", "--factory-startup", "--python", str(script), "--",
                 str(source), str(preview), str(blend)]
    executable = blender_executable or os.environ.get("BLENDER_EXECUTABLE") or shutil.which("blender") or shutil.which("blender.exe")
    if executable:
        if not Path(executable).is_file():
            raise FileNotFoundError(executable)
        command = [executable, *arguments]
    elif os.name == "nt":
        helper = Path(__file__).resolve().parents[1] / "extensions/Motion/blender/run_msix_blender.ps1"
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not helper.is_file() or not powershell:
            raise RuntimeError("Native Blender launcher is unavailable")
        helper_quoted = str(helper).replace("'", "''")
        arguments_quoted = subprocess.list2cmdline(arguments).replace("'", "''")
        script_call = f"& '{helper_quoted}' -Arguments '{arguments_quoted}' -Wait"
        command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script_call]
    else:
        raise RuntimeError("Blender not found; set BLENDER_EXECUTABLE")
    log = output / "blender.log"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=600, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode or not preview.is_file() or not blend.is_file():
        raise RuntimeError(f"Blender preview failed; see {log}")
    return preview, blend
