"""Load torchtune inference modules without its eager training imports.

HeartMuLa uses torchtune's Llama builder. The upstream package initializer also
loads datasets and training modules, which are unrelated to this inference path.
"""

import os
from pathlib import Path

__version__ = "0.4.0+cpu"

_site = os.environ.get("SSUI_HEARTMULA_DEPS")
if not _site:
    raise RuntimeError("SSUI_HEARTMULA_DEPS must point to the isolated torchtune site")
__path__ = [str(Path(_site).resolve() / "torchtune")]
