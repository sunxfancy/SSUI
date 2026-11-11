"""Prepare NATTEN 0.17.4's non-CUTLASS kernels for Windows ROCm/gfx1201."""
import argparse
from pathlib import Path
import subprocess
from prepare_nvdiffrast_rocm import checkout, extract_headers

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--directory", type=Path, default=Path(".build/natten-rocm"))
args = parser.parse_args()
root = args.directory.resolve()
source = root / "source"
root.mkdir(parents=True, exist_ok=True)
checkout("https://github.com/SHI-Labs/NATTEN.git",
         "c198e1517d9b8ffc3fc4cc7f14c371df6d30bd64", source)
subprocess.run(["git", "apply", str(Path(__file__).resolve().parent / "patches/natten-rocm.patch")],
               cwd=source, check=True)
extract_headers(root / "headers")
sources = [source / "csrc/natten.cpp"]
for pattern in ("csrc/src/*.cpp", "csrc/src/pytorch/*.cpp", "csrc/src/pytorch/cpu/*.cpp",
                "csrc/src/pytorch/cuda/*.cu", "csrc/autogen/src/cpu/naive/*.cpp",
                "csrc/autogen/src/cuda/naive/*.cu"):
    sources.extend(sorted(source.glob(pattern)))
converted = []
for path in sources:
    if path.suffix == ".cpp":
        target = path.with_name(path.stem + "_win.cu")
        target.write_text(path.read_text())
        path = target
    converted.append(path.relative_to(source).as_posix())
(source / "setup.py").write_text('''import os
from setuptools import setup, find_packages
from torch.utils.cpp_extension import BuildExtension, CUDAExtension
setup(
    name="natten", version="0.17.4+ssui.rocm72",
    packages=find_packages("src"), package_dir={"": "src"},
    ext_modules=[CUDAExtension(
        "natten.libnatten", sources=''' + repr(converted) + ''',
        include_dirs=[os.path.abspath("csrc/include"), os.path.abspath("csrc/autogen/include"),
                      os.environ["ROCM_DEVEL_INCLUDE"]],
        extra_compile_args={"nvcc": ["-O2", "-std=c++17", "-DSSUI_HIP_BUILD=1",
            "-DNATTEN_WITH_CUDA", "-DWITH_CUDA", "--offload-arch=gfx1201",
            "--rocm-device-lib-path=" + os.path.join(os.environ["ROCM_PATH"], "lib/llvm/amdgcn/bitcode")]},
    )], cmdclass={"build_ext": BuildExtension},
)
''')
print(f"Prepared {source}")
