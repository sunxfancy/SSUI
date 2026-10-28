"""Prepare the pinned CuMesh ROCm port with bounded tensor row copies."""
import argparse
from pathlib import Path
import subprocess
from prepare_nvdiffrast_rocm import checkout, extract_headers

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=Path('.build/cumesh-rocm'))
args = parser.parse_args()
root = args.directory.resolve()
root.mkdir(parents=True, exist_ok=True)
source = root / 'source'
checkout('https://github.com/sunxfancy/CuMesh.rocm72.git',
         'bb2ed49f4170a267ecb90c41b48daab1ddce7830', source)
checkout('https://gitlab.com/libeigen/eigen.git',
         '3147391d946bb4b6c68edd901f2add6ac1f31f8c',
         source / 'third_party/cubvh/third_party/eigen')
subprocess.run(['git', 'apply', str(Path(__file__).resolve().parent / 'patches/cumesh-rocm.patch')],
               cwd=source, check=True)
extract_headers(root / 'headers')
print(f'Prepared {source}')
