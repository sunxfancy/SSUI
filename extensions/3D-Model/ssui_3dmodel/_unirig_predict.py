"""Run UniRig with legacy Box checkpoint metadata decoded as ordered mappings."""
from collections import OrderedDict
from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    import torch
    # The official skin checkpoint's Box is configuration metadata, not model
    # state. Decode it as an ordinary mapping while retaining weights_only.
    # Recent PyTorch refuses SETITEMS on Box even when Box is allowlisted.
    torch.serialization.add_safe_globals([(OrderedDict, "box.box.Box")])
    sys.path.insert(0, str(Path.cwd()))
    sys.argv[0] = str(Path.cwd() / "run.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
