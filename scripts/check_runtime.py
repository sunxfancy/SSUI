"""Native CI smoke test: the interpreter and core inference stack must actually run."""
import argparse
import json
import platform
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--target', required=True)
    a = p.parse_args()
    config = json.loads((Path(__file__).resolve().parents[1] / 'dependencies/runtime.json').read_text())
    target = config['targets'][a.target]
    expected = target['pythonTarget'].split('-')[0]
    actual = {'AMD64': 'x86_64', 'arm64': 'aarch64', 'ARM64': 'aarch64'}.get(platform.machine(), platform.machine())
    if actual != expected or platform.python_version() != config['pythonVersion']:
        raise RuntimeError(f'expected Python {config["pythonVersion"]}/{expected}, got {platform.python_version()}/{actual}')
    import torch
    import torchvision
    import fastapi
    import diffusers
    import transformers
    # Both the Torch tensor kernels and torchvision native extension must load.
    assert torch.tensor([1.0, 2.0]).sum().item() == 3
    boxes = torch.tensor([[0., 0., 1., 1.], [0., 0., 1., 1.]])
    assert torchvision.ops.nms(boxes, torch.tensor([0.9, 0.8]), 0.5).tolist() == [0]
    print(f'OK {a.target}: Python {platform.python_version()}, torch {torch.__version__}, torchvision {torchvision.__version__}')


if __name__ == '__main__':
    main()
