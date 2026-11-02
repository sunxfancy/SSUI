"""Adapt a local upstream torch-scatter checkout for Windows ROCm compilation."""
from pathlib import Path
import argparse


def prepare(root):
    setup = root / "setup.py"
    text = setup.read_text(encoding="utf-8")
    text = text.replace("__version__ = '2.1.2'", "__version__ = '2.1.2+rocm72'")
    marker = "        Extension = CppExtension if suffix == 'cpu' else CUDAExtension"
    replacement = '''        if sys.platform == 'win32' and torch.version.hip:
            # Compile bindings and CPU dispatch with HIP clang to match the
            # Windows ROCm PyTorch ABI, rather than mixing MSVC and clang.
            from pathlib import Path
            hip_sources = []
            for source in sources:
                if source.endswith('.cpp'):
                    target = source[:-4] + '_binding.cu'
                    Path(target).write_text(Path(source).read_text(encoding='utf-8'), encoding='utf-8')
                    hip_sources.append(target)
                else:
                    hip_sources.append(source)
            sources = hip_sources
            extra_compile_args = {'cxx': ['/O2', '/std:c++17', '/EHsc'],
                'nvcc': ['-O3', '-std=c++17', '--offload-arch=' + os.environ.get('GPU_ARCHS', 'gfx1201'),
                    '--rocm-device-lib-path=' + os.path.join(os.environ['ROCM_HOME'], 'lib/llvm/amdgcn/bitcode')]}
            extra_link_args = []
        Extension = CppExtension if suffix == 'cpu' else CUDAExtension'''
    if replacement not in text:
        if marker not in text:
            raise RuntimeError("Unsupported torch-scatter setup.py")
        text = text.replace(marker, replacement)
    text = text.replace('include_dirs=[extensions_dir],',
        'include_dirs=[extensions_dir, os.environ["ROCM_DEVEL_INCLUDE"]] if torch.version.hip else [extensions_dir],')
    text = text.replace('use_ninja=False', 'use_ninja=True')
    setup.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source)
