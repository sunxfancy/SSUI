"""Place a 3D mesh on a tracked plane in an uploaded video.

The automatic anchor is a visual suggestion.  A normalized user click overrides
it; neither mode claims to understand the named surface in the prompt.
"""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import urllib.request
import json
import base64

import numpy as np

from ssui.annotation import param
from ssui.base import Mesh, Prompt, Video
from ssui.config import SSUIConfig
from ssui.controller import Slider
from uuid import uuid4


def _location_hint(prompt: str) -> tuple[float, float]:
    text = prompt.lower()
    x = .25 if any(w in text for w in ("左", "left")) else .75 if any(w in text for w in ("右", "right")) else .5
    y = .3 if any(w in text for w in ("上", "顶部", "top")) else .8 if any(w in text for w in ("地面", "桌面", "底部", "floor", "table", "bottom")) else .65
    return x, y


def _suggest_anchor(frame, prompt: str):
    """Use an optional grounded vision service, then a low-confidence hint."""
    import cv2
    endpoint = os.environ.get("SSUI_SCENE_GROUNDER_URL")
    if not endpoint:
        return _location_hint(prompt), "spatial_text_hint", .2
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Cannot encode the reference frame for scene grounding")
    request = urllib.request.Request(
        endpoint,
        json.dumps({"prompt": prompt, "image_jpeg_base64": base64.b64encode(encoded).decode("ascii")}).encode(),
        {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    point = result.get("point")
    confidence = result.get("confidence")
    if not isinstance(point, list) or len(point) != 2 or not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in point):
        raise ValueError("Scene grounder must return {'point': [x, y], 'confidence': 0..1}")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("Scene grounder confidence must be in [0, 1]")
    return (float(point[0]), float(point[1])), "vision_grounder", float(confidence)


def _mux_source_audio(rendered: Path, source: Path) -> bool:
    """Keep the source soundtrack when an ffmpeg executable is available."""
    try:
        import imageio_ffmpeg
    except ImportError:
        return False
    temporary = rendered.with_name(rendered.stem + "-audio-" + uuid4().hex + rendered.suffix)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(rendered), "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?",
               "-c:v", "copy", "-c:a", "aac", "-shortest", str(temporary)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Audio mux failed: {result.stderr[-1000:]}")
    os.replace(temporary, rendered)
    return True


def _mesh_geometry(mesh: Mesh):
    import trimesh
    if mesh.path:
        scene = trimesh.load(mesh.path, force="scene", process=False)
    elif mesh._model is not None:
        scene = mesh._model
    else:
        raise ValueError("A path-backed or in-memory Mesh is required")
    if isinstance(scene, trimesh.Scene):
        scene = scene.to_geometry()
    if not isinstance(scene, trimesh.Trimesh) or len(scene.faces) == 0:
        raise ValueError("The mesh has no renderable triangles")
    # Keep the CPU preview bounded for dense generated assets.
    if len(scene.faces) > 20000:
        raise ValueError("Preview renderer supports at most 20,000 triangles; simplify the mesh first")
    vertices = np.asarray(scene.vertices, np.float32).copy()
    vertices -= (vertices.min(axis=0) + vertices.max(axis=0)) / 2
    extent = float(np.max(vertices.max(axis=0) - vertices.min(axis=0)))
    if extent <= 0:
        raise ValueError("The mesh has zero size")
    vertices /= extent
    vertices[:, 2] -= vertices[:, 2].min()
    return vertices, np.asarray(scene.faces, np.int32)


def _render(frame, vertices, faces, center, size, rotation=0.0):
    """Small software rasterizer with a z buffer and directional lighting."""
    import cv2
    height, width = frame.shape[:2]
    theta = np.deg2rad(rotation)
    rotation_matrix = np.array([[np.cos(theta), -np.sin(theta), 0],
                                [np.sin(theta), np.cos(theta), 0], [0, 0, 1]], np.float32)
    points = vertices @ rotation_matrix.T
    # Orthographic camera with a visible top face. The tracked image point is
    # the ground contact point; apparent size is configured in image pixels.
    xy = np.column_stack((center[0] + size * (points[:, 0] + .35 * points[:, 1]),
                          center[1] + size * (.25 * points[:, 1] - .85 * points[:, 2])))
    depth = points[:, 1] + points[:, 2] * .1
    overlay = frame.copy()
    zbuf = np.full((height, width), -np.inf, np.float32)
    light = np.array([-.4, -.5, 1.0], np.float32)
    light /= np.linalg.norm(light)
    for triangle in faces:
        coords = xy[triangle]
        x0, y0 = np.floor(coords.min(axis=0)).astype(int)
        x1, y1 = np.ceil(coords.max(axis=0)).astype(int)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width - 1, x1), min(height - 1, y1)
        if x1 <= x0 or y1 <= y0:
            continue
        a, b, c = coords
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denominator) < 1e-5:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        u = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / denominator
        v = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / denominator
        w = 1 - u - v
        region = zbuf[y0:y1 + 1, x0:x1 + 1]
        z = u * depth[triangle[0]] + v * depth[triangle[1]] + w * depth[triangle[2]]
        mask = (u >= 0) & (v >= 0) & (w >= 0) & (z > region)
        if not np.any(mask):
            continue
        normal = np.cross(points[triangle[1]] - points[triangle[0]], points[triangle[2]] - points[triangle[0]])
        normal /= max(np.linalg.norm(normal), 1e-6)
        shade = .45 + .5 * abs(float(normal @ light))
        color = np.array([210, 165, 90], np.float32) * shade  # BGR preview material
        overlay[y0:y1 + 1, x0:x1 + 1][mask] = color.astype(np.uint8)
        region[mask] = z[mask]
    # Subtle contact shadow, limited to the surface around the anchor.
    shadow = np.zeros((height, width), np.uint8)
    cv2.ellipse(shadow, tuple(np.rint(center).astype(int)),
                (max(2, int(size * .48)), max(1, int(size * .12))), 0, 0, 360, 100, -1)
    shadow = cv2.GaussianBlur(shadow, (0, 0), max(1, size * .06))
    object_mask = np.any(overlay != frame, axis=2)
    darkened = (frame.astype(np.float32) * (1 - shadow[..., None] / 650)).astype(np.uint8)
    darkened[object_mask] = overlay[object_mask]
    return darkened


