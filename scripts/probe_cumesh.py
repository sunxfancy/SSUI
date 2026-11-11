"""Verify CuMesh read/write across the Windows HIP tall-copy boundary."""
import gc
import torch
import cumesh

for count in (1000, 1048576, 1048577, 5000000):
    vertices = torch.arange(count * 3, device='cuda', dtype=torch.float32).reshape(-1, 3) / 1000
    face_count = max(1, count * 7 // 5)
    faces = (torch.arange(face_count * 3, device='cuda', dtype=torch.int32) % count).reshape(-1, 3)
    mesh = cumesh.CuMesh()
    mesh.init(vertices, faces)
    actual_vertices, actual_faces = mesh.read()
    torch.testing.assert_close(actual_vertices, vertices, rtol=0, atol=0)
    torch.testing.assert_close(actual_faces, faces, rtol=0, atol=0)
    print(f'PASS exact CuMesh round trip: {count} vertices, {face_count} faces', flush=True)
    del mesh, vertices, faces, actual_vertices, actual_faces
    gc.collect()
    torch.cuda.empty_cache()
