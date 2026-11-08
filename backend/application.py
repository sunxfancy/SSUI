"""Composition root: the sole place that selects concrete backend providers."""
from backend.plugins import Plugin, PluginRegistry
from backend.plugins.runtime import InjectedOperation, LegacyModelLoader, ModuleCapability, ModelStore, SubprocessRunner, TorchDevices


# Entries are import paths, never eagerly imported inference implementations.
MODULES = {
    "image": ("SD1", "SDXL", "Flux", "Flux2", "PixelArt"),
    "video": ("AnimateDiff", "CogVideo", "Hunyuan", "LTX2", "MiniMaxH3", "QwenImage", "Wan", "Wan2", "Wan22"),
    "voice": ("Cosyvoice",),
    "llm": ("Qwen",),
    "mesh": ("WorldClaw", "Trellis", "Pixal3D", "StdGEN"),
    "motion": ("Kimodo", "pose", "bvh", "blender", "nodes"),
}

RUNTIME_IMPORTS = {
    "motion.Kimodo": ("kimodo", "torch", "transformers"),
    "motion.pose": ("mediapipe", "cv2"),
    "video.LTX2": ("ltx_pipelines", "torch", "transformers"),
    "video.MiniMaxH3": ("diffusers", "torch", "transformers", "av"),
    "voice.Cosyvoice": ("hyperpyyaml", "inflect", "whisper", "tn", "torchaudio"),
    "mesh.Pixal3D": ("cumesh", "o_voxel", "flex_gemm"),
    "mesh.Trellis": ("nvdiffrast", "kaolin", "spconv"),
}


def create_application(*, services=None, bindings=None, external=True):
    from backend.plugins.vendor import install_bundled_packages
    install_bundled_packages()
    registry = PluginRegistry()
    registry.register(Plugin("image.pixel_finisher", ("image.pixel_finisher",),
        lambda pixel_art: {"image.pixel_finisher": InjectedOperation(pixel_art, "finalize_pixel_art_image")},
        requires={"pixel_art": "image.PixelArt"}))
    for family, modules in MODULES.items():
        for name in modules:
            key = f"{family}.{name}"
            path = f"backend.plugins.{family}.{name}"
            if key == "video.QwenImage":
                def factory(finisher, path=path, key=key):
                    return {key: ModuleCapability(path, {
                        "QwenPixelArtGenerate": {"finisher": finisher},
                        "QwenPixelArtEdit": {"finisher": finisher},
                    })}
                registry.register(Plugin(key, (key,), factory,
                    requires={"finisher": "image.pixel_finisher"}))
            elif key == "motion.nodes":
                def factory(pose, blender, path=path, key=key):
                    return {key: ModuleCapability(path, {
                        "RecognizePose": {"recognizer": InjectedOperation(pose, "recognize_pose")},
                        "RenderBlenderComparison": {"renderer": InjectedOperation(blender, "render_blender_comparison")},
                    })}
                registry.register(Plugin(key, (key,), factory,
                    requires={"pose": "motion.pose", "blender": "motion.blender"}))
            elif key == "motion.blender":
                def factory(bvh, path=path, key=key):
                    return {key: ModuleCapability(path, {
                        "render_blender_comparison": {"exporter": InjectedOperation(bvh, "export_bvh")},
                    })}
                registry.register(Plugin(key, (key,), factory, requires={"bvh": "motion.bvh"}))
            elif key in ("image.SD1", "image.SDXL", "image.Flux"):
                def factory(model_loader, path=path, key=key, name=name):
                    family_name = {"SD1": "SD1", "SDXL": "SDXL", "Flux": "Flux"}[name]
                    operations = ["getModelLoader", f"{family_name}Model.load",
                        f"{family_name}Lora.load", f"{family_name}Lora.load_one",
                        f"{family_name}ControlNet.load"]
                    return {key: ModuleCapability(path, {
                        operation: {"model_loader": model_loader} for operation in operations})}
                registry.register(Plugin(key, (key,), factory,
                    requires={"model_loader": "model_loader"}))
            elif key == "image.Flux2":
                def factory(devices, models, path=path, key=key):
                    return {key: ModuleCapability(path, {
                        "Flux2KleinModel.load": {"devices": devices, "model_store": models},
                        "Flux2KleinModel.clear_cache": {"model_store": models},
                    })}
                registry.register(Plugin(key, (key,), factory,
                    requires={"devices": "devices", "models": "models"}))
            elif key in ("video.MiniMaxH3", "video.LTX2", "motion.Kimodo"):
                operations = {
                    "video.MiniMaxH3": ("_run_h3", "H3TextToVideo", "H3ImageToVideo"),
                    "video.LTX2": ("_run_ltx", "LTX2TextToVideo", "LTX2ImageToVideo"),
                    "motion.Kimodo": ("_run_kimodo", "KimodoTextToMotion",),
                }[key]
                def factory(processes, path=path, key=key, operations=operations):
                    return {key: ModuleCapability(path, {
                        operation: {"process_runner": processes} for operation in operations})}
                registry.register(Plugin(key, (key,), factory, requires={"processes": "processes"}))
            else:
                def factory(path=path, key=key):
                    return {key: ModuleCapability(path)}
                registry.register(Plugin(key, (key,), factory))
    if external:
        registry.discover()
    defaults = {"devices": TorchDevices(), "models": ModelStore(), "processes": SubprocessRunner(),
        "model_loader": LegacyModelLoader()}
    defaults.update(services or {})
    app = registry.assemble(defaults, bindings)
    for key, capability in app.capabilities.items():
        if isinstance(capability, ModuleCapability):
            capability.required_modules = RUNTIME_IMPORTS.get(key, ())
    # Services are owned by this executor's application, not module singletons.
    app._resources[:0] = [defaults[name] for name in ("models", "model_loader")
        if name not in (services or {})]
    return app