def composite_scene(video: Video, mesh: Mesh, prompt: Prompt, *, anchor_x: float = -1,
                    anchor_y: float = -1, size: float = .25, rotation: float = 0,
                    output_path: str | None = None) -> Video:
    import cv2
    if not video.path or not Path(video.path).is_file():
        raise ValueError("A path-backed uploaded video is required")
    if (anchor_x < 0) != (anchor_y < 0):
        raise ValueError("Provide both anchor coordinates, or neither")
    if anchor_x >= 0 and not (0 <= anchor_x <= 1 and 0 <= anchor_y <= 1):
        raise ValueError("Anchor coordinates must be normalized to [0, 1]")
    if not 0 < size <= 2:
        raise ValueError("size must be in (0, 2]")
    vertices, faces = _mesh_geometry(mesh)
    capture = cv2.VideoCapture(video.path)
    imageio_reader = None
    if not capture.isOpened():
        import imageio.v2 as imageio
        imageio_reader = imageio.get_reader(video.path, format="ffmpeg")
        capture.release()
    try:
        if imageio_reader is None:
            ok, first = capture.read()
        else:
            try:
                first = cv2.cvtColor(imageio_reader.get_data(0), cv2.COLOR_RGB2BGR)
                ok = True
            except StopIteration:
                ok, first = False, None
        if not ok:
            raise ValueError("The video has no frames")
        height, width = first.shape[:2]
        fps = (capture.get(cv2.CAP_PROP_FPS) if imageio_reader is None else imageio_reader.get_meta_data().get("fps")) or video.fps or 30
        uploaded = video.metadata or {}
        clicked = uploaded.get("anchor_x"), uploaded.get("anchor_y")
        manual = anchor_x >= 0 or all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in clicked)
        if manual:
            normalized = (anchor_x, anchor_y) if anchor_x >= 0 else clicked
            anchor_source, anchor_confidence = "manual", 1.0
        else:
            normalized, anchor_source, anchor_confidence = _suggest_anchor(first, str(prompt))
        center = np.array([normalized[0] * width, normalized[1] * height], np.float32)
        gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
        features = cv2.goodFeaturesToTrack(gray, 300, .01, 8)
        if features is None or len(features) < 8:
            raise ValueError("Insufficient scene texture for anchor tracking")
        first_points = features.reshape(-1, 2)
        output = Path(output_path) if output_path else Path(video.path).parent / f"ssui-scene-{uuid4().hex}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        use_imageio = not writer.isOpened()
        if use_imageio:
            writer.release()
            import imageio.v2 as imageio
            writer = imageio.get_writer(str(output), fps=fps, codec="libx264", macro_block_size=1)
        previous_gray = gray
        previous_points = first_points.reshape(-1, 1, 2)
        frame = first
        frames = 0
        confidences = []
        tracked_scale = 1.0
        tracked_rotation = 0.0
        scale_values = [1.0]
        try:
            while True:
                current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if frames:
                    next_points, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, current_gray, previous_points, None)
                    if next_points is None:
                        raise RuntimeError(f"Anchor tracking failed at frame {frames}")
                    valid = status.ravel().astype(bool)
                    old = previous_points.reshape(-1, 2)[valid]
                    new = next_points.reshape(-1, 2)[valid]
                    if len(old) < 8:
                        raise RuntimeError(f"Too few tracked points at frame {frames}")
                    transform, inliers = cv2.estimateAffinePartial2D(old, new, method=cv2.RANSAC)
                    if transform is None or inliers is None:
                        raise RuntimeError(f"Camera motion solve failed at frame {frames}")
                    confidence = float(inliers.mean())
                    if confidence < .4:
                        raise RuntimeError(f"Low camera tracking confidence at frame {frames}: {confidence:.2f}")
                    confidences.append(confidence)
                    center = cv2.transform(center.reshape(1, 1, 2), transform).reshape(2)
                    relative_scale = float(np.hypot(transform[0, 0], transform[1, 0]))
                    tracked_scale *= relative_scale
                    tracked_rotation += float(np.degrees(np.arctan2(transform[1, 0], transform[0, 0])))
                    if not .2 <= tracked_scale <= 5:
                        raise RuntimeError(f"Implausible tracked scale at frame {frames}: {tracked_scale:.2f}")
                    scale_values.append(tracked_scale)
                    previous_points = new.reshape(-1, 1, 2)
                composed = _render(frame, vertices, faces, center,
                                   min(width, height) * size * tracked_scale,
                                   rotation + tracked_rotation)
                if use_imageio:
                    writer.append_data(cv2.cvtColor(composed, cv2.COLOR_BGR2RGB))
                else:
                    writer.write(composed)
                frames += 1
                previous_gray = current_gray
                if imageio_reader is None:
                    ok, frame = capture.read()
                else:
                    try:
                        frame = cv2.cvtColor(imageio_reader.get_data(frames), cv2.COLOR_RGB2BGR)
                        ok = True
                    except (IndexError, StopIteration):
                        ok, frame = False, None
                if not ok:
                    break
        finally:
            writer.close() if use_imageio else writer.release()
        audio_muxed = _mux_source_audio(output, Path(video.path))
        return Video(path=str(output), fps=fps, metadata={
            "source": video.path, "anchor_source": anchor_source,
            "anchor_x": normalized[0], "anchor_y": normalized[1], "anchor_confidence": anchor_confidence,
            "tracking_confidence": min(confidences, default=1.0),
            "scale_range": [min(scale_values), max(scale_values)], "audio_muxed": audio_muxed,
            "frames": frames, "limitations": "Preview uses a tracked 2D plane and orthographic mesh rendering; no depth occlusion or recovered 3D camera."})
    finally:
        capture.release()
        if imageio_reader is not None:
            imageio_reader.close()


@param("anchor_x", Slider(-1, 1, .01), default=-1)
@param("anchor_y", Slider(-1, 1, .01), default=-1)
@param("size", Slider(.05, 1, .01), default=.25)
@param("rotation", Slider(-180, 180, 1), default=0)
def Composite3DPreview(config: SSUIConfig, video: Video, mesh: Mesh, prompt: Prompt) -> Video:
    """CPU preview; use -1 for both anchor values to use the text suggestion."""
    if config.is_prepare():
        return Video()
    return composite_scene(video, mesh, prompt, anchor_x=float(config["anchor_x"]),
                           anchor_y=float(config["anchor_y"]), size=float(config["size"]),
                           rotation=float(config["rotation"]))
