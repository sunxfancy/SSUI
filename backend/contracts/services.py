"""Interfaces shared by independently installed inference plugins."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any, Callable, Mapping, Protocol, Sequence

if TYPE_CHECKING:
    from backend.contracts.media import Image


class InferenceConfig(Protocol):
    def __getitem__(self, name: str) -> Any: ...
    def __contains__(self, name: str) -> bool: ...
    def __call__(self, name: str) -> InferenceConfig: ...
    def is_prepare(self) -> bool: ...


class PixelFinisher(Protocol):
    def __call__(self, image: Image, **options: Any) -> Image: ...


class CapabilityProvider(Protocol):
    """Assembly-time operation binding, including external plugin providers."""
    def call(self, operation: str, *args: Any, **kwargs: Any) -> Any: ...


class ProcessRunner(Protocol):
    def run(self, command: Sequence[str], *, context: ExecutionContext,
            env: Mapping[str, str] | None = None) -> str: ...


class DeviceService(Protocol):
    def select(self) -> str: ...


class ModelStore(Protocol):
    def get_or_load(self, key: Any, load: Callable[[], Any]) -> Any: ...
    def clear(self) -> None: ...


class ModelLoader(Protocol):
    def load_model(self, model_config: Any, submodel_type: Any = None) -> Any: ...


@dataclass
class ExecutionContext:
    """One invocation's state; never store this on a shared model instance."""
    output_dir: Path = field(default_factory=lambda: Path.cwd() / "output")
    seed: int = 0
    cancelled: Event = field(default_factory=Event)
    progress: Callable[[str], None] = print

    def check_cancelled(self) -> None:
        if self.cancelled.is_set():
            raise InterruptedError("Inference cancelled")
