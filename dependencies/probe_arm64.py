"""Native ARM64 probes; optional pinned MediaPipe assets, no GPU validation."""
import argparse
from datetime import datetime, timezone
import importlib.metadata as metadata
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen

CHECKS = {
    'torch-cpu': "import torch; x=torch.arange(4,dtype=torch.float32).reshape(2,2); assert torch.equal(x@torch.eye(2),x)",
    'torchvision-cpu': "import torch; from torchvision.ops import nms; assert nms(torch.tensor([[0.,0.,1.,1.]]),torch.tensor([.9]),.5).tolist()==[0]",
    'torchaudio-resample': "import torch,torchaudio; y=torchaudio.functional.resample(torch.zeros(1,160),16000,8000); assert y.shape==(1,80)",
    'numba-native-jit': "import numba,numpy as np; import llvmlite.binding as llvm; f=numba.njit(lambda a:(a*a).sum()); assert f(np.arange(10))==285; assert f.nopython_signatures; assert llvm.get_default_triple().startswith('aarch64'); print(llvm.get_default_triple())",
    'opencv-image': "import cv2,numpy as np; assert cv2.cvtColor(np.zeros((2,2,3),dtype=np.uint8),cv2.COLOR_BGR2GRAY).shape==(2,2)",
    'onnxruntime-cpu': "import numpy as np,onnx,onnxruntime as ort; from onnx import helper as h,TensorProto as T; g=h.make_graph([h.make_node('Relu',['x'],['y'])],'probe',[h.make_tensor_value_info('x',T.FLOAT,[4])],[h.make_tensor_value_info('y',T.FLOAT,[4])]); m=h.make_model(g,opset_imports=[h.make_opsetid('',13)]); m.ir_version=8; s=ort.InferenceSession(m.SerializeToString(),providers=['CPUExecutionProvider']); x=np.array([-1,2,-3,4],dtype=np.float32); np.testing.assert_array_equal(s.run(None,{'x':x})[0],np.maximum(x,0))",
    'arrow-snappy': "import pyarrow as pa,pyarrow.parquet as pq; t=pa.table({'a':[1,2,3]}); out=pa.BufferOutputStream(); pq.write_table(t,out,compression='snappy'); assert pq.read_table(pa.BufferReader(out.getvalue())).equals(t)",
    'mesh-repair': "import pyvista as pv,pymeshfix; m=pv.Sphere(theta_resolution=12,phi_resolution=12); f=pymeshfix.MeshFix(m); f.repair(verbose=False); assert f.mesh.n_points>0 and f.mesh.n_cells>0",
    'pynini-wetext': "import pynini; import tn.chinese.normalizer; assert pynini.shortestpath(pynini.cross('a','b')).string()=='b'",
    'hydra-antlr': "from hydra.core.override_parser.overrides_parser import OverridesParser; assert OverridesParser.create().parse_override('a=1').value()==1",
    'librosa-soxr': "import librosa,numpy as np; x=np.zeros(2048,dtype=np.float32); assert librosa.resample(x,orig_sr=16000,target_sr=8000).shape==(1024,); assert librosa.feature.melspectrogram(y=x,sr=16000,n_fft=512,hop_length=128,n_mels=16).shape[0]==16",
    'soundfile-wav': "import io,soundfile as sf,numpy as np; b=io.BytesIO(); sf.write(b,np.zeros(160),16000,format='WAV'); b.seek(0); x,sr=sf.read(b); assert len(x)==160 and sr==16000",
    'whisper-mel': "import torch,whisper; assert whisper.log_mel_spectrogram(torch.zeros(16000)).shape==(80,100)",
    'rembg-import': "import rembg,pymatting; assert callable(rembg.remove)",
    'controlnet-aux-import': "import numpy as np; from controlnet_aux import CannyDetector; x=np.zeros((128,128,3),dtype=np.uint8); x[32:96,32:96]=255; assert CannyDetector()(x,output_type='np').any()",
    'stream-generator-import': "import transformers_stream_generator.main",
    'stream-generator-model': "import runpy; runpy.run_path('dependencies/check_stream_compat.py',run_name='__main__')",
    'ffmpeg-ssui': "import runpy; runpy.run_path('dependencies/check_ffmpeg_compat.py',run_name='__main__')",
    'mediapipe-ssui': "import runpy; runpy.run_path('dependencies/check_mediapipe_compat.py',run_name='__main__')",
    'moderngl-native': "import moderngl,glcontext; assert callable(glcontext.default_backend())",
    'pyworld-pitch': "import pyworld,numpy as np; f,t=pyworld.dio(np.zeros(1600,dtype=np.float64),16000); assert len(f)==len(t)>0",
    'soxr-audio': "import soxr,numpy as np; assert len(soxr.resample(np.zeros(160,dtype=np.float32),16000,8000))==80",
    'hf-transfer-native': "import hf_transfer; assert callable(hf_transfer.download)",
    'tiktoken-offline': "import tiktoken; e=tiktoken.Encoding(name='ssui-probe',pat_str='.',mergeable_ranks={bytes([i]):i for i in range(256)},special_tokens={}); assert e.decode(e.encode('hello'))=='hello'",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--check', action='append', choices=CHECKS)
    parser.add_argument('--timeout', type=int, default=300, help='Seconds per check, including cold JIT compilation')
    parser.add_argument('--assets-root', help='Directory containing pinned MediaPipe models and official test images')
    parser.add_argument('--download-assets', action='store_true', help='Fetch and hash-check the pinned MediaPipe test assets')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() != 'arm64':
        raise SystemExit('Run probes with native Windows ARM64 Python')
    results = []
    if args.assets_root:
        os.environ['SSUI_ARM64_PROBE_ASSETS'] = str(Path(args.assets_root).resolve())
    if args.download_assets:
        if not args.assets_root:
            parser.error('--download-assets requires --assets-root')
        root = Path(args.assets_root)
        root.mkdir(parents=True, exist_ok=True)
        pins = json.loads(Path(__file__).with_name('arm64-probe-assets.json').read_text())
        for name, pin in pins.items():
            if Path(name).name != name:
                raise ValueError('Unsafe probe asset filename')
            dest = root / name
            if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == pin['sha256']:
                continue
            with tempfile.NamedTemporaryFile(dir=root, delete=False, suffix='.download') as file:
                temporary = Path(file.name)
            try:
                with urlopen(pin['url'], timeout=60) as source, temporary.open('wb') as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != pin['sha256']:
                    raise ValueError('Probe asset SHA256 mismatch: ' + name)
                os.replace(temporary, dest)
            finally:
                temporary.unlink(missing_ok=True)
    selected = args.check or [name for name in CHECKS if args.assets_root or name != 'mediapipe-ssui']
    if 'mediapipe-ssui' in selected and not args.assets_root:
        parser.error('mediapipe-ssui requires --assets-root with pinned model/test assets')
    for name in selected:
        try:
            proc = subprocess.run([sys.executable, '-c', CHECKS[name]], capture_output=True,
                                  text=True, encoding='utf-8', errors='replace', timeout=args.timeout)
            def clean(text):
                return text.replace(str(Path.cwd()), '$WORKSPACE').replace(str(Path.home()), '$USER_HOME')
            result = {'check': name, 'status': 'passed' if proc.returncode == 0 else 'failed',
                      'exitCode': proc.returncode, 'stdout': clean(proc.stdout[-3000:]), 'stderr': clean(proc.stderr[-4000:])}
        except subprocess.TimeoutExpired:
            result = {'check': name, 'status': 'failed', 'error': f'{args.timeout} second timeout'}
        results.append(result)
        print(name + ': ' + result['status'], flush=True)
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'arch': platform.machine(),
              'python': platform.python_version(), 'scope': 'Native CPU dependency operations and tiny-model generation; optional supplied MediaPipe fixtures; no GPU or rendering tests',
              'versions': dict(sorted((d.metadata['Name'], d.version) for d in metadata.distributions())),
              'checks': results}
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return int(any(item['status'] != 'passed' for item in results))


if __name__ == '__main__':
    raise SystemExit(main())
