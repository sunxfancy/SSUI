"""Explicit constructor injection. Only the composition root uses this registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib.metadata import entry_points
from typing import Any, Callable, Mapping


class AssemblyError(ValueError):
    pass


class PluginState(str, Enum):
    AVAILABLE = "available"
    MISSING_DEPENDENCY = "missing_dependency"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class Plugin:
    id: str
    provides: tuple[str, ...]
    factory: Callable[..., Mapping[str, Any]]
    requires: Mapping[str, str] = field(default_factory=dict)
    optional: Mapping[str, str] = field(default_factory=dict)
    api_version: int = 1
    # A lightweight check only: no imports of torch, pipeline libraries or weights.
    check: Callable[[], tuple[PluginState, str] | None] | None = None


@dataclass
class Assembly:
    capabilities: dict[str, Any]
    states: dict[str, tuple[PluginState, str]]
    _resources: list[Any] = field(default_factory=list, repr=False)

    def close(self) -> None:
        errors = []
        for resource in reversed(self._resources):
            try:
                close = getattr(resource, "close", None)
                if close:
                    close()
            except Exception as exc:
                errors.append(exc)
        self._resources.clear()
        if errors:
            raise RuntimeError(f"Failed to close {len(errors)} plugin resource(s)") from errors[0]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        if plugin.id in self._plugins:
            raise AssemblyError(f"Duplicate plugin ID: {plugin.id}")
        if plugin.api_version != 1:
            raise AssemblyError(f"Unsupported plugin API {plugin.api_version}: {plugin.id}")
        if not plugin.provides or len(set(plugin.provides)) != len(plugin.provides):
            raise AssemblyError(f"Invalid capability declarations: {plugin.id}")
        if set(plugin.requires) & set(plugin.optional):
            raise AssemblyError(f"Duplicate dependency arguments: {plugin.id}")
        self._plugins[plugin.id] = plugin

    def discover(self) -> None:
        for entry in sorted(entry_points(group="ssui.backend_plugins"), key=lambda e: e.name):
            entry.load()(self)

    def assemble(self, services: Mapping[str, Any] | None = None,
                 bindings: Mapping[str, str] | None = None) -> Assembly:
        services, bindings = dict(services or {}), dict(bindings or {})
        providers: dict[str, list[str]] = {}
        states: dict[str, tuple[PluginState, str]] = {}
        for plugin in self._plugins.values():
            try:
                issue = plugin.check() if plugin.check else None
            except Exception as exc:
                issue = (PluginState.FAILED, f"{type(exc).__name__}: {exc}")
            if issue:
                states[plugin.id] = issue
            for capability in plugin.provides:
                providers.setdefault(capability, []).append(plugin.id)
        for capability, provider in bindings.items():
            if provider not in providers.get(capability, []):
                raise AssemblyError(f"Invalid binding {capability} -> {provider}")
        selected = {}
        for capability, candidates in providers.items():
            if capability in services:
                continue
            available = [p for p in candidates if p not in states]
            if capability in bindings:
                selected[capability] = bindings[capability]
            elif len(available) == 1:
                selected[capability] = available[0]
            elif len(available) > 1:
                raise AssemblyError(f"Ambiguous capability {capability}: {', '.join(available)}")

        assembly = Assembly(services.copy(), states)
        stack: list[str] = []
        built: dict[str, Mapping[str, Any]] = {}

        def build(plugin_id: str) -> None:
            if plugin_id in built or plugin_id in states:
                return
            if plugin_id in stack:
                raise AssemblyError("Dependency cycle: " + " -> ".join(stack + [plugin_id]))
            plugin = self._plugins[plugin_id]
            stack.append(plugin_id)
            arguments = {}
            for argument, capability in {**plugin.requires, **plugin.optional}.items():
                if capability not in assembly.capabilities:
                    provider = selected.get(capability)
                    if provider:
                        build(provider)
                value = assembly.capabilities.get(capability)
                if value is None and argument in plugin.requires:
                    states[plugin_id] = (PluginState.MISSING_DEPENDENCY,
                        " -> ".join(stack + [capability]))
                    stack.pop()
                    return
                arguments[argument] = value
            try:
                exports = dict(plugin.factory(**arguments))
                if set(exports) != set(plugin.provides):
                    raise AssemblyError(f"Invalid exports for {plugin_id}: expected {plugin.provides}")
                built[plugin_id] = exports
                for capability, value in exports.items():
                    if selected.get(capability) == plugin_id:
                        assembly.capabilities[capability] = value
                    if all(value is not old for old in assembly._resources):
                        assembly._resources.append(value)
            except Exception as exc:
                states[plugin_id] = (PluginState.FAILED, f"{type(exc).__name__}: {exc}")
            else:
                states[plugin_id] = (PluginState.AVAILABLE, "")
            stack.pop()

        try:
            for plugin_id in dict.fromkeys(selected.values()):
                build(plugin_id)
        except BaseException:
            assembly.close()
            raise
        return assembly
