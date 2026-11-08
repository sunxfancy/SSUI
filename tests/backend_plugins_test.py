"""Behavioral tests for dependency injection, isolation and lifecycle."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

from backend.plugins import AssemblyError, Plugin, PluginRegistry, PluginState
from backend.plugins.runtime import ModelStore


class BackendPluginsTest(unittest.TestCase):
    def test_injection_and_reverse_cleanup(self):
        events = []
        class Service:
            def __init__(self, name): self.name = name
            def close(self): events.append(self.name)
        registry = PluginRegistry()
        registry.register(Plugin("consumer", ("consumer",),
            lambda dependency: {"consumer": Service(dependency.name + ".consumer")},
            requires={"dependency": "service"}))
        registry.register(Plugin("provider", ("service",), lambda: {"service": Service("provider")}))
        with registry.assemble() as app:
            self.assertEqual(app.capabilities["consumer"].name, "provider.consumer")
        self.assertEqual(events, ["provider.consumer", "provider"])

    def test_cycles_report_chain(self):
        registry = PluginRegistry()
        registry.register(Plugin("first", ("a",), lambda other: {"a": other}, requires={"other": "b"}))
        registry.register(Plugin("second", ("b",), lambda other: {"b": other}, requires={"other": "a"}))
        with self.assertRaisesRegex(AssemblyError, "first -> second -> first"):
            registry.assemble()

    def test_missing_and_failed_plugins_do_not_break_unrelated_capabilities(self):
        registry = PluginRegistry()
        registry.register(Plugin("missing", ("missing",), lambda dependency: {}, requires={"dependency": "absent"}))
        def fail(): raise RuntimeError("incompatible runtime")
        registry.register(Plugin("failed", ("failed",), fail))
        registry.register(Plugin("healthy", ("healthy",), lambda: {"healthy": 42}))
        app = registry.assemble()
        self.assertEqual(app.capabilities["healthy"], 42)
        self.assertEqual(app.states["missing"][0], PluginState.MISSING_DEPENDENCY)
        self.assertEqual(app.states["failed"][0], PluginState.FAILED)

    def test_optional_dependency_and_explicit_provider(self):
        registry = PluginRegistry()
        for name in ("one", "two"):
            registry.register(Plugin(name, ("service",), lambda name=name: {"service": name}))
        registry.register(Plugin("consumer", ("consumer",), lambda optional: {"consumer": optional}, optional={"optional": "absent"}))
        with self.assertRaisesRegex(AssemblyError, "Ambiguous"):
            registry.assemble()
        app = registry.assemble(bindings={"service": "two"})
        self.assertEqual(app.capabilities["service"], "two")
        self.assertIsNone(app.capabilities["consumer"])

    def test_duplicate_and_incompatible_api_are_rejected(self):
        registry = PluginRegistry()
        plugin = Plugin("one", ("one",), lambda: {"one": 1})
        registry.register(plugin)
        with self.assertRaisesRegex(AssemblyError, "Duplicate"):
            registry.register(plugin)
        with self.assertRaisesRegex(AssemblyError, "Unsupported"):
            registry.register(Plugin("two", ("two",), lambda: {}, api_version=2))

    def test_model_stores_are_per_application(self):
        a, b = ModelStore(), ModelStore()
        first = a.get_or_load("model", object)
        self.assertIs(a.get_or_load("model", object), first)
        self.assertIsNot(b.get_or_load("model", object), first)
        a.clear()
        self.assertIsNot(a.get_or_load("model", object), first)

    def test_discovery_does_not_import_inference_libraries(self):
        result = subprocess.run([sys.executable, "-c", "from backend.application import create_application; "
            "import sys; app = create_application(external=False); "
            "assert 'torch' not in sys.modules; assert 'diffusers' not in sys.modules; app.close()"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backend_does_not_import_sdk_or_other_plugin_families(self):
        root = Path(__file__).resolve().parents[1] / "backend"
        for path in root.rglob("*.py"):
            if "vendor" in path.parts:
                continue
            family = path.relative_to(root).parts
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                imports = ([node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else
                    [a.name for a in node.names] if isinstance(node, ast.Import) else [])
                for name in imports:
                    self.assertFalse(name.split(".")[0] in ("ssui", "server", "extensions"), (path, name))
                    if len(family) > 2 and family[0] == "plugins" and name.startswith("backend.plugins."):
                        self.assertEqual(name.split(".")[2], family[1], (path, name))

    def test_registered_plugins_do_not_import_each_other_even_in_same_family(self):
        from importlib.util import resolve_name
        from backend.application import MODULES
        root = Path(__file__).resolve().parents[1]
        entries = {f"backend.plugins.{family}.{module}"
            for family, modules in MODULES.items() for module in modules}
        for consumer in entries:
            source = root.joinpath(*consumer.split(".")).with_suffix(".py")
            for node in ast.walk(ast.parse(source.read_text())):
                imported = []
                if isinstance(node, ast.ImportFrom):
                    target = node.module or ""
                    if node.level:
                        target = resolve_name("." * node.level + target, consumer.rsplit(".", 1)[0])
                    imported = [target, *(target + "." + alias.name for alias in node.names)]
                elif isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                for target in imported:
                    self.assertFalse(target in entries and target != consumer,
                        f"{consumer} directly imports plugin {target}; inject a contract instead")

    def test_motion_nodes_use_injected_peer_providers(self):
        from backend.application import create_application
        from backend.contracts.media import SkeletonAnimation, Video
        from backend.contracts.motion import PoseRecognitionOptions
        calls = []
        class Provider:
            def __init__(self, result): self.result = result
            def call(self, operation, *args, **kwargs):
                calls.append((operation, args, kwargs))
                return self.result
        class Config(dict):
            def is_prepare(self): return False
        overlay, skeleton = Video(), SkeletonAnimation()
        rendered = Video()
        with create_application(external=False, services={
            "motion.pose": Provider((overlay, skeleton)),
            "motion.blender": Provider(rendered),
        }) as app:
            nodes = app.capabilities["motion.nodes"]
            result = nodes.call("RecognizePose", Config(model_path="model.task",
                sample_fps=12, detection_confidence=0.6, tracking_confidence=0.7,
                smoothing=0.2, max_gap_frames=2), Video())
            self.assertEqual(result, (overlay, skeleton))
            self.assertIsInstance(calls[0][1][1], PoseRecognitionOptions)
            self.assertEqual(calls[0][1][1].sample_fps, 12)
            self.assertIs(nodes.call("RenderBlenderComparison",
                Config(blender_executable="custom-blender"), skeleton), rendered)
        self.assertEqual([call[0] for call in calls], ["recognize_pose", "render_blender_comparison"])
        self.assertEqual(calls[-1][2], {"blender_executable": "custom-blender"})

    def test_pixel_finishing_follows_registered_image_provider(self):
        from unittest.mock import Mock
        from backend.application import create_application
        replacement = Mock()
        replacement.call.return_value = object()
        image = object()
        with create_application(external=False, services={"image.PixelArt": replacement}) as app:
            result = app.capabilities["image.pixel_finisher"](image, width=32)
            self.assertIs(result, replacement.call.return_value)
        replacement.call.assert_called_once_with("finalize_pixel_art_image", image, width=32)

    def test_blender_uses_injected_bvh_provider(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import Mock
        from backend.application import create_application
        from backend.contracts.media import SkeletonAnimation
        replacement = Mock()
        replacement.call.side_effect = RuntimeError("replacement BVH exporter")
        with TemporaryDirectory() as directory, create_application(external=False,
                services={"motion.bvh": replacement}) as app:
            animation = SkeletonAnimation(frames=[object()])
            with self.assertRaisesRegex(RuntimeError, "replacement BVH exporter"):
                app.capabilities["motion.blender"].call("render_blender_comparison",
                    animation, output_dir=directory)
            replacement.call.assert_called_once_with("export_bvh", animation, Path(directory) / "motion.bvh")

    def test_workflow_applications_do_not_share_injected_capabilities(self):
        from concurrent.futures import ThreadPoolExecutor
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from ss_executor.loader import SSLoader
        class Capability:
            def __init__(self, label): self.label = label
            def call(self, operation, *args, **kwargs): return self.label
        with TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.py"
            path.write_text('from ssui import workflow, Prompt\n'
                'from ssui.config import SSUIConfig\n'
                'from ssui_video.MiniMaxH3 import H3TextToVideo\n'
                'config = SSUIConfig()\n'
                '@workflow\ndef run() -> str:\n'
                '    return H3TextToVideo(config("H3"), Prompt("test"))\n')
            functions = []
            for label in ("first", "second"):
                app = SimpleNamespace(capabilities={"video.MiniMaxH3": Capability(label)})
                loader = SSLoader(use_sandbox=False, backend_application=app)
                loader.load(str(path))
                loader.Execute()
                functions.append(loader.callables[0][0])
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda function: function(), functions))
            self.assertEqual(results, ["first", "second"])

    def test_runner_reports_failures_and_honors_pre_cancel(self):
        from backend.contracts.services import ExecutionContext
        from backend.plugins.runtime import SubprocessRunner
        runner = SubprocessRunner()
        context = ExecutionContext(progress=lambda line: None)
        with self.assertRaisesRegex(RuntimeError, "7.*diagnostic"):
            runner.run([sys.executable, "-c", "print('diagnostic'); raise SystemExit(7)"], context=context)
        context.cancelled.set()
        with self.assertRaises(InterruptedError):
            runner.run([sys.executable, "-c", "raise SystemExit(0)"], context=context)

    def test_sdk_wire_type_names_remain_compatible(self):
        from ssui.backend_adapter import public_type_module
        from ssui.base import Image
        from backend.contracts.media import Image as BackendImage
        self.assertIs(Image, BackendImage)
        self.assertEqual(public_type_module(Image.__module__), "ssui.base")
        self.assertEqual(public_type_module("backend.plugins.image.SD1"), "ssui_image.SD1")

    def test_external_entrypoint_registers_without_special_treatment(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        def register(registry):
            registry.register(Plugin("external", ("external",), lambda: {"external": 123}))
        entry = SimpleNamespace(name="external", load=lambda: register)
        registry = PluginRegistry()
        with patch("backend.plugins.registry.entry_points", return_value=[entry]):
            registry.discover()
        self.assertEqual(registry.assemble().capabilities["external"], 123)


if __name__ == "__main__":
    unittest.main()
