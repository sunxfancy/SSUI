"""Fetch pinned official sources and install independent auto-rigging environments."""
import argparse
import json
import os
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(Path(__file__).with_name("rigging_models.json").read_text(encoding="utf-8"))


def run(*args, cwd=None):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=(*MANIFEST, "all"))
    parser.add_argument("--source-only", action="store_true", help="Fetch source only, without installing or downloading weights")
    parser.add_argument("--python", default=sys.executable, help="Python 3.11 interpreter used to create the isolated environment")
    parser.add_argument("--download", action="store_true", help="Download inference checkpoints/templates after installation")
    parser.add_argument("--cuda-native", action="store_true", help="Build a modern native CUDA runtime, including Windows ARM64")
    parser.add_argument("--base-python", type=Path, help="Existing CUDA-enabled Python to inherit without modifying its packages")
    parser.add_argument("--torch-index-url", default="https://download.pytorch.org/whl/cu128",
                        help="PyTorch wheel index for UniRig/RigAnything; MIA uses its upstream pinned stack")
    args = parser.parse_args()
    if not args.source_only and platform.system() == "Windows" and platform.machine().lower() in ("arm64", "aarch64"):
        args.cuda_native = True
    names = MANIFEST if args.model == "all" else [args.model]
    for name in names:
        info = MANIFEST[name]
        repo = ROOT / "models/rigging" / name
        repo.parent.mkdir(parents=True, exist_ok=True)
        if not repo.exists():
            repo.mkdir()
            run("git", "init", repo)
            run("git", "remote", "add", "origin", info["repo"], cwd=repo)
        # Do not overwrite an existing user's checkout or local modifications.
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo, text=True)
        if dirty.strip():
            raise RuntimeError(f"{repo} has local changes; refusing to switch its revision")
        run("git", "fetch", "--depth=1", "origin", info["revision"], cwd=repo)
        run("git", "checkout", "--detach", info["revision"], cwd=repo)
        run("git", "submodule", "update", "--init", "--recursive", "--depth=1", cwd=repo)
        if args.source_only:
            continue
        if args.cuda_native:
            from install_rigging_cuda import install
            install(name, repo, args.base_python, args.download)
            continue
        run(args.python, "-c", "import sys; assert sys.version_info[:2] == (3, 11), 'Use --python with a Python 3.11 interpreter'")
        env = ROOT / ".venv/rigging" / name
        run(args.python, "-m", "venv", env)
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(python, "-m", "pip", "install", "--upgrade", "pip")
        if name != "mia":
            run(python, "-m", "pip", "install", "torch>=2.7,<3", "torchvision", "--index-url", args.torch_index_url)
        run(python, "-m", "pip", "install", "-r", repo / "requirements.txt", cwd=repo)
        run(python, "-m", "pip", "install", "huggingface_hub")
        if args.download:
            if name == "mia":
                run(python, "-c", "from huggingface_hub import snapshot_download; "
                    "snapshot_download('jasongzy/Make-It-Animatable', allow_patterns=['output/best/new/**'], local_dir='.'); "
                    "snapshot_download('jasongzy/Mixamo', repo_type='dataset', allow_patterns=['bones*.fbx'], local_dir='data/Mixamo')", cwd=repo)
            elif name == "riganything":
                run(python, "-c", "from huggingface_hub import snapshot_download; "
                    "snapshot_download('Isabellaliu/RigAnything', allow_patterns=['riganything_ckpt.pt'], local_dir='ckpt')", cwd=repo)
            else:
                run(python, "-c", "from huggingface_hub import hf_hub_download; "
                    "[hf_hub_download('VAST-AI/UniRig', filename=p) for p in "
                    "['skeleton/articulation-xl_quantization_256/model.ckpt', 'skin/articulation-xl/model.ckpt']]; "
                    "hf_hub_download('facebook/opt-350m', filename='config.json')")
        print(f"{name}: source and Python dependencies installed. Native CUDA packages may require platform-specific setup; see RIGGING.md.")


if __name__ == "__main__":
    main()
