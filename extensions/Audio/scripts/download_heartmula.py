"""Download the three public official HeartMuLa inference components."""

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    for repository, destination in (
        ("HeartMuLa/HeartMuLaGen", root),
        ("HeartMuLa/HeartMuLa-oss-3B-happy-new-year", root / "HeartMuLa-oss-3B"),
        ("HeartMuLa/HeartCodec-oss-20260123", root / "HeartCodec-oss"),
    ):
        print(f"Downloading {repository} to {destination}", flush=True)
        snapshot_download(repo_id=repository, local_dir=destination)


if __name__ == "__main__":
    main()
