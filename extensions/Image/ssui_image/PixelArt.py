"""Deterministic pixel-art finishing and external source renderers."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image as PILImage

from ssui.annotation import param
from ssui.base import Image as SSUIImage
from ssui.config import SSUIConfig
from ssui.controller import Select, Slider, Switch


# Pillow 8 uses module-level constants; newer releases expose enum namespaces.
_RESAMPLING = getattr(PILImage, "Resampling", PILImage)
_QUANTIZE = getattr(PILImage, "Quantize", PILImage)
_DITHER = getattr(PILImage, "Dither", PILImage)


class AgentPaintAsset:
    def __init__(self, source_path: str = "", executable: str = "agentpaint"):
        self.source_path = source_path
        self.executable = executable

    @staticmethod
    def load(
        source_path: str,
        executable: str = "agentpaint",
    ) -> "AgentPaintAsset":
        path = _require_source(source_path, {".apx", ".apxa"})
        return AgentPaintAsset(str(path), executable)


class PixelSrcAsset:
    def __init__(self, source_path: str = "", executable: str = "pxl"):
        self.source_path = source_path
        self.executable = executable

    @staticmethod
    def load(source_path: str, executable: str = "pxl") -> "PixelSrcAsset":
        path = _require_source(source_path, {".pxl"})
        return PixelSrcAsset(str(path), executable)


def _require_source(source_path: str, suffixes: set[str]) -> Path:
    path = Path(source_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Pixel-art source does not exist: {path}")
    if path.suffix.lower() not in suffixes:
        expected = ", ".join(sorted(suffixes))
        raise ValueError(f"Expected a {expected} source, got: {path.suffix}")
    return path


def _resolve_executable(value: str) -> str:
    explicit = Path(value).expanduser()
    if explicit.parent != Path(".") or explicit.is_absolute():
        resolved = explicit.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Pixel-art CLI does not exist: {resolved}")
        return str(resolved)
    found = shutil.which(value)
    if found is None:
        raise FileNotFoundError(
            f"Could not find '{value}' on PATH; install the CLI or pass its full path"
        )
    return found


def _run_cli(command: list[str], timeout: int = 120) -> None:
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        creationflags=creationflags,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown error").strip()
        raise RuntimeError(f"Pixel-art CLI failed ({completed.returncode}): {detail}")


def _load_rendered(path: Path) -> SSUIImage:
    if not path.is_file():
        raise RuntimeError(f"Pixel-art CLI did not create its expected output: {path}")
    with PILImage.open(path) as image:
        return SSUIImage(image.convert("RGBA").copy())


@param("scale", Slider(1, 16, 1), default=1)
@param("frame", Slider(0, 255, 1), default=0)
def RenderAgentPaint(
    config: SSUIConfig,
    asset: AgentPaintAsset,
) -> SSUIImage:
    if config.is_prepare():
        return SSUIImage()
    source = _require_source(asset.source_path, {".apx", ".apxa"})
    executable = _resolve_executable(asset.executable)

    with tempfile.TemporaryDirectory(prefix="ssui-agentpaint-") as temp_dir:
        output = Path(temp_dir) / "render.png"
        if source.suffix.lower() == ".apxa":
            _run_cli([executable, "validate-animation", str(source)])
            command = [
                executable,
                "render-frame",
                str(source),
                "--frame",
                str(config["frame"]),
                "--out",
                str(output),
            ]
        else:
            _run_cli([executable, "validate", str(source)])
            command = [executable, "render", str(source), "--out", str(output)]
        _run_cli(command)
        rendered = _load_rendered(output)

    if config["scale"] > 1:
        image = rendered._image
        rendered = SSUIImage(
            image.resize(
                (image.width * config["scale"], image.height * config["scale"]),
                _RESAMPLING.NEAREST,
            )
        )
    return rendered


@param("scale", Slider(1, 16, 1), default=1)
@param("spritesheet", Switch(), default=False)
def RenderPixelSrc(
    config: SSUIConfig,
    asset: PixelSrcAsset,
) -> SSUIImage:
    if config.is_prepare():
        return SSUIImage()
    source = _require_source(asset.source_path, {".pxl"})
    executable = _resolve_executable(asset.executable)

    with tempfile.TemporaryDirectory(prefix="ssui-pixelsrc-") as temp_dir:
        output = Path(temp_dir) / "render.png"
        _run_cli([executable, "validate", str(source)])
        command = [executable, "render", str(source), "-o", str(output)]
        if config["scale"] > 1:
            command.extend(["--scale", str(config["scale"])])
        if config["spritesheet"]:
            command.append("--spritesheet")
        _run_cli(command)
        return _load_rendered(output)


@param("width", Slider(8, 512, 1), default=64)
@param("height", Slider(8, 512, 1), default=64)
@param("colors", Slider(2, 256, 1), default=24)
@param("alpha_threshold", Slider(0, 255, 1), default=128)
@param("downsample", Select("box", "nearest"), default="box")
@param("preview_scale", Slider(1, 16, 1), default=1)
def FinalizePixelArt(
    config: SSUIConfig,
    image: SSUIImage,
) -> SSUIImage:
    """Convert a generated image into a deterministic native pixel grid.

    This is intentionally a baseline, not a replacement for a learned pixel
    fixer. It gives Qwen-Image workflows a reproducible palette and alpha
    contract while keeping all processing local.
    """

    if config.is_prepare():
        return SSUIImage()
    if image is None or image._image is None:
        raise ValueError("FinalizePixelArt requires an input image")

    return finalize_pixel_art_image(
        image,
        width=config["width"],
        height=config["height"],
        colors=config["colors"],
        alpha_threshold=config["alpha_threshold"],
        downsample=config["downsample"],
        preview_scale=config["preview_scale"],
    )


def finalize_pixel_art_image(
    image: SSUIImage,
    *,
    width: int = 64,
    height: int = 64,
    colors: int = 24,
    alpha_threshold: int = 128,
    downsample: str = "box",
    preview_scale: int = 1,
) -> SSUIImage:
    """Apply the pixel-grid contract without requiring a second node config."""

    if image is None or image._image is None:
        raise ValueError("Pixel-art finalization requires an input image")
    if downsample not in {"box", "nearest"}:
        raise ValueError("downsample must be 'box' or 'nearest'")

    rgba = image._image.convert("RGBA")
    resampling = (
        _RESAMPLING.BOX
        if downsample == "box"
        else _RESAMPLING.NEAREST
    )
    rgba = rgba.resize((width, height), resampling)

    pixels = list(rgba.getdata())
    cleaned = [
        (r, g, b, 255) if a >= alpha_threshold else (0, 0, 0, 0)
        for r, g, b, a in pixels
    ]
    rgba.putdata(cleaned)

    alpha = rgba.getchannel("A")
    quantized = rgba.convert("RGB").quantize(
        colors=colors,
        method=_QUANTIZE.MAXCOVERAGE,
        dither=_DITHER.NONE,
    ).convert("RGBA")
    quantized.putalpha(alpha)

    if preview_scale > 1:
        quantized = quantized.resize(
            (
                quantized.width * preview_scale,
                quantized.height * preview_scale,
            ),
            _RESAMPLING.NEAREST,
        )
    return SSUIImage(quantized)
