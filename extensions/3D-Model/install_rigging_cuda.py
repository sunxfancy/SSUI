"""Modern CUDA dependency installation, isolated from an existing CUDA Python."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def run(command, **kwargs):
    print(subprocess.list2cmdline(list(map(str, command))), flush=True)
    subprocess.run(list(map(str, command)), check=True, **kwargs)


def install(name, repo, base_python=None, download=False):
    base = Path(base_python or ROOT / ".build/cuda-arm64-venv/Scripts/python.exe").resolve()
    if not base.is_file():
        raise RuntimeError("CUDA Python was not found. Supply --base-python with an existing "
                           "NVIDIA CUDA-enabled Python interpreter; see RIGGING.md.")
    info = json.loads(subprocess.check_output([str(base), "-c",
        "import json,sys,sysconfig,torch; "
        "assert torch.cuda.is_available(), 'CUDA PyTorch required'; "
        "print(json.dumps(dict(site=sysconfig.get_paths()['purelib'], torch=torch.__version__, "
        "cuda=torch.version.cuda, capability=torch.cuda.get_device_capability(), python=sys.version)))"], text=True).splitlines()[-1])
    target = ROOT / ".venv/rigging" / name
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        run([base, "-m", "venv", str(target)])
    site = Path(subprocess.check_output([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], text=True).strip())
    # Append the immutable base's site-packages after this venv's own packages.
    # Dependencies installed below land only in target, never in the CUDA base.
    (site / "ssui_cuda_base.pth").write_text(info["site"] + "\n", encoding="utf-8")
    run([python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "packaging", "ninja"])
    requirements = Path(__file__).with_name("requirements-rigging-cuda.txt")
    run([python, "-m", "pip", "install", "-r", requirements])
    extra = {
        "mia": ["timm", "gradio>=6,<7", "spaces", "matplotlib", "plyfile", "iopath", "fvcore", "transformers==5.1.0"],
        "unirig": ["transformers==4.51.3", "timm", "python-box", "omegaconf", "pytorch_lightning", "lightning", "addict", "fast-simplification", "pyrender", "wandb", "psutil", "pccm", "pybind11", "ccimport", "lark"],
        "riganything": ["transformers==4.51.3"],
    }[name]
    if extra:
        run([python, "-m", "pip", "install", *extra])
    (target / "cuda-runtime.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    if download:
        code = {
            "riganything": "snapshot_download('Isabellaliu/RigAnything', allow_patterns=['riganything_ckpt.pt'], local_dir='ckpt')",
            "mia": "snapshot_download('jasongzy/Make-It-Animatable', allow_patterns=['output/best/new/**'], local_dir='.'); snapshot_download('jasongzy/Mixamo', repo_type='dataset', allow_patterns=['bones*.fbx'], local_dir='data/Mixamo')",
            "unirig": "[hf_hub_download('VAST-AI/UniRig', filename=p) for p in ['skeleton/articulation-xl_quantization_256/model.ckpt', 'skin/articulation-xl/model.ckpt']]; hf_hub_download('facebook/opt-350m', filename='config.json')",
        }[name]
        run([python, "-c", "from huggingface_hub import snapshot_download,hf_hub_download; " + code], cwd=repo)
    print(f"CUDA base ready for {name}: {python}. Model-specific native operators still require validation.", flush=True)
