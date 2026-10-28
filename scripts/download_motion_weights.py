"""Download public motion weights, recording exact Hugging Face revisions."""
import argparse
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', choices=['msflow', 'hy-motion'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--list', action='store_true', help='List available model files only')
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.model == 'msflow':
        requests = [('ly-corporation/MSFlow', 'e272ad6d023a18af53d248ffdd7b36560d1cea4a', ['checkpoints/t2m/MMDiT_xyz_pretrained/**', 'LICENSE'], root),
                    ('distilbert/distilbert-base-uncased', '12040accade4e8a0f71eabdb258fecc2e7e948be', ['*.json', '*.txt', '*.safetensors'], root / 'text-encoder')]
    else:
        requests = [('tencent/HY-Motion-1.0', '620dd559f8d964aac2f82f1204fe6a35ad8ad14d', ['HY-Motion-1.0-Lite/*', 'LICENSE*'], root / 'motion'),
                    ('Qwen/Qwen3-8B', 'b968826d9c46dd6066d109eabc6255188de91218', ['*.json', '*.txt', '*.safetensors', '*.jinja', 'LICENSE*'], root / 'qwen'),
                    ('openai/clip-vit-large-patch14', '32bd64288804d66eefd0ccbe215aa642df71cc41', ['*.json', '*.txt', '*.safetensors', 'merges.txt'], root / 'clip')]
    api = HfApi()
    provenance = []
    for repo, revision, patterns, directory in requests:
        info = api.model_info(repo, revision=revision)
        if args.list:
            print(repo, [file.rfilename for file in info.siblings], flush=True)
            continue
        print(f'Downloading {repo}@{info.sha} to {directory}', flush=True)
        snapshot_download(repo, revision=info.sha, allow_patterns=patterns, local_dir=str(directory), max_workers=4)
        provenance.append({'repo': repo, 'revision': info.sha, 'directory': str(directory), 'patterns': patterns})
        (root / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
