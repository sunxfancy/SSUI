"""Use pinned official test assets to exercise SSUI face and pose adapters."""
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image

root = Path(os.environ['SSUI_ARM64_PROBE_ASSETS'])
pins = json.loads(Path(__file__).with_name('arm64-probe-assets.json').read_text())
for name, pin in pins.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == pin['sha256'], name
from backend.image_util.mediapipe_face import detect_faces
portrait = Image.open(root / 'portrait.jpg').convert('RGB')
annotated = detect_faces(portrait, model_path=root / 'face_landmarker.task')
assert annotated.size == portrait.size and np.asarray(annotated).any()
blank = detect_faces(Image.fromarray(np.zeros((128, 128, 3), dtype=np.uint8)), model_path=root / 'face_landmarker.task')
assert not np.asarray(blank).any()
os.environ['SSUI_MEDIAPIPE_FACE_MODEL'] = str(root / 'face_landmarker.task')
from controlnet_aux import MediapipeFaceDetector
assert MediapipeFaceDetector()(portrait, output_type='np').any()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions/Motion'))
from ssui_motion import MediaPipePoseDetector
detector = MediaPipePoseDetector(model_path=str(root / 'pose_landmarker_lite.task'))
try:
    image = np.asarray(Image.open(root / 'pose.jpg').convert('RGB'))
    for timestamp in (0, 33):
        landmarks, world = detector.detect(image, timestamp_ms=timestamp)
        assert len(landmarks) == 33 and len(world) == 33
finally:
    detector.close()
print('SSUI MediaPipe Tasks: positive face annotation, empty-image handling and CPU pose tracking passed')
