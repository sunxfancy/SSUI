# Adapted from https://github.com/huggingface/controlnet_aux

from PIL import Image

from backend.image_util.mediapipe_face.mediapipe_face_common import generate_annotation
from backend.image_util.util import np_to_pil, pil_to_np


def detect_faces(image: Image.Image, max_faces: int = 1, min_confidence: float = 0.5, *, model_path=None) -> Image.Image:
    """Detects faces in an image using MediaPipe."""

    np_img = pil_to_np(image)
    kwargs = {'model_path': model_path} if model_path is not None else {}
    detected_map = generate_annotation(np_img, max_faces, min_confidence, **kwargs)
    detected_map_pil = np_to_pil(detected_map)
    return detected_map_pil
