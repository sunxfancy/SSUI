from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol, Sequence
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
from PIL import Image as PILImage, ImageDraw

from ssui import PoseFrame, PoseLandmark, SkeletonAnimation, Video


LANDMARK_NAMES = (
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner",
    "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left",
    "mouth_right", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky", "left_index",
    "right_index", "left_thumb", "right_thumb", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel",
    "right_heel", "left_foot_index", "right_foot_index",
)

POSE_CONNECTIONS = (
    (0, 2), (2, 5), (5, 0), (2, 7), (5, 8), (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 29),
    (29, 31), (27, 31), (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
)

POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/1/pose_landmarker_full.task"
)


@dataclass(frozen=True)
class PoseRecognitionOptions:
    model_path: str | None = None
    sample_fps: float | None = None
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    smoothing: float = 0.45
    max_gap_frames: int = 3
    draw_confidence: float = 0.35

    def __post_init__(self):
        if self.sample_fps is not None and self.sample_fps <= 0:
            raise ValueError("sample_fps must be positive")
        for name in ("min_detection_confidence", "min_tracking_confidence", "smoothing", "draw_confidence"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_gap_frames < 0:
            raise ValueError("max_gap_frames cannot be negative")


class PoseDetector(Protocol):
    def detect(self, rgb_frame: np.ndarray, timestamp_ms: int = 0) -> tuple[Sequence[object], Sequence[object] | None] | None: ...
    def close(self) -> None: ...


class MediaPipePoseDetector:
    """Lazy MediaPipe adapter so importing workflows does not initialize a model."""

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: str | None = None,
    ):
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError(
                "MediaPipe Pose is unavailable. Install the Motion extension dependencies."
            ) from exc
        self._mp = mp
        self._uses_tasks = not hasattr(mp, "solutions")
        if not self._uses_tasks:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=False,
                enable_segmentation=False,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        else:
            asset = _ensure_pose_model(model_path)
            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=asset),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=min_detection_confidence,
                min_pose_presence_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                output_segmentation_masks=False,
            )
            self._pose = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def detect(self, rgb_frame: np.ndarray, timestamp_ms: int = 0):
        if self._uses_tasks:
            image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB,
                data=np.ascontiguousarray(rgb_frame),
            )
            result = self._pose.detect_for_video(image, timestamp_ms)
            if not result.pose_landmarks:
                return None
            world = result.pose_world_landmarks[0] if result.pose_world_landmarks else None
            return result.pose_landmarks[0], world
        result = self._pose.process(rgb_frame)
        if result.pose_landmarks is None:
            return None
        world = result.pose_world_landmarks.landmark if result.pose_world_landmarks else None
        return result.pose_landmarks.landmark, world

    def close(self):
        self._pose.close()


