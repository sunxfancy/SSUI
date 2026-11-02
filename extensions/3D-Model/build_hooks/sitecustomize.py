"""Scoped workaround for PyTorch build output decoding on Windows ARM64."""
import os

if os.environ.get("SSUI_RIGGING_CUDA_BUILD") == "1":
    import subprocess
    original_popen = subprocess.Popen

    class DiagnosticPopen(original_popen):
        def __init__(self, *args, **kwargs):
            if kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding"):
                kwargs.setdefault("errors", "replace")
            super().__init__(*args, **kwargs)

    subprocess.Popen = DiagnosticPopen
    import torch.utils.cpp_extension
    # Windows GUI-launched processes can report an unusable OEM codepage.
    # Compiler output is diagnostic text; preserve it with replacement decoding.
    torch.utils.cpp_extension.SUBPROCESS_DECODE_ARGS = ("utf-8", "replace")
    extension = torch.utils.cpp_extension.BuildExtension
    original_init = extension.__init__
    original_build = extension.build_extensions

    def initialize(self, *args, **kwargs):
        # Old PyG setup scripts disable ninja on Windows. With recent
        # setuptools that path sends .cu files to cl instead of nvcc.
        kwargs["use_ninja"] = True
        original_init(self, *args, **kwargs)

    def build(self):
        for ext in self.extensions:
            flags = ext.extra_compile_args
            if not isinstance(flags, dict):
                flags = {"cxx": list(flags or []), "nvcc": []}
                ext.extra_compile_args = flags
            for compiler in ("cxx", "nvcc"):
                values = [flag for flag in flags.get(compiler, []) if not flag.startswith(("-std=", "/std:"))]
                values.append("/std:c++20" if compiler == "cxx" and os.name == "nt" else "-std=c++20")
                flags[compiler] = values
        original_build(self)

    extension.__init__ = initialize
    extension.build_extensions = build
    try:
        import ccimport
        import ccimport.core
        from pathlib import Path
        import shutil
        original_ccimport = ccimport.ccimport

        def native_build(*args, **kwargs):
            # Recover cleanly after an interrupted codegen build: ccimport's
            # hash cache otherwise returns a non-existent staged library.
            kwargs["disable_hash"] = True
            result = original_ccimport(*args, **kwargs)
            if isinstance(result, (str, Path)):
                path = Path(result)
                generated = path.parent / "build" / path.name.split(".")[0] / path.name
                if not path.exists() and generated.is_file():
                    shutil.copyfile(generated, path)
            return result

        ccimport.ccimport = native_build
        ccimport.core.ccimport = native_build
    except ImportError:
        pass
