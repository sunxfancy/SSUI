"""Exercise built wheels in a fresh venv while the build venv's Torch is hidden."""
from pathlib import Path
import os
import re
import subprocess
import sys
import sysconfig


def main():
    root = Path.cwd()
    python = root / '.build' / 'wheel-consumer' / 'bin' / 'python'
    subprocess.run([sys.executable, '-m', 'venv', str(python.parents[1])], check=True)
    wheels = sorted(str(p) for p in (root / 'native-wheels').glob('*.whl'))
    subprocess.run([str(python), '-m', 'pip', 'install', 'numpy==1.26.4', 'soundfile==0.14.0', *wheels], check=True)
    site = Path(subprocess.check_output([str(python), '-c',
        "import sysconfig; print(sysconfig.get_paths()['platlib'])"], text=True).strip())
    for package in ('torch', 'torchvision', 'torchaudio'):
        for library in (site / package).rglob('*'):
            if library.suffix not in ('.so', '.dylib'):
                continue
            links = subprocess.check_output(['otool', '-L', str(library)], text=True)
            paths = [line.strip().split(' (', 1)[0] for line in links.splitlines()[1:]]
            commands = subprocess.check_output(['otool', '-l', str(library)], text=True)
            paths += re.findall(r'cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset', commands)
            for dependency in paths:
                if dependency.startswith('/') and not dependency.startswith(('/usr/lib/', '/System/Library/')):
                    raise RuntimeError(f'Non-portable dynamic library reference: {library}: {dependency}')
    original = Path(sysconfig.get_paths()['platlib']) / 'torch'
    hidden = original.with_name('torch-build-hidden')
    if original.exists():
        original.rename(hidden)
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'PYTHONPATH'))}
        subprocess.run([str(python), '-c', '''
import torch, torchvision, torchaudio, tempfile
from pathlib import Path
assert torch.arange(4).sum().item() == 6
assert torchvision.ops.nms(torch.tensor([[0.,0.,1.,1.]]),torch.tensor([.9]),.5).tolist() == [0]
assert torchaudio.functional.resample(torch.zeros(1,160),16000,8000).shape == (1,80)
x = torch.zeros((3,8,8), dtype=torch.uint8)
assert torch.equal(torchvision.io.decode_png(torchvision.io.encode_png(x)), x)
with tempfile.TemporaryDirectory() as directory:
    wav = str(Path(directory) / 'native.wav')
    torchaudio.save(wav, torch.zeros(1,160), 16000)
    samples, rate = torchaudio.load(wav)
    assert samples.shape == (1,160) and rate == 16000
assert torch.distributed.is_available()
print('Native CPU wheels work without the build environment')
'''], cwd=python.parent, env=env, check=True)
    finally:
        if hidden.exists():
            hidden.rename(original)


if __name__ == '__main__':
    main()
