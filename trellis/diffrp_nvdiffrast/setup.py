# Copyright (c) 2020, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import nvdiffrast
import setuptools
import os
import torch
from torch.utils.cpp_extension import CUDAExtension, BuildExtension

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="diffrp-nvdiffrast",
    version=nvdiffrast.__version__,
    author="Samuli Laine",
    author_email="slaine@nvidia.com",
    description="nvdiffrast - modular primitives for high-performance differentiable rendering",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NVlabs/nvdiffrast",
    packages=setuptools.find_packages(),
    package_data={
        "nvdiffrast": [
            "common/*.h",
            "common/*.inl",
            "common/*.cu",
            "common/*.cpp",
            "common/cudaraster/*.hpp",
            "common/cudaraster/impl/*.cpp",
            "common/cudaraster/impl/*.hpp",
            "common/cudaraster/impl/*.inl",
            "common/cudaraster/impl/*.cu",
            "lib/*.h",
            "torch/*.h",
            "torch/*.inl",
            "torch/*.cpp",
            "tensorflow/*.cu",
            "*.pyd",
            "*.cp312-win_amd64.pyd"
        ]
        + (["lib/*.lib"] if os.name == "nt" else [])
    },
    include_package_data=True,
    install_requires=[
        "numpy"
    ],  # note: can't require torch here as it will install torch even for a TensorFlow container
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    ext_modules=[
        CUDAExtension(
            name="nvdiffrast.nvdiffrast_plugin",
            sources=[
                "./nvdiffrast/common/cudaraster/impl/Buffer.cpp",
                "./nvdiffrast/common/cudaraster/impl/CudaRaster.cpp",
                "./nvdiffrast/common/cudaraster/impl/RasterImpl_cuda.cu",
                "./nvdiffrast/common/cudaraster/impl/RasterImpl.cpp",
                "./nvdiffrast/common/common.cpp",
                "./nvdiffrast/common/rasterize.cu",
                "./nvdiffrast/common/interpolate.cu",
                "./nvdiffrast/common/texture_cuda.cu",
                "./nvdiffrast/common/texture.cpp",
                "./nvdiffrast/common/antialias.cu",
                "./nvdiffrast/torch/torch_bindings.cpp",
                "./nvdiffrast/torch/torch_rasterize.cpp",
                "./nvdiffrast/torch/torch_interpolate.cpp",
                "./nvdiffrast/torch/torch_texture.cpp",
                "./nvdiffrast/torch/torch_antialias.cpp",
            ],
            extra_compile_args={
                "cxx": (
                    ["-DNVDR_TORCH"]
                    + (["/wd4067", "/wd4624"] if os.name == "nt" else [])
                ),
                "nvcc": ["-DNVDR_TORCH"],
            },
            library_dirs=[
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "nvdiffrast", "lib"
                )
            ],
            extra_link_args=(
                [
                    "/LIBPATH:"
                    + os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "nvdiffrast", "lib"
                    )
                ]
                if os.name == "nt"
                else []
            ),
            libraries=(
                [
                    "gdi32",
                    "opengl32",
                    "user32",
                    "setgpu",
                ]
                if os.name == "nt"
                else ["GL", "EGL"]
            ),
        ),
        CUDAExtension(
            name="nvdiffrast.nvdiffrast_plugin_gl",
            sources=[
                "./nvdiffrast/common/common.cpp",
                "./nvdiffrast/common/glutil.cpp",
                "./nvdiffrast/common/rasterize_gl.cpp",
                "./nvdiffrast/torch/torch_bindings_gl.cpp",
                "./nvdiffrast/torch/torch_rasterize_gl.cpp",
            ],
            extra_compile_args={
                "cxx": (
                    ["-DNVDR_TORCH"]
                    + (["/wd4067", "/wd4624"] if os.name == "nt" else [])
                ),
                "nvcc": ["-DNVDR_TORCH"],
            },
            library_dirs=[
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "nvdiffrast", "lib"
                )
            ],
            extra_link_args=(
                [
                    "/LIBPATH:"
                    + os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "nvdiffrast", "lib"
                    )
                ]
                if os.name == "nt"
                else []
            ),
            libraries=(
                [
                    "gdi32",
                    "opengl32",
                    "user32",
                    "setgpu",
                ]
                if os.name == "nt"
                else ["GL", "EGL"]
            ),
        ),
    ],
    cmdclass={"build_ext": BuildExtension},
)
