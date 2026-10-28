"""Close generated part boundaries with MeshLab and preserve quad-only groups.

Only open parts are refined. Triangular facets are split into three convex
quads, sharing every edge midpoint; this also handles odd boundary loops.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

try:
    from .quad_quality import edge_counts, repair_polygons, validate_glb
except ImportError:  # Launched as an isolated native worker file.
    from quad_quality import edge_counts, repair_polygons, validate_glb


def quadrangulate(vertices, triangles):
    points = np.asarray(vertices, dtype=np.float64).tolist()
    midpoints = {}
    faces = []
    for a, b, c in triangles:
        center = len(points)
        points.append(np.asarray([points[a], points[b], points[c]]).mean(axis=0).tolist())
        mids = []
        for u, v in ((a,b), (b,c), (c,a)):
            key = tuple(sorted((int(u), int(v))))
            if key not in midpoints:
                midpoints[key] = len(points)
                points.append(((np.asarray(points[u]) + points[v]) / 2).tolist())
            mids.append(midpoints[key])
        ab, bc, ca = mids
        faces.extend([[int(a),ab,center,ca], [int(b),bc,center,ab], [int(c),ca,center,bc]])
    return np.asarray(points), faces


def thin_shell(mesh, half_thickness):
    """Preserve an open surface as a thin solid when a safe disk cap is unavailable."""
    mesh = mesh.copy()
    trimesh.repair.fix_normals(mesh, multibody=True)
    normals = np.array(mesh.vertex_normals)
    for vertex in np.flatnonzero(np.linalg.norm(normals,axis=1) < .5):
        incident = np.flatnonzero(np.any(mesh.faces == vertex,axis=1))
        normals[vertex] = mesh.face_normals[incident[0]]
    if not np.isfinite(normals).all() or np.any(np.linalg.norm(normals,axis=1) < .5):
        raise RuntimeError('Cannot construct finite shell normals')
    normals /= np.linalg.norm(normals,axis=1)[:,None]
    n = len(mesh.vertices)
    points = np.vstack([mesh.vertices + normals*half_thickness, mesh.vertices - normals*half_thickness])
    faces = mesh.faces.tolist() + (mesh.faces[:,::-1]+n).tolist()
    counts = edge_counts(mesh.faces.tolist())
    for face in mesh.faces:
        for a,b in zip(face,np.roll(face,-1)):
            if counts[tuple(sorted((int(a),int(b))))] == 1:
                faces.extend([[int(a+n),int(b+n),int(b)],[int(a+n),int(b),int(a)]])
    result = trimesh.Trimesh(points,np.asarray(faces),process=False)
    if not result.is_watertight:
        raise RuntimeError('Thin shell failed closed surface validation')
    return result


def close_part(vertices, faces):
    vertices, faces, triangles, initial_cleanup = repair_polygons(vertices, faces)
    counts = edge_counts(faces)
    before = sum(count == 1 for count in counts.values())
    if any(count > 2 for count in counts.values()):
        raise RuntimeError('Cannot close a part containing nonmanifold edges')
    stats = {'input_boundary_edges': before, 'input_faces': len(faces),
             'input_cleanup': initial_cleanup, 'refined': False, 'inserted_triangles': 0,
             'cap_area': 0., 'split_vertices': 0}
    if before:
        import pymeshlab
        ms = pymeshlab.MeshSet()
        ms.add_mesh(pymeshlab.Mesh(np.asarray(vertices), np.asarray(triangles)))
        ms.meshing_repair_non_manifold_vertices(vertdispratio=0)
        split = ms.current_mesh()
        stats['split_vertices'] = split.vertex_number() - len(vertices)
        original = trimesh.Trimesh(split.vertex_matrix(), split.face_matrix(), process=False)
        components = original.split(only_watertight=False,repair=False)
        surfaces, methods = [], []
        thickness = float(np.linalg.norm(np.ptp(np.asarray(vertices),axis=0))) * .00002
        for component in components:
            if component.is_watertight:
                surfaces.append(component)
                methods.append({'method':'already_closed','input_faces':len(component.faces),'output_faces':len(component.faces)})
                continue
            cap = pymeshlab.MeshSet()
            cap.add_mesh(pymeshlab.Mesh(component.vertices,component.faces))
            cap.meshing_close_holes(maxholesize=max(30,before+stats['split_vertices']),
                                   selfintersection=True,refinehole=False)
            current = cap.current_mesh()
            candidate = trimesh.Trimesh(current.vertex_matrix(),current.face_matrix(),process=False)
            valid_caps = (candidate.is_watertight and
                abs(float(candidate.volume)) > component.area * thickness * .1 and
                np.all(candidate.area_faces > float(np.linalg.norm(np.ptp(np.asarray(vertices),axis=0)))**2 * 1e-11))
            if valid_caps:
                surface = candidate
                inserted = len(surface.faces)-len(component.faces)
                cap_area = max(0.,float(surface.area-component.area))
                stats['inserted_triangles'] += inserted
                stats['cap_area'] += cap_area
                method = {'method':'intersection_checked_caps','inserted_triangles':inserted,'cap_area':cap_area}
            else:
                # Never disable intersection checking or silently delete a failed surface.
                surface = thin_shell(component,thickness)
                method = {'method':'bounded_thin_shell','half_thickness':thickness,
                          'max_vertex_offset_fraction_of_part_diagonal':.00002,
                          'remaining_edges_after_rejected_caps':int(sum(np.bincount(candidate.edges_unique_inverse)==1))}
            method.update({'input_faces':len(component.faces),'output_faces':len(surface.faces)})
            methods.append(method)
            surfaces.append(surface)
        mesh = trimesh.util.concatenate(surfaces)
        stats['components'] = methods
        stats['cap_area_fraction'] = stats['cap_area'] / original.area
        stats['preserved_components'] = len(surfaces)
        if not mesh.is_watertight:
            raise RuntimeError('Boundary closure lost a component or left an open surface')
        trimesh.repair.fix_normals(mesh, multibody=True)
        vertices, faces = quadrangulate(mesh.vertices, mesh.faces)
        triangles = [tri for a,b,c,d in faces for tri in ([a,b,c],[a,c,d])]
        stats.update({'refined': True,
                      'method': 'Intersection-checked caps or bounded thin shells; shared midpoint triangle-to-quad refinement'})
    final = edge_counts(faces)
    stats.update({'output_boundary_edges': sum(n == 1 for n in final.values()),
                  'nonmanifold_edges': sum(n > 2 for n in final.values()), 'output_faces': len(faces)})
    if stats['output_boundary_edges'] or stats['nonmanifold_edges'] or any(len(f) != 4 for f in faces):
        raise RuntimeError('Closure failed quad/manifold boundary validation: ' + json.dumps(stats))
    return np.asarray(vertices), faces, triangles, stats


def run(source, output):
    payload = json.loads(source.read_text(encoding='utf-8'))
    old_report = json.loads(Path(payload['artifacts']['report.json']).read_text(encoding='utf-8'))
    parts = json.loads(Path(payload['preview_path']).read_text(encoding='utf-8'))
    scene = trimesh.Scene()
    preview, reports = [], []
    offset = 0
    with (output / 'retopology.obj').open('w', encoding='utf-8', newline='\n') as obj:
        obj.write('# SSUI closed quad-only HoloPart groups\n')
        for index, part in enumerate(parts):
            try:
                vertices, faces, triangles, closure = close_part(part['vertices'], part['faces'])
            except RuntimeError as error:
                raise RuntimeError(f'Part {part["name"]}: {error}') from error
            name = part['name']
            obj.write(f'o {name}\n')
            for vertex in vertices:
                obj.write('v ' + ' '.join(format(v,'.17g') for v in vertex) + '\n')
            for face in faces:
                obj.write('f ' + ' '.join(str(v+offset+1) for v in face) + '\n')
            offset += len(vertices)
            mesh = trimesh.Trimesh(vertices, triangles, process=False)
            mesh.visual.face_colors = [(index*73+80)%220+20,(index*113+40)%220+20,(index*47+100)%220+20,255]
            scene.add_geometry(mesh, node_name=name, geom_name=name)
            preview.append({'name':name,'vertices':vertices.tolist(),'faces':faces})
            reports.append({'name':name,'faces':len(faces),'quads':len(faces),'closure':closure})
    scene.export(str(output/'retopology.glb'))
    degenerate = validate_glb(output/'retopology.glb')
    exported = trimesh.load(output/'retopology.glb', force='scene', process=False)
    if set(exported.geometry) != {part['name'] for part in parts} or not all(m.is_watertight for m in exported.geometry.values()):
        raise RuntimeError('Export changed part grouping or closed topology')
    quality = dict(old_report['quality'])
    quality.update({'parts':len(parts), 'quads':sum(p['quads'] for p in reports),
                    'boundary_edges':0,'boundary_edges_away_from_input':0,
                    'nonmanifold_edges':0,'degenerate_export_triangles':degenerate,'closed_parts':len(parts)})
    closure_report = {'source_quality':old_report['quality'], 'quality':quality, 'parts':reports,
                      'source_artifacts':payload['artifacts'],
                      'summary':{'refined_parts':sum(p['closure']['refined'] for p in reports),
                          'thin_shell_components':sum(c['method']=='bounded_thin_shell' for p in reports for c in p['closure'].get('components',[])),
                          'thin_shell_max_vertex_offset_fraction_of_part_diagonal':.00002},
                      'note':'Open surfaces capped or made into bounded thin shells and refined; closed parts kept. All groups separate. No global self-intersection guarantee.'}
    (output/'closure.json').write_text(json.dumps(closure_report,indent=2),encoding='utf-8')
    (output/'report.json').write_text(json.dumps({'backend':'QuadriFlow standalone + explicit boundary closure',
        'quality':quality,'parts':reports,'closure':closure_report},indent=2),encoding='utf-8')
    (output/'preview.json').write_text(json.dumps(preview),encoding='utf-8')
    (output/'result.json').write_text(json.dumps({'quality':quality}),encoding='utf-8')
    print(json.dumps(quality),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    run(args.source,args.output)
