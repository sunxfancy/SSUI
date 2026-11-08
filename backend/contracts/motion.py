"""Data and callable contracts shared by independent Motion plugins."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from backend.contracts.media import SkeletonAnimation, Video


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
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_gap_frames < 0:
            raise ValueError("max_gap_frames cannot be negative")


class PoseRecognizer(Protocol):
    def __call__(self, video: Video, options: PoseRecognitionOptions) -> tuple[Video, SkeletonAnimation]: ...


class BVHExportResult(Protocol):
    report: dict[str, Any]


class BVHExporter(Protocol):
    def __call__(self, animation: SkeletonAnimation, path: str | Path) -> BVHExportResult: ...


class BlenderRenderer(Protocol):
    def __call__(self, animation: SkeletonAnimation, output_dir: str | Path | None = None,
                 blender_executable: str | None = None) -> Video: ...
