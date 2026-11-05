"""True 3D camera solve and GLB render in Blender for SSUI footage."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import numpy as np

from ssui.annotation import param
from ssui.base import Mesh, Prompt, Video
from ssui.config import SSUIConfig
from ssui.controller import Input, Slider

from .SceneComposite import _mux_source_audio, _suggest_anchor


def _load_frames(path: str, maximum: int):
    import imageio.v2 as imageio
    reader = imageio.get_reader(path, format="ffmpeg")
    frames = []
    try:
        fps = float(reader.get_meta_data().get("fps") or 30)
        for index in range(maximum + 1):
            try:
                frame = reader.get_data(index)
            except (IndexError, StopIteration):
                break
            if index == maximum:
                raise ValueError(f"Blender solve is limited to {maximum} frames per clip")
            frames.append(frame)
    finally:
        reader.close()
    if len(frames) < 12:
        raise ValueError("Blender camera solve needs at least 12 frames with camera parallax")
    return frames, fps


def _feature_tracks(frames):
    import cv2
    gray = cv2.cvtColor(frames[0], cv2.COLOR_RGB2GRAY)
    corners = cv2.goodFeaturesToTrack(gray, 400, .008, 7, blockSize=5)
    if corners is None or len(corners) < 12:
        raise ValueError("Not enough visual features for Blender camera solving")
    points = corners.astype(np.float32)
    history = [[(1, float(point[0][0]), float(point[0][1]))] for point in points]
    active = np.arange(len(points))
    for frame_index, image in enumerate(frames[1:], start=2):
        current = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        next_points, status, _ = cv2.calcOpticalFlowPyrLK(gray, current, points, None,
                                                          winSize=(21, 21), maxLevel=3)
        if next_points is None:
            break
        good = status.ravel().astype(bool)
        points = next_points[good]
        active = active[good]
        for identity, position in zip(active, points.reshape(-1, 2)):
            history[identity].append((frame_index, float(position[0]), float(position[1])))
        gray = current
        if len(active) < 12:
            break
    tracks = [history[index] for index in active if len(history[index]) == len(frames)]
    if len(tracks) < 12:
        raise ValueError(f"Only {len(tracks)} features survived the full clip; need at least 12")
    first = np.float32([[track[0][1], track[0][2]] for track in tracks])
    last = np.float32([[track[-1][1], track[-1][2]] for track in tracks])
    _, inliers = cv2.findFundamentalMat(first, last, cv2.FM_RANSAC, 1.5, .99)
    if inliers is None or int(inliers.sum()) < 12:
        raise ValueError("The footage lacks enough consistent 3D feature tracks")
    return [track for track, keep in zip(tracks, inliers.ravel()) if keep]


def _run_blender(manifest_path: Path, explicit: str | None):
    script = Path(__file__).with_name("blender_solve_render.py")
    args = ["--background", "--factory-startup", "--python", str(script), "--", str(manifest_path)]
    executable = explicit or os.environ.get("BLENDER_EXECUTABLE") or shutil.which("blender") or shutil.which("blender.exe")
    if executable:
        subprocess.run([executable, *args], check=True)
        return
    if os.name != "nt":
        raise FileNotFoundError("Blender not found; set BLENDER_EXECUTABLE")
    helper = Path(__file__).resolve().parents[1] / "blender" / "run_msix_blender.ps1"
    if not helper.is_file():
        raise FileNotFoundError("Blender not found; set BLENDER_EXECUTABLE")
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        raise FileNotFoundError("PowerShell is required for Microsoft Store Blender")
    helper_quoted = str(helper).replace("'", "''")
    arguments_quoted = subprocess.list2cmdline(args).replace("'", "''")
    script_call = f"& '{helper_quoted}' -Arguments '{arguments_quoted}' -Wait"
    subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script_call], check=True)


def blender_composite_scene(video: Video, mesh: Mesh, prompt: Prompt, *,
                            size: float = .25, focal_px: float = 0,
                            max_solve_error: float = 2.0,
                            blender_executable: str | None = None,
                            output_dir: str | None = None) -> Video:
    if not video.path or not Path(video.path).is_file():
        raise ValueError("A path-backed video is required")
    if not 0 < size <= 1:
        raise ValueError("size must be in (0, 1]")
    frames, fps = _load_frames(video.path, 150)
    height, width = frames[0].shape[:2]
    tracks = _feature_tracks(frames)
    uploaded = video.metadata or {}
    clicked = uploaded.get("anchor_x"), uploaded.get("anchor_y")
    if all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in clicked):
        anchor, anchor_source, anchor_confidence = clicked, "manual", 1.0
    else:
        import cv2
        anchor, anchor_source, anchor_confidence = _suggest_anchor(
            cv2.cvtColor(frames[0], cv2.COLOR_RGB2BGR), str(prompt))
    root = Path(output_dir) if output_dir else Path(video.path).parent / f"blender-scene-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    if mesh.path:
        mesh_path = Path(mesh.path).resolve()
    elif mesh._model is not None:
        mesh_path = root / "asset.glb"
        mesh._model.export(mesh_path)
    else:
        raise ValueError("A 3D mesh is required")
    if not mesh_path.is_file() or mesh_path.suffix.lower() not in {".glb", ".gltf"}:
        raise ValueError("Blender composite requires a GLB or glTF mesh")
    manifest = {"video_path": str(Path(video.path).resolve()), "mesh_path": str(mesh_path),
                "output_dir": str(root.resolve()), "width": width, "height": height,
                "fps": fps, "frames": len(frames), "tracks": tracks,
                "anchor": anchor, "size": size, "focal_px": focal_px or max(width, height),
                "max_solve_error": max_solve_error}
    manifest_path = root / "blender-input.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _run_blender(manifest_path, blender_executable)
    report_path = root / "solve.json"
    if not report_path.is_file():
        error_path = root / "blender-error.txt"
        detail = error_path.read_text(encoding="utf-8")[-3000:] if error_path.is_file() else "No solve report produced"
        raise RuntimeError(f"Blender camera solve failed: {detail}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    import imageio.v2 as imageio
    output = root / "composite.mp4"
    writer = imageio.get_writer(str(output), fps=fps, codec="libx264", macro_block_size=1)
    try:
        for index, background in enumerate(frames, start=1):
            path = root / "renders" / f"frame_{index:04d}.png"
            if not path.is_file():
                raise RuntimeError(f"Blender render is missing frame {index}")
            foreground = imageio.imread(path).astype(np.float32)
            if foreground.shape[:2] != background.shape[:2] or foreground.shape[2] != 4:
                raise RuntimeError(f"Blender render has invalid RGBA dimensions at frame {index}")
            alpha = foreground[:, :, 3:4] / 255
            combined = foreground[:, :, :3] * alpha + background.astype(np.float32) * (1 - alpha)
            writer.append_data(np.clip(combined, 0, 255).astype(np.uint8))
    finally:
        writer.close()
    audio_muxed = _mux_source_audio(output, Path(video.path))
    return Video(path=str(output), fps=fps, metadata={
        "kind": "blender_scene_composite", "scene_path": str(root / "scene.blend"),
        "report_path": str(report_path), "solve_error_px": report["solve_error_px"],
        "camera_frames": report["camera_frames"],
        "camera_translation_span": report["camera_translation_span"],
        "blender_version": report["blender_version"],
        "anchor_source": anchor_source, "anchor_confidence": anchor_confidence,
        "audio_muxed": audio_muxed})


@param("size", Slider(.05, 1, .01), default=.25)
@param("focal_px", Slider(0, 4000, 1), default=0)
@param("max_solve_error", Slider(.1, 5, .1), default=2.0)
@param("blender_executable", Input("Blender 可执行文件路径（可选）"), default="")
def CompositeWithBlender(config: SSUIConfig, video: Video, mesh: Mesh, prompt: Prompt) -> Video:
    if config.is_prepare():
        return Video()
    return blender_composite_scene(video, mesh, prompt,
                                   size=float(config["size"]), focal_px=float(config["focal_px"]),
                                   max_solve_error=float(config["max_solve_error"]),
                                   blender_executable=config["blender_executable"] or None)
