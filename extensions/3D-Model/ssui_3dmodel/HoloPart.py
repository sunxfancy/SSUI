"""Optional HoloPart amodal completion in an isolated native ROCm process."""
import json
import os
from pathlib import Path
import subprocess
from ssui import Mesh
from ssui.annotation import param
from ssui.config import SSUIConfig
from ssui.controller import Slider
from .Retopology import _job, quad_remesh


def _run(command, log):
    # Keep long GPU jobs observable without retaining progress bars in memory.
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
    if process.returncode:
        raise RuntimeError(f'HoloPart failed ({process.returncode}); see {log}:\n' +
                           log.read_text(encoding='utf-8', errors='replace')[-6000:])


def complete_parts(mesh: Mesh, steps=50, seed=42, resolution=8) -> Mesh:
    if mesh._model is None:
        raise ValueError('Import a segmented model before completion')
    if not 1 <= steps <= 100 or not 6 <= resolution <= 9:
        raise ValueError('HoloPart requires 1..100 steps and octree depth 6..9')
    root = Path(os.environ.get('SSUI_HOLOPART_ROOT', '')).resolve()
    python = os.environ.get('SSUI_HOLOPART_PYTHON')
    weights = Path(os.environ.get('SSUI_HOLOPART_WEIGHTS', '')).resolve()
    if not python or not (root / 'scripts/inference_holopart.py').is_file() or not (weights / 'model_index.json').is_file():
        raise RuntimeError('Configure SSUI_HOLOPART_ROOT, SSUI_HOLOPART_PYTHON and SSUI_HOLOPART_WEIGHTS; see doc/HoloPart.md')
    job = _job()
    source = job / 'segmented.glb'
    mesh._model.export(str(source))
    worker = Path(__file__).with_name('holopart_worker.py')
    _run([python, '-u', str(worker), str(root), str(weights), str(source), str(job),
          '--steps', str(steps), '--seed', str(seed), '--depth', str(resolution)], job / 'holopart.log')
    report = job / 'completion.json'
    target = job / 'completed.glb'
    if not target.is_file() or not report.is_file():
        raise RuntimeError('HoloPart produced no validated result')
    metadata = json.loads(report.read_text(encoding='utf-8'))
    if metadata['runtime']['backend'] != 'native-rocm' or metadata['input_parts'] != metadata['output_parts']:
        raise RuntimeError('HoloPart runtime or part-count validation failed')
    import trimesh
    prepared = job / 'prepared.glb'
    preparation = job / 'preparation.json'
    if not prepared.is_file() or not preparation.is_file():
        raise RuntimeError('HoloPart produced no prepared geometry report')
    result = Mesh(trimesh.load(prepared, force='scene', process=False))
    result.artifacts = {name: str(job / name) for name in
                        ('completed.glb', 'prepared.glb', 'completion.json', 'preparation.json')}
    return result


@param('steps', Slider(1, 100, 1), default=50)
@param('resolution', Slider(6, 9, 1), default=8)
@param('seed', Slider(0, 100000, 1), default=42)
def CompleteParts(config: SSUIConfig, mesh: Mesh) -> Mesh:
    """补全被遮挡的部件表面；会生成新几何，不保留原 UV 或纹理。"""
    return Mesh() if config.is_prepare() else complete_parts(mesh, config['steps'], config['seed'], config['resolution'])


@param('target_faces', Slider(100, 200000, 100), default=5000)
def QuadRemeshCompleted(config: SSUIConfig, mesh: Mesh) -> Mesh:
    """逐曲面重拓扑并闭合开口，保留部件分组；补洞加密会增加面数。"""
    return Mesh() if config.is_prepare() else remesh_completed(mesh, config['target_faces'])


def remesh_completed(mesh: Mesh, target_faces=5000) -> Mesh:
    python = os.environ.get('SSUI_HOLOPART_PYTHON')
    if not python:
        raise RuntimeError('Configure SSUI_HOLOPART_PYTHON for native boundary closure')
    if os.environ.get('SSUI_QUADRIFLOW_WSL_DISTRO'):
        raise RuntimeError('HoloPart remeshing requires native QuadriFlow, not WSL')
    raw = quad_remesh(mesh, target_faces, split_components=True)
    job = _job()
    source = job/'source.json'
    source.write_text(json.dumps({'artifacts':raw.artifacts,'preview_path':raw.preview_path}),encoding='utf-8')
    _run([python,'-u',str(Path(__file__).with_name('holopart_closure.py')),str(source),str(job)],job/'closure.log')
    import trimesh
    result = Mesh(trimesh.load(job/'retopology.glb',force='scene',process=False))
    result.artifacts = {name:str(job/name) for name in ('retopology.obj','retopology.glb','report.json','preview.json','closure.json')}
    result.preview_path = str(job/'preview.json')
    result.quality = json.loads((job/'result.json').read_text(encoding='utf-8'))['quality']
    return result
