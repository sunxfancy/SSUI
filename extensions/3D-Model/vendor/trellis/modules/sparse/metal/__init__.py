"""Lazy local build for PyTorch versions predating torch.mps.compile_shader."""
from functools import lru_cache
import hashlib
from pathlib import Path
import platform
import tempfile
import torch


@lru_cache(None)
def extension():
    from torch.utils.cpp_extension import load
    source = Path(__file__).with_name('neighbors.mm')
    signature = source.read_bytes() + f'{torch.__version__}-{platform.python_version()}-{platform.machine()}'.encode()
    key = hashlib.sha256(signature).hexdigest()[:16]
    build = Path(tempfile.gettempdir()) / 'ssui-trellis-metal' / key
    build.mkdir(parents=True, exist_ok=True)
    return load(name=f'trellis_metal_{key}', sources=[str(source)], build_directory=str(build),
                extra_cflags=['-O2', '-std=c++17'],
                extra_ldflags=['-framework', 'Foundation', '-framework', 'Metal', '-framework', 'MetalPerformanceShaders'],
                verbose=False)
