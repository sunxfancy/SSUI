"""Make verified wheel-bundled command-line tools visible to SSUI children."""
import importlib.metadata
import os
from pathlib import Path
import platform
import sys


def configure_native_tools():
    if sys.platform != 'win32' or platform.machine().lower() not in ('arm64', 'aarch64'):
        return None
    # Preserve an explicit user override rather than replacing it at startup.
    if os.environ.get('IMAGEIO_FFMPEG_EXE'):
        return Path(os.environ['IMAGEIO_FFMPEG_EXE'])
    try:
        wheel = importlib.metadata.distribution('imageio-ffmpeg')
    except importlib.metadata.PackageNotFoundError:
        return None
    binary = Path(wheel.locate_file('imageio_ffmpeg/binaries/ffmpeg.exe'))
    if not binary.is_file():
        return None
    os.environ['IMAGEIO_FFMPEG_EXE'] = str(binary)
    paths = os.environ.get('PATH', '').split(os.pathsep)
    if str(binary.parent) not in paths:
        os.environ['PATH'] = os.pathsep.join([str(binary.parent), *paths])
    return binary
