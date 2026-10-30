"""Explicit, reported preparation of generated fragments for QuadriFlow."""
import json
from pathlib import Path


def prepare(job, minimum_area_fraction=0.001):
    import numpy as np
    import trimesh
    import pymeshlab
    scene = trimesh.load(job / 'completed.glb', force='scene', process=False)
    prepared = trimesh.Scene()
    reports = []
    for name, source in scene.geometry.items():
        ms = pymeshlab.MeshSet()
        ms.add_mesh(pymeshlab.Mesh(source.vertices, source.faces))
        # Remove invalid face incidence, then split singular vertices without moving them.
        ms.meshing_remove_duplicate_faces()
        ms.meshing_repair_non_manifold_edges(method='Remove Faces')
        ms.meshing_repair_non_manifold_vertices(vertdispratio=0)
        current = ms.current_mesh()
        mesh = trimesh.Trimesh(current.vertex_matrix(), current.face_matrix(), process=False)
        components = mesh.split(only_watertight=False, repair=False)
        kept = [c for c in components if c.area >= mesh.area * minimum_area_fraction and len(c.faces) >= 8]
        if not kept:
            raise RuntimeError(f'No usable generated surface in {name}; raw completion retained')
        dropped_area_fraction = max(0., 1 - sum(c.area for c in kept) / source.area)
        if dropped_area_fraction > 0.025:
            raise RuntimeError(f'Fragment cleanup would remove over 2.5% of {name}; raw completion retained')
        result = trimesh.util.concatenate(kept)
        counts = np.bincount(result.edges_unique_inverse)
        if np.any(counts > 2):
            raise RuntimeError(f'Nonmanifold edges remain in {name}')
        prepared.add_geometry(result, node_name=name, geom_name=name)
        reports.append({'name': name, 'input_components': len(components), 'retained_components': len(kept),
            'removed_components': len(components)-len(kept), 'removed_area_fraction': dropped_area_fraction,
            'input_faces': len(source.faces), 'manifold_repair_removed_faces': len(source.faces)-len(mesh.faces),
            'prepared_faces': len(result.faces),
            'boundary_edges': int(sum(counts == 1)), 'nonmanifold_edges': int(sum(counts > 2))})
    prepared.export(str(job / 'prepared.glb'))
    report = {'minimum_component_area_fraction': minimum_area_fraction, 'minimum_component_faces': 8,
              'maximum_removed_area_fraction_per_part': 0.025, 'parts': reports,
              'note': 'Raw completion retained. Duplicate/nonmanifold faces and small generated islands removed; singular vertices split, no caps.'}
    (job / 'preparation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job', type=Path)
    prepare(parser.parse_args().job)
