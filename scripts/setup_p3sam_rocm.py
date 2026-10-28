"""Prepare upstream P3-SAM for the explicit native ROCm inference adapter."""
import argparse
from pathlib import Path


def prepare(root):
    model = root / "P3-SAM/model.py"
    text = model.read_text(encoding="utf-8")
    text = text.replace('from utils.misc import smart_load_model', '# Unused X-Part import omitted for isolated inference.')
    text = text.replace('sonata.load("sonata",', 'sonata.load(os.environ.get("SSUI_SONATA_CHECKPOINT", "sonata"),')
    text = text.replace("download_root='/root/sonata'", 'download_root=os.path.join(os.path.expanduser("~"), ".cache/sonata/ckpt")')
    model.write_text(text, encoding="utf-8")
    auto = root / "P3-SAM/demo/auto_mask.py"
    text = auto.read_text(encoding="utf-8")
    text = text.replace('    point_num = 100000\n    prompt_num = 400\n',
                        '    # Respect sampling parameters supplied by AutoMask.\n')
    auto.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    prepare(parser.parse_args().checkout)
