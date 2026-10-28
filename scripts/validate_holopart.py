"""Reuse the actual P3-SAM GPU segmentation, complete all parts, remesh and serialize."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'extensions/3D-Model'))
from ssui import Mesh
from ssui_3dmodel.HoloPart import complete_parts
from ssui_3dmodel.Retopology import quad_remesh
from ss_executor.__main__ import convert_task_return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved', type=Path, default=Path('output/retopology-rocm-validation/preview-payloads.json'))
    parser.add_argument('--output', type=Path, default=Path('output/holopart-rocm-validation'))
    parser.add_argument('--steps', type=int, default=50)
    parser.add_argument('--depth', type=int, default=8)
    parser.add_argument('--completed-job', type=Path, help='Reuse an already validated real GPU completion job')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ['SSUI_3D_OUTPUT'] = str(args.output.resolve())
    data = json.loads(args.saved.read_text(encoding='utf-8'))
    data.pop('quality_repair', None)
    prior = json.loads(Path(data['segmented']['artifacts']['segmentation.json']).read_text(encoding='utf-8'))
    if prior['runtime']['backend'] != 'native-rocm-flexgemm':
        raise RuntimeError('Expected the saved real native ROCm segmentation')
    start = time.monotonic()
    if args.completed_job:
        report = args.completed_job / 'completion.json'
        metadata = json.loads(report.read_text(encoding='utf-8'))
        if metadata['runtime']['backend'] != 'native-rocm' or metadata['input_parts'] != metadata['output_parts']:
            raise RuntimeError('Invalid saved GPU completion')
        import trimesh
        target = args.completed_job / 'prepared.glb'
        completed = Mesh(trimesh.load(target, force='scene', process=False))
        completed.artifacts = {name: str((args.completed_job / name).resolve()) for name in
                              ('completed.glb', 'prepared.glb', 'completion.json', 'preparation.json')}
    else:
        completed = complete_parts(Mesh.load(data['segmented']['path']), args.steps, resolution=args.depth)
    print('Completion finished; running standalone QuadriFlow', flush=True)
    completion_report = json.loads(Path(completed.artifacts['completion.json']).read_text(encoding='utf-8'))
    remesh_start = time.monotonic()
    result = quad_remesh(completed, 5000, split_components=True)
    script = str(ROOT / 'examples/basic/workflow-holopart.py')
    data['completed'] = convert_task_return(completed, script)
    data['retopology'] = convert_task_return(result, script)
    data['validation_stage_seconds'] = time.monotonic() - start
    data['completion_seconds'] = completion_report['seconds']
    data['remesh_export_seconds'] = time.monotonic() - remesh_start
    data['reused_completion'] = bool(args.completed_job)
    data['reused_segmentation'] = str(args.saved.resolve())
    data['segmentation_runtime'] = prior['runtime']
    (args.output / 'preview-payloads.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps({'completion_seconds': data['completion_seconds'],
                      'remesh_export_seconds': data['remesh_export_seconds'], 'quality': result.quality}, indent=2))


if __name__ == '__main__':
    main()
