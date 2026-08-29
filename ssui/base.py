import PIL.Image
import trimesh
from dataclasses import asdict, dataclass, field
from typing import Any

class Image():
    def __init__(self, image: PIL.Image.Image = None):
        self._image = image

    @staticmethod
    def load(path: str) -> "Image":
        with PIL.Image.open(path) as image:
            return Image(image.convert("RGB").copy())

class Mesh():
    def __init__(self, model: trimesh.Trimesh = None):
        self._model = model

    @staticmethod
    def load(path: str) -> "Mesh":
        return Mesh(trimesh.load(path, force="scene"))

class Video():
    def __init__(self, format: str = "mp4", frames: list[PIL.Image.Image] = None, fps: float = 30, video: str = None, path: str = None, metadata: dict[str, Any] = None):
        self._format = format
        self._frames = frames
        self._fps = fps
        # Upload components historically send {"video": path}; ``path`` is the
        # clearer spelling for programmatic callers.  Keep both compatible.
        self._path = path or video
        self._metadata = metadata or {}

    @property
    def path(self):
        return self._path

    @property
    def frames(self):
        return self._frames

    @property
    def fps(self):
        return self._fps

    @property
    def metadata(self):
        return self._metadata


@dataclass
class PoseLandmark:
    """One normalized body landmark.

    x/y are normalized image coordinates. z is MediaPipe's relative depth;
    world_x/y/z are metric model-space coordinates when the detector provides
    them.
    """

    name: str
    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.0
    presence: float = 0.0
    world_x: float | None = None
    world_y: float | None = None
    world_z: float | None = None


@dataclass
class PoseFrame:
    frame_index: int
    timestamp: float
    landmarks: list[PoseLandmark] = field(default_factory=list)
    detected: bool = True


@dataclass
class SkeletonAnimation:
    """Time-indexed pose data suitable for preview, editing, and retargeting."""

    frames: list[PoseFrame] = field(default_factory=list)
    fps: float = 30.0
    width: int = 0
    height: int = 0
    source: str | None = None
    model: str = "mediapipe-pose-33"
    coordinate_system: str = "image-normalized+x-right+y-down; world+x-right+y-up"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return self.frames[-1].timestamp if self.frames else 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class Audio():
    def __init__(
        self,
        format: str = "wav",
        audio: Any = None,
        fps: int = 16000,
        path: str = None,
        sample_rate: int = None,
    ):
        self._format = format
        self._audio = audio
        self._fps = sample_rate or fps
        self._path = path

    @staticmethod
    def load(path: str) -> "Audio":
        extension = path.rsplit(".", 1)[-1] if "." in path else "wav"
        return Audio(format=extension, path=path)

    @property
    def path(self):
        return self._path

    @property
    def sample_rate(self):
        return self._fps

class Voice(Audio):
    def __init__(self, format: str = "wav", audio: Any = None, fps: int = 16000, text: str = None, path: str = None):
        super().__init__(format=format, audio=audio, fps=fps, path=path)
        self._text = text


class Prompt():
    @staticmethod
    def create(text: str):
        return Prompt(text)

    def __init__(self, text: str):
        self._text = text
    
    def __str__(self):
        return self._text

    @property
    def text(self):
        return self._text


class Noise():
    def __init__(self, config):
        self.config = config
