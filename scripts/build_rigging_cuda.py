"""Compile and execute native CUDA operators with the host's ARM64 MSVC tools."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

ROOT = Path(__file__).resolve().parents[1]


def freetype(python, env, reuse=False):
    """FreeType is a CPU font utility imported by pyrender, not a CUDA operator."""
    cached = ROOT / ".build/rigging-cuda/freetype/libfreetype.dll"
    if not reuse or not cached.is_file():
        source = ROOT / ".build/rgsrc/ft"
        if not source.exists():
            subprocess.run(["git", "clone", "--depth=1", "--branch", "VER-2-13-3",
                            "https://github.com/freetype/freetype.git", str(source)], check=True)
        build = source / "build-native"
        subprocess.run(["cmake", "-S", str(source), "-B", str(build), "-G", "Ninja",
                        "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=ON",
                        "-DFT_DISABLE_ZLIB=TRUE", "-DFT_DISABLE_BZIP2=TRUE", "-DFT_DISABLE_PNG=TRUE",
                        "-DFT_DISABLE_HARFBUZZ=TRUE", "-DFT_DISABLE_BROTLI=TRUE"], env=env, check=True)
        subprocess.run(["cmake", "--build", str(build), "--parallel", "4"], env=env, check=True)
        library = next(build.rglob("freetype.dll"))
        cached.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(library, cached)
        shutil.copyfile(source / "docs/FTL.TXT", cached.parent / "FTL.TXT")
    site = Path(subprocess.check_output([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], text=True).strip())
    destination = site / "freetype"
    if not destination.is_dir():
        raise RuntimeError("Install freetype-py in the target environment first")
    shutil.copyfile(cached, destination / "libfreetype.dll")
    shutil.copyfile(cached.parent / "FTL.TXT", destination / "FreeType_LICENSE.txt")
    subprocess.run([str(python), "-c", "import freetype; print('FreeType native library:', freetype.version())"], check=True)


def build_environment():
    env = os.environ.copy()
    if os.name == "nt":
        candidates = list(Path("C:/Program Files/Microsoft Visual Studio").glob("*/*/VC/Auxiliary/Build/vcvarsarm64.bat"))
        if not candidates:
            raise RuntimeError("Install Visual Studio C++ ARM64 build tools")
        output = subprocess.check_output(f'call "{candidates[-1]}" >nul && set', shell=True, text=True, errors="replace")
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if separator and key:
                env[key] = value
        env["DISTUTILS_USE_SDK"] = "1"
        env["MSSdk"] = "1"
    env["CUDA_HOME"] = env.get("CUDA_PATH", "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v13.4")
    env.setdefault("TORCH_CUDA_ARCH_LIST", "12.1")
    env.setdefault("MAX_JOBS", "2")
    env["FORCE_CUDA"] = "1"
    env["FLASH_ATTENTION_FORCE_BUILD"] = "TRUE"
    env.setdefault("FLASH_ATTN_CUDA_ARCHS", "121")
    env.setdefault("CUMM_CUDA_ARCH_LIST", "12.1")
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["VSLANG"] = "1033"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    if os.name == "nt":
        env["CL"] = env.get("CL", "") + " /std:c++20 /Zc:__cplusplus /Zc:preprocessor /utf-8"
        env["NVCC_APPEND_FLAGS"] = env.get("NVCC_APPEND_FLAGS", "") + " -std=c++20 -Xcompiler=/Zc:preprocessor --device-entity-has-hidden-visibility=false -static-global-template-stub=false"
    env["SSUI_RIGGING_CUDA_BUILD"] = "1"
    hooks = ROOT / "extensions/3D-Model/build_hooks"
    env["PYTHONPATH"] = str(hooks) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def worker():
    import torch
    from torch.utils.cpp_extension import load_inline
    target = ROOT / ".build/rigging-cuda/probe"
    target.mkdir(parents=True, exist_ok=True)
    module = load_inline(
        name="ssui_rigging_cuda_probe", build_directory=str(target),
        cpp_sources="torch::Tensor add_one_cuda(torch::Tensor x);",
        cuda_sources=r'''
#include <torch/extension.h>
#include <cuda_runtime.h>
__global__ void add_one_kernel(float* p, int64_t n) {
    int64_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) p[i] += 1.0f;
}
torch::Tensor add_one_cuda(torch::Tensor x) {
    TORCH_CHECK(x.is_cuda() && x.scalar_type() == torch::kFloat32 && x.is_contiguous());
    auto y = x.clone();
    add_one_kernel<<<(y.numel()+255)/256,256>>>(y.data_ptr<float>(),y.numel());
    TORCH_CHECK(cudaDeviceSynchronize() == cudaSuccess);
    return y;
}
''', functions=["add_one_cuda"], with_cuda=True, verbose=True,
    )
    x = torch.arange(1024, device="cuda", dtype=torch.float32)
    torch.testing.assert_close(module.add_one_cuda(x), x + 1)
    report = dict(torch=torch.__version__, cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(),
                  capability=torch.cuda.get_device_capability(), compiled_kernel="passed")
    (target.parent / "probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/rigging/riganything/Scripts/python.exe")
    parser.add_argument("--package", choices=("probe", "torch-scatter", "torch-cluster", "pytorch3d", "cumm", "spconv", "flash-attn", "freetype"), default="probe")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--reuse", action="store_true", help="Install a previously compiled local wheel")
    args = parser.parse_args()
    if args.reuse and args.package == "probe":
        parser.error("--reuse requires --package with a native library name")
    if args.worker:
        worker()
        return
    if args.package == "freetype":
        freetype(args.python, build_environment(), args.reuse)
        return
    wheels = ROOT / ".build/rigging-cuda/wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    if args.reuse:
        # pip built wheels are architecture-tagged; retain a project-local copy.
        cache_python = ROOT / ".venv/rigging/riganything/Scripts/python.exe"
        if not cache_python.is_file():
            cache_python = args.python.resolve()
        cached = subprocess.check_output([str(cache_python), "-m", "pip", "cache", "list", "--format=abspath"], text=True)
        for line in cached.splitlines():
            path = Path(line.strip())
            if path.is_file() and path.name.startswith(("torch_cluster-", "torch_scatter-", "pytorch3d-", "cumm-", "spconv-", "flash_attn-")):
                shutil.copyfile(path, wheels / path.name)
        subprocess.run([str(args.python), "-m", "pip", "install", "--force-reinstall", "--no-index", "--no-deps", "--find-links", str(wheels), args.package], check=True)
        return
    env = build_environment()
    if args.package == "probe":
        command = [str(args.python), str(Path(__file__).resolve()), "--worker"]
    else:
        packages = {"torch-scatter": "torch-scatter==2.1.2", "torch-cluster": "torch-cluster==1.6.3",
                    "pytorch3d": "git+https://github.com/facebookresearch/pytorch3d.git@v0.7.9",
                    "cumm": "cumm", "spconv": "spconv", "flash-attn": "flash-attn"}
        sources = {
            "pytorch3d": ("https://github.com/facebookresearch/pytorch3d.git", "v0.7.9", "p3"),
            "cumm": ("https://github.com/FindDefinition/cumm.git", "v0.7.11", "cu"),
            "spconv": ("https://github.com/traveller59/spconv.git", "v2.3.8", "sc"),
            "flash-attn": ("https://github.com/Dao-AILab/flash-attention.git", "v2.8.3", "fa"),
        }
        package = packages[args.package]
        if args.package in sources:
            url, revision, directory = sources[args.package]
            source = ROOT / ".build/rgsrc" / directory
            source.parent.mkdir(parents=True, exist_ok=True)
            if not source.exists():
                subprocess.run(["git", "-c", "core.longpaths=true", "clone", "--depth=1", "--branch", revision, url, str(source)], check=True)
            if args.package == "flash-attn":
                subprocess.run(["git", "-c", "core.longpaths=true", "submodule", "update", "--init", "--depth=1", "csrc/cutlass"], cwd=source, check=True)
                setup = source / "setup.py"
                content = setup.read_text(encoding="utf-8")
                # CK is AMD-only and its paths exceed MAX_PATH. Cutlass is the
                # only submodule needed by this explicitly CUDA-only build.
                content = content.replace('subprocess.run(["git", "submodule", "update", "--init", "csrc/composable_kernel"], check=True)', "pass  # SSUI: CUDA build does not use composable_kernel")
                setup.write_text(content, encoding="utf-8")
                env["FLASH_ATTN_CUDA_ARCHS"] = "120"
            if args.package == "cumm":
                env["CUMM_DISABLE_JIT"] = "1"
                setup = source / "setup.py"
                setup.write_text(setup.read_text(encoding="utf-8").replace(
                    "sys.path.append(str(Path(__file__).parent))", "sys.path.insert(0, str(Path(__file__).parent))"), encoding="utf-8")
                common = source / "cumm/common.py"
                content = common.read_text(encoding="utf-8")
                if "supported_arches += ['12.0', '12.1']" not in content:
                    content = content.replace("valid_arch_strings =", "supported_arches += ['12.0', '12.1']\n    valid_arch_strings =")
                content = content.replace(r"\\lib\\x64", r"\\lib\\arm64")
                common.write_text(content, encoding="utf-8")
            if args.package == "spconv":
                env["SPCONV_DISABLE_JIT"] = "1"
                setup = source / "setup.py"
                setup.write_text(setup.read_text(encoding="utf-8").replace(
                    "sys.path.append(str(Path(__file__).parent))", "sys.path.insert(0, str(Path(__file__).parent))"), encoding="utf-8")
                operations = source / "spconv/csrc/sparse/all.py"
                content = operations.read_text(encoding="utf-8")
                if 'self.add_include("thrust/tuple.h")' not in content:
                    content = content.replace("self.add_dependency(ThrustLib)", 'self.add_dependency(ThrustLib)\n        self.add_include("thrust/tuple.h")')
                operations.write_text(content, encoding="utf-8")
            package = str(source)
        command = [str(args.python), "-m", "pip", "wheel", "--wheel-dir", str(wheels), "--no-build-isolation", "--no-deps", "--no-binary=:all:", "-v", package]
    subprocess.run(command, env=env, check=True)
    if args.package != "probe":
        subprocess.run([str(args.python), "-m", "pip", "install", "--force-reinstall", "--no-index", "--no-deps", "--find-links", str(wheels), args.package], check=True)


if __name__ == "__main__":
    main()
