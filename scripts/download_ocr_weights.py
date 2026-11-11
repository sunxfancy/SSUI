"""Fetch EasyOCR's official-hash CRAFT and Chinese/English weights via ModelScope."""

import argparse
import hashlib
from pathlib import Path
import shutil
from zipfile import ZipFile


WEIGHTS = {
    "craft_mlt_25k.pth": "2f8227d2def4037cdb3b34389dcf9ec1",
    "zh_sim_g2.pth": "b601ce7143293387d3ec4f41a66edc07",
}


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path,
                        default=Path(".build/ocr-models"))
    args = parser.parse_args()
    model_dir = args.model_dir.resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    if all((model_dir / name).is_file() and md5(model_dir / name) == checksum
           for name, checksum in WEIGHTS.items()):
        print(f"EasyOCR weights verified: {model_dir}")
        return

    from modelscope import snapshot_download
    from modelscope.hub.api import ModelScopeConfig

    ModelScopeConfig.path_credential = str(model_dir / "credentials")
    cache = model_dir / "cache"
    detector = Path(snapshot_download("ms-agent/craft_mlt_25k",
                                      cache_dir=str(cache),
                                      allow_file_pattern="craft_mlt_25k.zip"))
    recognizer = Path(snapshot_download("Ceceliachenen/easyocr",
                                        cache_dir=str(cache),
                                        allow_file_pattern="zh_sim_g2.pth"))
    with ZipFile(detector / "craft_mlt_25k.zip") as archive:
        with archive.open("craft_mlt_25k.pth") as source:
            with (model_dir / "craft_mlt_25k.pth").open("wb") as target:
                shutil.copyfileobj(source, target)
    shutil.copy2(recognizer / "zh_sim_g2.pth", model_dir / "zh_sim_g2.pth")

    for name, expected in WEIGHTS.items():
        actual = md5(model_dir / name)
        if actual != expected:
            raise RuntimeError(f"{name}: MD5 mismatch ({actual} != {expected})")
    print(f"EasyOCR weights verified: {model_dir}")


if __name__ == "__main__":
    main()
