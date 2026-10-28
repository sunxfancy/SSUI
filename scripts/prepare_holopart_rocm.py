"""Prepare pinned external HoloPart dependencies for native Windows HIP builds."""
import argparse
from pathlib import Path


FLAGS = '''{'cxx': ['/O2', '/std:c++17', '/EHsc'], 'nvcc': ['-O3', '-std=c++17',
    '--offload-arch=' + os.environ.get('GPU_ARCHS', 'gfx1201'),
    '--rocm-device-lib-path=' + os.path.join(os.environ['ROCM_HOME'], 'lib/llvm/amdgcn/bitcode')]}'''


def prepare(root):
    cluster = root / 'pytorch_cluster/setup.py'
    text = cluster.read_text()
    marker = "        Extension = CppExtension if suffix == 'cpu' else CUDAExtension"
    if '# SSUI native HIP' not in text:
        text = text.replace(marker, '''        # SSUI native HIP: compile bindings with the same clang ABI as PyTorch.
        if sys.platform == 'win32' and torch.version.hip:
            from pathlib import Path
            converted = []
            for source in sources:
                if source.endswith('.cpp'):
                    target = source[:-4] + '_binding.cu'
                    Path(target).write_text(Path(source).read_text())
                    converted.append(target)
                else:
                    converted.append(source)
            sources = converted
            extra_compile_args = ''' + FLAGS + '''
            extra_link_args = []
''' + marker)
        text = text.replace("include_dirs=[extensions_dir],", 'include_dirs=[extensions_dir, os.environ["ROCM_DEVEL_INCLUDE"]],')
        text = text.replace('use_ninja=False', 'use_ninja=True')
        text = text.replace("__version__ = '1.6.3'", "__version__ = '1.6.3+rocm72'")
        cluster.write_text(text)
    diso = root / 'diso/setup.py'
    text = diso.read_text()
    if '# SSUI native HIP' not in text:
        text = text.replace('    sources = [s for s in sources]', '''    # SSUI native HIP: hipify bindings and kernels together.
    from pathlib import Path
    binding = Path('src/pybind_binding.cu')
    binding.write_text(Path('src/pybind.cpp').read_text())
    sources = [str(binding)] + [s for s in source_cuda if Path(s).name != 'pybind_binding.cu']
    extension = CUDAExtension
    define_macros += [('WITH_CUDA', None)]
    extra_compile_args = ''' + FLAGS)
        text = text.replace('include_dirs = ["src"]', 'include_dirs = ["src", os.environ["ROCM_DEVEL_INCLUDE"]]')
        text = text.replace('version="0.1.4"', 'version="0.1.4+rocm72"')
        diso.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    prepare(parser.parse_args().source_root)
