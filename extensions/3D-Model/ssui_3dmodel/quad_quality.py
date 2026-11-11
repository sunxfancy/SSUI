"""Bounded geometric cleanup without welding separate sheets or capping cuts."""
from collections import Counter

import numpy as np


def _candidates(face):
    if len(face) == 3:
        return [[face]]
    a, b, c, d = face
    return [[[a, b, c], [a, c, d]], [[a, b, d], [b, c, d]]]


def _areas(vertices, triangles):
    p = vertices[np.asarray(triangles)]
    normals = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    return np.linalg.norm(normals, axis=1), normals


def _best_triangles(vertices, face, epsilon):
    choices = []
    for triangles in _candidates(face):
        areas, normals = _areas(vertices, triangles)
        if float(areas.min()) > epsilon:
            # Prefer consistently oriented facets when both diagonals work.
            normal = normals.sum(axis=0)
            consistent = bool(np.all(normals @ normal > 0))
            choices.append((consistent, float(areas.min()), triangles))
    return max(choices, key=lambda item: item[:2])[2] if choices else None


def edge_counts(faces):
    return Counter(tuple(sorted((a, b))) for face in faces
                   for a, b in zip(face, face[1:] + face[:1]))


def validate_glb(path):
    """Check the actual float32 export, not only the pre-export float64 mesh."""
    import trimesh

    scene = trimesh.load(path, force="scene", process=False)
    threshold = max(float(np.linalg.norm(scene.extents)) ** 2 * 1e-14, 1e-30)
    degenerate = 0
    for geometry in scene.geometry.values():
        if not np.isfinite(geometry.vertices).all():
            raise ValueError("GLB export contains non-finite vertices")
        degenerate += int(np.count_nonzero(geometry.area_faces <= threshold))
    if degenerate:
        raise ValueError(f"GLB export contains {degenerate} degenerate triangles after float32 conversion")
    return degenerate


def repair_polygons(vertices, faces):
    """Preserve connectivity; unfold collapsed edges within 0.005% of part size.

Zero-area faces carry no surface and are removed. Other degenerate quads are
regularized towards their own one-ring neighbours, never globally welded.
Failure to produce nonzero triangles is explicit rather than silently exported.
"""
    original = np.asarray(vertices, dtype=np.float64)
    diagonal = float(np.linalg.norm(np.ptp(original, axis=0)))
    epsilon = max(diagonal * diagonal * 1e-12, 1e-30)
    limit = diagonal * 0.00005
    retained = []
    removed = 0
    for face in faces:
        area = max(float(_areas(original, candidate)[0].sum()) for candidate in _candidates(face))
        if area <= epsilon:
            removed += 1
        else:
            retained.append(list(face))
    if not retained:
        raise ValueError("QuadriFlow produced no nonzero-area surface")
    current = original.copy()
    neighbours = [set() for _ in current]
    for face in retained:
        for a, b in zip(face, face[1:] + face[:1]):
            neighbours[a].add(b)
            neighbours[b].add(a)
    bad = {i for i, face in enumerate(retained) if _best_triangles(current, face, epsilon) is None}
    initial_bad = len(bad)
    for _ in range(12):
        if not bad:
            break
        candidate = current.copy()
        for vertex in sorted({v for i in bad for v in retained[i]}):
            if neighbours[vertex]:
                mean = current[sorted(neighbours[vertex])].mean(axis=0)
                candidate[vertex] += 0.001 * (mean - current[vertex])
        delta = candidate - original
        lengths = np.linalg.norm(delta, axis=1)
        candidate = original + delta * np.minimum(1, limit / np.maximum(lengths, 1e-30))[:, None]
        new_bad = {i for i, face in enumerate(retained) if _best_triangles(candidate, face, epsilon) is None}
        if not new_bad.issubset(bad):
            raise ValueError("Bounded quad cleanup would damage previously valid faces")
        current, bad = candidate, new_bad
    if bad:
        raise ValueError(f"{len(bad)} degenerate faces could not be repaired within the movement limit")
    triangles = [triangle for face in retained for triangle in _best_triangles(current, face, epsilon)]
    displacement = np.linalg.norm(current - original, axis=1)
    # Compact unused vertices left behind by zero-area faces.
    used = np.unique(np.asarray([v for face in retained for v in face]))
    remap = np.full(len(current), -1, dtype=int)
    remap[used] = np.arange(len(used))
    cleaned_faces = [[int(remap[v]) for v in face] for face in retained]
    cleaned_triangles = [[int(remap[v]) for v in face] for face in triangles]
    return current[used].tolist(), cleaned_faces, cleaned_triangles, {
        "removed_zero_area_faces": removed,
        "regularized_faces": initial_bad,
        "moved_vertices": int(np.count_nonzero(displacement > diagonal * 1e-14)),
        "max_vertex_displacement": float(displacement.max()),
        "max_vertex_displacement_fraction": float(displacement.max() / diagonal) if diagonal else 0,
        "movement_limit_fraction": 0.00005,
        "degenerate_export_triangles": 0,
    }


