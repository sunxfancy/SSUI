"""SDK composition boundary. Workflow adapters capture injected capabilities.

Direct Python imports get a standalone application. SSLoader scopes adapter
calls to its executor-owned application, including concurrent workflows.
"""
import functools
import inspect
import sys
from types import ModuleType
from contextlib import contextmanager
from contextvars import ContextVar


_application = ContextVar("ssui_workflow_backend", default=None)


def public_type_module(module):
    """Preserve workflow/UI wire names while backend owns the Python classes."""
    if module == "backend.contracts.media":
        return "ssui.base"
    for family, package in (("image", "ssui_image"), ("video", "ssui_video"),
            ("mesh", "ssui_3dmodel"), ("motion", "ssui_motion"),
            ("voice", "ssui_voice"), ("llm", "ssui_llm")):
        prefix = f"backend.plugins.{family}."
        if module.startswith(prefix):
            return package + "." + module[len(prefix):]
    return module


@contextmanager
def backend_scope(application):
    """Application boundary only; inference implementations never access this."""
    token = _application.set(application)
    try:
        yield
    finally:
        _application.reset(token)


def bind_module(namespace, capability):
    namespace["_capability"] = capability


def initialize_adapter(namespace, key):
    from backend.application import create_application
    application = create_application(external=False)
    capability = application.capabilities[key]
    implementation = capability.module()
    namespace.update({k: v for k, v in vars(implementation).items() if not k.startswith("__")})
    namespace["_implementation"] = implementation
    namespace["_capability"] = capability
    namespace["_standalone_application"] = application

    # Preserve legacy monkey-patch locations while implementations move. This
    # forwarding is confined to the compatibility boundary, never used for DI.
    patches = {}
    class CompatibilityModule(ModuleType):
        def __setattr__(self, name, value):
            if name in vars(implementation) and not name.startswith("__"):
                stack = patches.setdefault(name, [])
                if stack and value is stack[-1][0]:
                    _, original = stack.pop()
                    setattr(implementation, name, original)
                else:
                    stack.append((vars(self).get(name), getattr(implementation, name)))
                    setattr(implementation, name, value)
            super().__setattr__(name, value)
    sys.modules[namespace["__name__"]].__class__ = CompatibilityModule

    def bind_backend(application):
        standalone = namespace.pop("_standalone_application", None)
        if standalone is not None:
            standalone.close()
        bind_module(namespace, application.capabilities[key])
    namespace["bind_backend"] = bind_backend

    def delegate(name):
        target = implementation
        for part in name.split("."):
            target = getattr(target, part)
        @functools.wraps(target)
        def invoke(*args, **kwargs):
            app = _application.get()
            selected = app.capabilities[key] if app is not None else namespace["_capability"]
            return selected.call(name, *args, **kwargs)
        # Injected arguments are backend implementation details, never SDK ports.
        signature = inspect.signature(target)
        injected = capability.arguments.get(name, {})
        invoke.__signature__ = signature.replace(parameters=[
            p for p in signature.parameters.values() if p.name not in injected and p.name != "context"])
        return invoke

    # Keep model-loading APIs callable from old workflows, while injecting their
    # dependencies at this boundary rather than inside backend classes.
    for name, value in list(namespace.items()):
        if not inspect.isclass(value) or value.__module__ != implementation.__name__:
            continue
        methods = {}
        for operation in capability.arguments:
            if operation.startswith(name + "."):
                methods[operation.split(".", 1)[1]] = staticmethod(delegate(operation))
        if methods:
            namespace[name] = type(name, (value,), {"__module__": namespace["__name__"], **methods})
    for operation in capability.arguments:
        if "." not in operation:
            namespace[operation] = delegate(operation)
    return delegate
