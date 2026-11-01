"""Download the Qwen-Image files used by SSUI without loading the models."""

import argparse
import fnmatch
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download


GENERATION_JOBS = {
    "Qwen/Qwen-Image": (
        "transformer/diffusion_pytorch_model*.safetensors",
        "text_encoder/model*.safetensors",
        "vae/diffusion_pytorch_model.safetensors",
        "tokenizer/*",
    ),
}

EDIT_JOBS = {
    "Qwen/Qwen-Image-Edit-2509": (
        "transformer/diffusion_pytorch_model*.safetensors",
    ),
    "Qwen/Qwen-Image-Edit": ("processor/*",),
}


def matching_files(repo_id: str, patterns: tuple[str, ...]) -> list[str]:
    files = HfApi().list_repo_files(repo_id)
    return sorted(
        file
        for file in files
        if any(fnmatch.fnmatchcase(file, pattern) for pattern in patterns)
    )


def download_repo(repo_id: str, patterns: tuple[str, ...], model_root: Path) -> None:
    files = matching_files(repo_id, patterns)
    if not files:
        raise RuntimeError(f"No files matched for {repo_id}: {patterns}")

    local_dir = model_root / repo_id
    for index, filename in enumerate(files, start=1):
        print(f"[{repo_id} {index}/{len(files)}] {filename}", flush=True)
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=local_dir,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, default=Path("models"))
    parser.add_argument(
        "--generation-only",
        action="store_true",
        help="Skip Qwen-Image-Edit-2509 and its processor",
    )
    args = parser.parse_args()

    jobs = dict(GENERATION_JOBS)
    if not args.generation_only:
        jobs.update(EDIT_JOBS)
    for repo_id, patterns in jobs.items():
        download_repo(repo_id, patterns, args.model_root)


if __name__ == "__main__":
    main()
