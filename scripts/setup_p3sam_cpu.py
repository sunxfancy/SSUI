"""Apply small, explicit CPU compatibility changes to a local upstream checkout.

The network, checkpoint loader and segmentation algorithm remain upstream code.
CPU spconv and Sonata's existing non-Flash attention implement the same model.
"""
import argparse
from pathlib import Path


def patch(root):
    auto_mask = root / "P3-SAM/demo/auto_mask.py"
    text = auto_mask.read_text(encoding="utf-8")
    text = text.replace('.cuda()', '.to(os.environ.get("SSUI_P3SAM_DEVICE", "cuda"))')
    # Upstream overwrites both public arguments inside mesh_sam; honor the API.
    text = text.replace('    point_num = 100000\n    prompt_num = 400\n',
                        '    # Respect point_num and prompt_num supplied by AutoMask.\n')
    auto_mask.write_text(text, encoding="utf-8")
    model = root / "P3-SAM/model.py"
    text = model.read_text(encoding="utf-8")
    text = text.replace('from utils.misc import smart_load_model', '# Unused X-Part import omitted for isolated P3-SAM inference.')
    text = text.replace('download_root=\'/root/sonata\'',
        'download_root=os.path.join(os.path.expanduser("~"), ".cache/sonata/ckpt"), custom_config={"enable_flash": os.environ.get("SSUI_P3SAM_DEVICE") != "cpu"}')
    text = text.replace("os.path.join(os.path.expanduser('~'), '/.cache/p3sam/weights')",
        'os.path.join(os.path.expanduser("~"), ".cache/p3sam/weights")')
    model.write_text(text, encoding="utf-8")
    print("CPU device selection and native Sonata attention enabled in", root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    patch(parser.parse_args().checkout)