def _ensure_pose_model(model_path: str | None) -> str:
    if model_path:
        path = Path(model_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Pose model not found: {path}")
        return str(path)

    cache_root = Path(os.environ.get("SSUI_MODEL_CACHE", Path.home() / ".cache" / "ssui"))
    path = cache_root / "mediapipe" / "pose_landmarker_full.task"
    if path.is_file() and path.stat().st_size > 0:
        return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    try:
        with urlopen(POSE_MODEL_URL, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if temporary.stat().st_size == 0:
            raise RuntimeError("Downloaded pose model is empty")
        os.replace(temporary, path)
    except (OSError, URLError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "Unable to download the MediaPipe pose model. Set PoseRecognitionOptions.model_path "
            "to a local pose_landmarker .task file, or set SSUI_MODEL_CACHE to a writable cache."
        ) from exc
    return str(path)


def _read_frames(video: Video):
    if video.frames is not None:
        frames = [frame.convert("RGB") for frame in video.frames]
        if not frames:
            raise ValueError("Video contains no frames")
        yield from ((i, frame, float(video.fps or 30)) for i, frame in enumerate(frames))
        return
    if not video.path:
        raise ValueError("Video needs either a file path or in-memory frames")

    import cv2

    capture = cv2.VideoCapture(video.path)
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {video.path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or video.fps or 30)
    index = 0
    try:
        while True:
            ok, bgr = capture.read()
            if not ok:
                break
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            yield index, PILImage.fromarray(rgb), fps
            index += 1
    finally:
        capture.release()


def _landmarks(raw: Sequence[object], world: Sequence[object] | None) -> list[PoseLandmark]:
    result = []
    for index, point in enumerate(raw):
        world_point = world[index] if world is not None and index < len(world) else None
        result.append(PoseLandmark(
            name=LANDMARK_NAMES[index] if index < len(LANDMARK_NAMES) else f"landmark_{index}",
            x=float(point.x), y=float(point.y), z=float(point.z),
            visibility=float(getattr(point, "visibility", 0.0)),
            presence=float(getattr(point, "presence", 0.0)),
            world_x=float(world_point.x) if world_point is not None else None,
            world_y=float(world_point.y) if world_point is not None else None,
            world_z=float(world_point.z) if world_point is not None else None,
        ))
    return result


def _blend(previous: list[PoseLandmark], current: list[PoseLandmark], smoothing: float) -> list[PoseLandmark]:
    if len(previous) != len(current) or smoothing <= 0:
        return current
    keep = smoothing
    fresh = 1 - keep
    blended = []
    for old, new in zip(previous, current):
        values = {}
        for axis in ("x", "y", "z", "world_x", "world_y", "world_z"):
            a, b = getattr(old, axis), getattr(new, axis)
            values[axis] = b if a is None or b is None else a * keep + b * fresh
        blended.append(PoseLandmark(
            name=new.name, visibility=new.visibility, presence=new.presence, **values
        ))
    return blended


def _draw_pose(image: PILImage.Image, landmarks: list[PoseLandmark], confidence: float) -> PILImage.Image:
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    width, height = canvas.size
    for a, b in POSE_CONNECTIONS:
        if a >= len(landmarks) or b >= len(landmarks):
            continue
        pa, pb = landmarks[a], landmarks[b]
        if min(pa.visibility, pb.visibility) < confidence:
            continue
        draw.line((pa.x * width, pa.y * height, pb.x * width, pb.y * height), fill=(63, 224, 208, 225), width=max(2, width // 320))
    radius = max(2, width // 240)
    for point in landmarks:
        if point.visibility < confidence:
            continue
        x, y = point.x * width, point.y * height
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 190, 74, 255))
    return canvas


def recognize_pose(
    video: Video,
    options: PoseRecognitionOptions | None = None,
    detector: PoseDetector | None = None,
) -> tuple[Video, SkeletonAnimation]:
    """Recognize a single person's pose and return overlay video plus animation data."""

    options = options or PoseRecognitionOptions()
    owns_detector = detector is None
    detector = detector or MediaPipePoseDetector(
        options.min_detection_confidence, options.min_tracking_confidence, options.model_path
    )
    pose_frames: list[PoseFrame] = []
    overlay_frames: list[PILImage.Image] = []
    previous: list[PoseLandmark] = []
    missed = 0
    source_fps = float(video.fps or 30)
    output_fps = options.sample_fps or source_fps
    width = height = 0
    next_sample_time = 0.0
    try:
        for frame_index, image, actual_fps in _read_frames(video):
            source_fps = actual_fps
            output_fps = options.sample_fps or actual_fps
            timestamp = frame_index / actual_fps
            if options.sample_fps:
                if timestamp + 1e-9 < next_sample_time:
                    continue
                next_sample_time += 1.0 / options.sample_fps
            width, height = image.size
            found = detector.detect(np.asarray(image), round(timestamp * 1000))
            detected = found is not None
            if found is not None:
                current = _blend(previous, _landmarks(*found), options.smoothing)
                previous, missed = current, 0
            elif previous and missed < options.max_gap_frames:
                missed += 1
                current = [PoseLandmark(**{**point.__dict__, "visibility": point.visibility * (0.65 ** missed)}) for point in previous]
            else:
                missed += 1
                current = []
            pose_frames.append(PoseFrame(frame_index, timestamp, current, detected))
            overlay_frames.append(_draw_pose(image, current, options.draw_confidence))
    finally:
        if owns_detector:
            detector.close()

    animation = SkeletonAnimation(
        frames=pose_frames, fps=output_fps, width=width, height=height,
        source=video.path,
        metadata={"source_fps": source_fps, "sample_fps": output_fps, "landmark_count": len(LANDMARK_NAMES)},
    )
    return Video("mp4", overlay_frames, output_fps), animation