def inspect_boundaries(vertices, faces, reference):
    """Compare boundary positions with the input, without assuming cuts are holes."""
    from scipy.spatial import cKDTree

    reference = reference.copy()
    reference.merge_vertices(merge_tex=True, merge_norm=True)
    v = np.asarray(vertices)
    counts = edge_counts(faces)
    boundary = np.asarray([edge for edge, count in counts.items() if count == 1], dtype=int).reshape(-1, 2)
    input_counts = np.bincount(reference.edges_unique_inverse, minlength=len(reference.edges_unique))
    source_edges = reference.edges_unique[input_counts == 1]
    lengths = np.linalg.norm(v[boundary[:, 0]] - v[boundary[:, 1]], axis=1)
    stats = {"input_boundary_edges": len(source_edges), "output_boundary_edges": len(boundary),
        "nonmanifold_edges": sum(count > 2 for count in counts.values()),
        "output_boundary_length": float(lengths.sum()),
        "policy": "preserve input cuts; no automatic caps or cross-part welding"}
    if not len(boundary):
        return {**stats, "boundary_edges_near_input": 0, "boundary_edges_away_from_input": 0}
    if not len(source_edges):
        return {**stats, "boundary_edges_near_input": 0, "boundary_edges_away_from_input": len(boundary)}
    start = np.asarray(reference.vertices)[source_edges[:, 0]]
    delta = np.asarray(reference.vertices)[source_edges[:, 1]] - start
    tree = cKDTree(start + delta / 2)
    p = v[boundary]
    samples = np.stack((p[:, 0], p.mean(axis=1), p[:, 1]), axis=1).reshape(-1, 3)
    _, nearest = tree.query(samples, k=min(16, len(start)))
    nearest = np.asarray(nearest).reshape(len(samples), -1)
    a, d = start[nearest], delta[nearest]
    t = np.clip(np.sum((samples[:, None] - a) * d, axis=2) / np.maximum(np.sum(d*d, axis=2), 1e-30), 0, 1)
    distance = np.linalg.norm(samples[:, None] - (a + t[:, :, None] * d), axis=2).min(axis=1)
    edge_distance = distance.reshape(-1, 3).max(axis=1)
    tolerance = float(np.linalg.norm(reference.extents) * .002 + np.median(lengths) * .5)
    near = int(np.count_nonzero(edge_distance <= tolerance))
    return {**stats, "boundary_edges_near_input": near, "boundary_edges_away_from_input": len(boundary) - near,
        "boundary_match_tolerance": tolerance,
        "boundary_distance_p95": float(np.percentile(edge_distance, 95)),
        "classification_note": "Approximate proximity to input boundary segments; away edges need review, not automatic filling"}
