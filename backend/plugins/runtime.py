"""Default service implementations. No model libraries are imported at startup."""
from __future__ import annotations

import importlib
import inspect
from importlib.util import find_spec
import subprocess
import threading
from typing import Any

from backend.contracts.services import CapabilityProvider, ExecutionContext


class TorchDevices:
    def select(self) -> str:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"


class ModelStore:
    """For pipeline objects; existing tensor-level ModelCache remains authoritative."""
    def __init__(self):
        self._models = {}
        self._lock = threading.RLock()

    def get_or_load(self, key, load):
        with self._lock:
            if key not in self._models:
                self._models[key] = load()
            return self._models[key]

    def clear(self):
        with self._lock:
            self._models.clear()

    close = clear


class SubprocessRunner:
    def run(self, command, *, context: ExecutionContext, env=None) -> str:
        context.check_cancelled()
        # Output is read on a separate thread so cancellation also works when
        # a native process produces no output for a long time.
        process = subprocess.Popen(list(command), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
        lines = []
        completed = threading.Event()
        def wait():
            try:
                process.wait()
            finally:
                completed.set()
        def read():
            assert process.stdout is not None
            for line in process.stdout:
                lines.append(line)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        waiter = threading.Thread(target=wait, daemon=True)
        waiter.start()
        cursor = 0
        try:
            while not completed.is_set():
                context.check_cancelled()
                while cursor < len(lines):
                    context.progress(lines[cursor])
                    cursor += 1
                context.cancelled.wait(0.05)
            reader.join()
            for line in lines[cursor:]:
                context.progress(line)
            context.check_cancelled()
            output = "".join(lines)
            if process.returncode:
                raise RuntimeError(f"Process exited with {process.returncode}: {output[-5000:]}")
            return output
        finally:
            if not completed.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            reader.join(timeout=5)
            if process.stdout and hasattr(process.stdout, "close"):
                process.stdout.close()


class ModuleCapability:
    """Lazy adapter for a migrated module, with explicitly injected operations."""
    def __init__(self, module: str, arguments: dict[str, dict[str, Any]] | None = None):
        self.module_name = module
        self.arguments = arguments or {}
        self._lock = threading.RLock()
        self.required_modules: tuple[str, ...] = ()

    def missing_dependencies(self) -> list[str]:
        return [name for name in self.required_modules if find_spec(name) is None]

    def module(self):
        return importlib.import_module(self.module_name)

    def call(self, operation: str, *args, **kwargs):
        supplied = self.arguments.get(operation, {})
        if supplied.keys() & kwargs.keys():
            raise TypeError("Injected dependencies cannot be overridden by inference arguments")
        with self._lock:
            target = self.module()
            for part in operation.split("."):
                target = getattr(target, part)
            if "context" in inspect.signature(target).parameters and "context" not in kwargs:
                kwargs["context"] = ExecutionContext()
            return target(*args, **kwargs, **supplied)


class LegacyModelLoader:
    """Executor-owned facade over the existing registered loader and ModelCache."""
    def __init__(self):
        self._loader = None
        self._lock = threading.RLock()

    def load_model(self, model_config, submodel_type=None):
        with self._lock:
            if self._loader is None:
                from backend.plugins.image.api.model import ModelLoaderService
                self._loader = ModelLoaderService()
            return self._loader.load_model(model_config, submodel_type)

    def close(self):
        self._loader = None


class InjectedOperation:
    """Bind a provider's operation at assembly time, without importing it."""
    def __init__(self, provider: CapabilityProvider, operation: str):
        self._provider = provider
        self._operation = operation

    def __call__(self, *args, **kwargs):
        return self._provider.call(self._operation, *args, **kwargs)
