"""Inspect real polygon exports and approximate shape error from saved payloads."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'extensions/3D-Model'))
from ssui_3dmodel.Retopology import _read_polygons


def inspect(payload_file):
    data = json.loads(payload_file.read_text(encoding='utf-8'))
    source = trimesh.load(data['input']['path'], force='mesh')
    exported = trimesh.load(data['retopology']['artifacts']['retopology.glb'], force='scene', process=False)
    preview_export = trimesh.load(data['retopology']['path'],force='scene',process=False)
    if 'closure.json' in data['retopology']['artifacts']:
        if set(exported.geometry) != set(preview_export.geometry) or not all(m.is_watertight for m in preview_export.geometry.values()):
            raise RuntimeError('Serialized Mesh export changed closed part grouping')
    target = trimesh.util.concatenate(list(exported.geometry.values()))
    vertices, polygons = _read_polygons(data['retopology']['artifacts']['retopology.obj'])
    edges = Counter(tuple(sorted((face[i], face[(i + 1) % len(face)])))
                    for face in polygons for i in range(len(face)))
    a, _ = trimesh.sample.sample_surface(source, 30000, seed=42)
    b, _ = trimesh.sample.sample_surface(target, 30000, seed=42)
    distances = np.concatenate([cKDTree(a).query(b)[0], cKDTree(b).query(a)[0]])
    diagonal = np.linalg.norm(source.bounds[1] - source.bounds[0])
    report = {'exported_part_count':len(exported.geometry),
        'serialized_export_part_count':len(preview_export.geometry),
        'serialized_export_watertight_parts':sum(m.is_watertight for m in preview_export.geometry.values()),
        'watertight_parts':sum(m.is_watertight for m in exported.geometry.values()),
        'exported_groups':{name:{'watertight':bool(m.is_watertight), 'winding_consistent':bool(m.is_winding_consistent)} for name,m in exported.geometry.items()},
        'polygons': len(polygons), 'quads': sum(len(face) == 4 for face in polygons),
        'quad_ratio': sum(len(face) == 4 for face in polygons) / len(polygons),
        'finite_vertices': bool(np.isfinite(vertices).all()),
        'boundary_edges': sum(count == 1 for count in edges.values()),
        'nonmanifold_edges': sum(count > 2 for count in edges.values()),
        'degenerate_glb_triangles': int(np.count_nonzero(target.area_faces <= diagonal**2 * 1e-14)),
        'approx_symmetric_surface_distance': {'method': 'nearest neighbour between 30000 surface samples each; not exact Hausdorff',
            'mean_percent_of_bbox_diagonal': float(distances.mean() / diagonal * 100),
            'p95_percent_of_bbox_diagonal': float(np.percentile(distances, 95) / diagonal * 100),
            'sample_max_percent_of_bbox_diagonal': float(distances.max() / diagonal * 100)}}
    (payload_file.parent / 'geometry-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    browser_file = payload_file.parent / 'browser-validation.json'
    if browser_file.is_file():
        segmentation = json.loads(Path(data['segmented']['artifacts']['segmentation.json']).read_text(encoding='utf-8'))
        browser = json.loads(browser_file.read_text(encoding='utf-8'))
        summary = {'browser': browser,
            'geometry': report, 'segmentation': segmentation,
            'input_faces': len(source.faces), 'artifacts': data['retopology']['artifacts'],
            'scope': browser.get('scope', 'Real SSUI upload/file routes and native UI components; standalone validation page, not full Tauri desktop automation'),
            'limitation': ('Degenerate export faces require cleanup' if report['degenerate_glb_triangles'] else
                'Input cuts are preserved; inspect boundary proximity details in the per-part report'),
            'quality_repair': data.get('quality_repair')}
        if 'completed' in data:
            summary['completion'] = json.loads(Path(data['completed']['artifacts']['completion.json']).read_text(encoding='utf-8'))
            summary['preparation'] = json.loads(Path(data['completed']['artifacts']['preparation.json']).read_text(encoding='utf-8'))
            summary['completion_artifacts'] = data['completed']['artifacts']
            summary['limitation'] = 'Generated amodal geometry changes the input shape; open boundaries remain and require review'
            if 'closure.json' in data['retopology']['artifacts']:
                summary['closure'] = json.loads(Path(data['retopology']['artifacts']['closure.json']).read_text(encoding='utf-8'))
                summary['limitation'] = 'Closed indexed topology verified per group; bounded thin shells can replace unsafe caps. Global self-intersections are not certified.'
        (payload_file.parent / 'verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payloads', type=Path)
    inspect(parser.parse_args().payloads)
