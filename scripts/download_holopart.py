"""Download and verify the pinned official HoloPart weights (about 3.8 GB)."""
import argparse
import hashlib
from pathlib import Path
from huggingface_hub import snapshot_download

REVISION = '29cdb1417121842c4c4d59b9d283cc734f8c3aec'
HASHES = {
    'part_encoder/diffusion_pytorch_model.safetensors': '95cdf41201fcb656f5a56cfebdbbe51c3daff46c025839f3528e7a9a3aef7ace',
    'transformer/diffusion_pytorch_model.safetensors': '1b68b7e632635a3818da6c783fb40bc04ab7c93041a0f31a962cc6f576f6d0b3',
    'vae/diffusion_pytorch_model.safetensors': 'b43b006e5692223877427cdb568c2c1477f52a2d226db4d5eb354b4886c167a4',
}


def verify(directory):
    for name, expected in HASHES.items():
        with (directory / name).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise RuntimeError(f'HoloPart weight hash mismatch: {name}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.build/holopart/weights'))
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only:
        snapshot_download('VAST-AI/HoloPart', revision=REVISION, local_dir=str(args.output), token=False)
    verify(args.output)
    print('Official HoloPart weights verified: ' + REVISION)
