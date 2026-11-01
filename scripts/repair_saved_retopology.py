"""Reuse a real GPU segmentation and rerun remeshing/export with quality cleanup."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'extensions/3D-Model'))
from ssui import Mesh
from ssui_3dmodel.Retopology import quad_remesh
from ss_executor.__main__ import convert_task_return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payloads', type=Path)
    parser.add_argument('--faces', type=int, default=5000)
    args = parser.parse_args()
    data = json.loads(args.payloads.read_text(encoding='utf-8'))
    before = args.payloads.with_name('preview-payloads.before-quality.json')
    if not before.exists():
        before.write_text(json.dumps(data, indent=2), encoding='utf-8')
    start = time.monotonic()
    result = quad_remesh(Mesh.load(data['segmented']['path']), args.faces)
    data['retopology'] = convert_task_return(result, str(ROOT / 'examples/basic/workflow-retopology.py'))
    data['quality_repair'] = {'reused_gpu_segmentation': data['segmented']['path'],
        'remesh_seconds': time.monotonic()-start, 'quality': result.quality}
    args.payloads.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps(data['quality_repair'], indent=2))


if __name__ == '__main__':
    main()
