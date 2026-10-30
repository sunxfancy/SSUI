"""Exercise native audio and 3D extensions; import-only tests miss DLL/ABI errors."""
import tempfile
from pathlib import Path
import torch
import torchaudio
import numpy as np
import pyvista as pv
import pymeshfix
import moderngl
import tiktoken

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'native.wav'
    waveform = torch.sin(torch.arange(1600, dtype=torch.float32)[None, :] / 20)
    torchaudio.save(str(path), waveform, 16000, backend='soundfile')
    restored, rate = torchaudio.load(str(path), backend='soundfile')
    assert rate == 16000 and restored.shape == waveform.shape
    assert torchaudio.functional.resample(restored, 16000, 8000).shape[-1] == 800
# Exercise VTK C++ and PyMeshFix, without requiring a GPU/display server.
mesh = pv.Sphere(theta_resolution=12, phi_resolution=12).triangulate()
fixed = pymeshfix.MeshFix(mesh.points, mesh.faces.reshape(-1, 4)[:, 1:])
fixed.repair()
assert fixed.v.shape[0] > 0 and np.isfinite(fixed.v).all()
# Importing moderngl loads its native extension; rendering also depends on the host GPU driver.
assert moderngl.__version__
from tiktoken._tiktoken import CoreBPE
assert CoreBPE
print('Native audio round-trip, resampling, VTK geometry, mesh repair and native extension imports passed.')
