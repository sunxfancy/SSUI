# SPDX-License-Identifier: Apache-2.0
"""MediaPipe Tasks adapter for the existing RGB face annotation entry point."""
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

import cv2
import mediapipe as mp
import numpy as np

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
MODEL_SHA256 = '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'


def _model_path(explicit=None):
    explicit = explicit or os.environ.get('SSUI_MEDIAPIPE_FACE_MODEL')
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f'Face landmarker model not found: {path}')
        return path
    cache = Path(os.environ.get('SSUI_MODEL_CACHE', Path.home() / '.cache/ssui')) / 'mediapipe'
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / 'face_landmarker.task'
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256:
        return path
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.download', delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with urlopen(MODEL_URL, timeout=60) as src, temporary.open('wb') as dest:
            while chunk := src.read(1024 * 1024):
                dest.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != MODEL_SHA256:
            raise RuntimeError('Face landmarker model SHA256 mismatch')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _draw_faces(image, faces):
    height, width = image.shape[:2]
    canvas = np.zeros_like(image)
    connections = mp.tasks.vision.FaceLandmarksConnections
    styles = (
        (connections.FACE_LANDMARKS_FACE_OVAL, (10, 200, 10)),
        (connections.FACE_LANDMARKS_LEFT_EYE, (180, 200, 10)),
        (connections.FACE_LANDMARKS_LEFT_EYEBROW, (180, 220, 10)),
        (connections.FACE_LANDMARKS_RIGHT_EYE, (10, 200, 180)),
        (connections.FACE_LANDMARKS_RIGHT_EYEBROW, (10, 220, 180)),
        (connections.FACE_LANDMARKS_LIPS, (10, 180, 10)),
    )
    for face in faces:
        if min((max(p.x for p in face) - min(p.x for p in face)) * width,
               (max(p.y for p in face) - min(p.y for p in face)) * height) < 64:
            continue
        points = [(int(p.x * width), int(p.y * height))
                  if 0 <= p.x < 1 and 0 <= p.y < 1 else None for p in face]
        for edges, color in styles:
            for edge in edges:
                start, end = points[edge.start], points[edge.end]
                if start is not None and end is not None:
                    cv2.line(canvas, start, end, color, thickness=2)
        for index, color in ((468, (10, 200, 250)), (473, (250, 200, 10))):
            if index < len(points) and points[index] is not None:
                cv2.circle(canvas, points[index], 2, color, thickness=-1)
    return canvas[:, :, ::-1].copy()


def generate_annotation(img_rgb, max_faces=1, min_confidence=0.5, *, model_path=None):
    if img_rgb.ndim != 3 or img_rgb.shape[2] != 3 or img_rgb.dtype != np.uint8:
        raise ValueError('Face annotation expects an HxWx3 uint8 RGB image')
    if max_faces < 1 or not 0 <= min_confidence <= 1:
        raise ValueError('Invalid face count or detection confidence')
    base = mp.tasks.BaseOptions
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=base(model_asset_path=str(_model_path(model_path)), delegate=base.Delegate.CPU),
        num_faces=max_faces, min_face_detection_confidence=min_confidence,
        min_face_presence_confidence=min_confidence)
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(img_rgb))
        return _draw_faces(img_rgb, detector.detect(image).face_landmarks)
