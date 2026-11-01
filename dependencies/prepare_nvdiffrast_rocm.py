"""Prepare pinned upstream sources for the SSUI Windows ROCm wheel build.

The Linux RDNA4 kernel patches are applied separately from the Windows build
adaptations, following sunxfancy/CuMesh.rocm72's HIP binding compilation.
Only a fresh source checkout is accepted; existing work is never reset.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

UPSTREAM = "253ac4fcea7de5f396371124af597e6cc957bfae"
PATCHES = "7ad5076e27bf2722f8f19c9f6a2bb42021f00b70"


def checkout(url, revision, path):
    if path.exists():
        raise RuntimeError(f"Use a new build directory; refusing to overwrite {path}")
    subprocess.run(["git", "clone", url, str(path)], check=True)
    subprocess.run(["git", "checkout", "--detach", revision], cwd=path, check=True)


def python_blocks(path):
    return re.findall(r"<<'(PY(?:EOF)?)'\n(.*?)\n\1", path.read_text(encoding="utf-8"), re.S)


def extract_headers(destination):
    import rocm_sdk_devel

    archive = next(Path(rocm_sdk_devel.__file__).parent.glob("_devel.tar*"))
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        prefix = "_rocm_sdk_devel/include/"
        for member in tar.getmembers():
            if member.name.startswith(prefix) and member.isfile():
                output = (destination / member.name[len(prefix):]).resolve()
                output.relative_to(destination)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(tar.extractfile(member).read())


def prepare(source, patches):
    shutil.copytree(source / "csrc/common/cudaraster", source / "csrc/common/hipraster")
    os.chdir(source)
    os.environ["MODE"] = "runtime"
    generator = patches / "scripts/nvdiffrast_rocm72_bundle_v52_generator.sh"
    # Execute only the pinned source-rewriting Python block, not shell cleanup,
    # package uninstall, installation or diagnostic code in the Linux script.
    for _, code in python_blocks(generator):
        if "impl = Path(" in code:
            exec(compile(code, str(generator), "exec"), {})
    for name in (
        "patch_rocm_v36_wave32.sh",
        "patch_antialias_grad_rocm_wave32_v38.sh",
        "patch_antialias_grad_rocm_wave32_v38b_gradpos_guard.sh",
        "patch_antialias_persistent_loop_v39b.sh",
        "patch_active_hip_antialias_fwd_bounds_v40f_patch_cu_and_hip.sh",
        "patch_clang_antialias_evhash_narrowing_v41c.sh",
        "patch_rocm_interpolate_emptywarp_allsync_fix_v41m2.sh",
    ):
        sys.argv = ["patch", str(source) if "v41" in name else "csrc/common/antialias.cu"]
        for _, code in python_blocks(patches / "patches" / name):
            exec(compile(code, name, "exec"), {})

    path = Path("csrc/common/framework.h")
    path.write_text(path.read_text().replace(
        "#ifndef __CUDACC__", "#if !defined(__CUDACC__) || defined(NVDR_HOST_BINDING)"))
    path = Path("csrc/common/hipraster/impl/Defs.hpp")
    path.write_text(path.read_text().replace("<cuda_runtime.h>", "<hip/hip_runtime.h>"))
    path = Path("csrc/common/hipraster/impl/Util.inl")
    path.write_text(path.read_text().replace('"PrivateDefs.hpp"', '"PrivateDefs_hip.hpp"'))
    path = Path("csrc/torch/torch_common.inl")
    path.write_text(path.read_text().replace("framework.h", "framework_hip.h"))

    path = Path("setup.py")
    text = path.read_text().replace('"csrc/common/cudaraster/', '"csrc/common/hipraster/')
    for filename in re.findall(r'"(csrc/[^\"]+\.cpp)"', text):
        new_name = filename[:-4] + "_win.cu"
        Path(new_name).write_text("#define NVDR_HOST_BINDING 1\n" + Path(filename).read_text())
        text = text.replace('"' + filename + '"', '"' + new_name + '"')
    text = text.replace('"nvcc": ["-DNVDR_TORCH", "-lineinfo"]',
        '"nvcc": ["-DNVDR_TORCH", "-O2", "-std=c++17", '
        '"--offload-arch=" + os.environ.get("GPU_ARCHS", "gfx1201"), '
        '"--rocm-device-lib-path=" + os.path.join(os.environ["ROCM_PATH"], "lib/llvm/amdgcn/bitcode")]')
    text = text.replace("extra_compile_args={", 'include_dirs=[os.environ["ROCM_DEVEL_INCLUDE"]],\n            extra_compile_args={')
    path.write_text(text)
    path = Path("pyproject.toml")
    path.write_text(path.read_text().replace('version = "0.4.0"', 'version = "0.4.0+ssui.rocm72"'))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(".build/nvdiffrast-repro"))
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source, patches = root / "source", root / "patches"
    checkout("https://github.com/NVlabs/nvdiffrast.git", UPSTREAM, source)
    checkout("https://github.com/Painter3000/amd-nvdiffrast-rocm72-gfx1201.git", PATCHES, patches)
    extract_headers(root / "headers")
    prepare(source, patches)
    print(f"Prepared {source}")
