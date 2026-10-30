"""Exercise built wheels in a fresh venv while the build venv's Torch is hidden."""
from pathlib import Path
import os
import subprocess
import sys
import sysconfig


def main():
    root = Path.cwd()
    python = root / '.build' / 'wheel-consumer' / 'bin' / 'python'
    subprocess.run([sys.executable, '-m', 'venv', str(python.parents[1])], check=True)
    wheels = sorted(str(p) for p in (root / 'native-wheels').glob('*.whl'))
    subprocess.run([str(python), '-m', 'pip', 'install', 'numpy==1.26.4', *wheels], check=True)
    original = Path(sysconfig.get_paths()['platlib']) / 'torch'
    hidden = original.with_name('torch-build-hidden')
    if original.exists():
        original.rename(hidden)
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'PYTHONPATH'))}
        subprocess.run([str(python), '-c', '''
import torch, torchvision, torchaudio
assert torch.arange(4).sum().item() == 6
assert torchvision.ops.nms(torch.tensor([[0.,0.,1.,1.]]),torch.tensor([.9]),.5).tolist() == [0]
assert torchaudio.functional.resample(torch.zeros(1,160),16000,8000).shape == (1,80)
x = torch.zeros((3,8,8), dtype=torch.uint8)
assert torch.equal(torchvision.io.decode_png(torchvision.io.encode_png(x)), x)
assert torch.distributed.is_available()
print('Native CPU wheels work without the build environment')
'''], cwd=python.parent, env=env, check=True)
    finally:
        if hidden.exists():
            hidden.rename(original)


if __name__ == '__main__':
    main()
