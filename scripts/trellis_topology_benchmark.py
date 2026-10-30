"""Exact topology checks and synchronized CPU-roundtrip / MPS benchmarks."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extensions/3D-Model/vendor'))
os.environ['SPARSE_BACKEND'] = 'torch'
os.environ['ATTN_BACKEND'] = 'sdpa'
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '0'
import torch
from trellis.modules.sparse import SparseTensor, SparseConv3d
from trellis.modules.sparse.topology import unique_rows, count_indices, neighbor_pairs, compact_pairs


def timed(fn, repeats):
    fn()
    samples = []
    for _ in range(repeats):
        torch.mps.synchronize()
        start = time.perf_counter()
        result = fn()
        torch.mps.synchronize()
        samples.append((time.perf_counter()-start)*1000)
        del result
    return statistics.median(samples)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', default='output/trellis-topology.json')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--reference-mesh', type=Path)
    parser.add_argument('--audit-mesh', type=Path)
    parser.add_argument('--compare-mesh', nargs=2, metavar=('BEFORE', 'AFTER'))
    args = parser.parse_args()
    if args.reference_mesh or args.audit_mesh:
        # Controlled reference: identical current decoder, only topology runs
        # on CPU. Used to distinguish kernel changes from old artifact drift.
        import trellis.modules.sparse.topology as topology
        import trellis.modules.sparse.conv.conv_torch as convolution
        def cpu_unique(rows):
            return tuple(t.to(rows.device) for t in torch.unique(rows.cpu(),dim=0,return_inverse=True,return_counts=True))
        def cpu_counts(indices, minlength):
            return torch.bincount(indices.cpu().long(),minlength=minlength).to(indices.device)
        def cpu_neighbors(coords,kernel,dilation):
            conv = SparseConv3d(1,1,kernel,dilation=dilation)
            x = SparseTensor(torch.zeros(len(coords),1),coords.cpu())
            return [(a.to(coords.device),b.to(coords.device)) for a,b in conv._pairs(x)]
        if args.audit_mesh:
            def checked(name, gpu, cpu):
                def run(*a, **kw):
                    actual, expected = gpu(*a, **kw), cpu(*a, **kw)
                    def compare(x,y):
                        if isinstance(x,(tuple,list)):
                            for xx,yy in zip(x,y): compare(xx,yy)
                        else:
                            torch.testing.assert_close(x.cpu(),y.cpu(),rtol=0,atol=0)
                    print('Audit',name,tuple(a[0].shape),flush=True)
                    compare(actual,expected)
                    return actual
                return run
            cpu_unique = checked('unique', topology.unique_rows, cpu_unique)
            cpu_counts = checked('counts', topology.count_indices, cpu_counts)
            cpu_neighbors = checked('neighbors', convolution.neighbor_pairs, cpu_neighbors)
        convolution.neighbor_pairs = cpu_neighbors
        for name, module in list(sys.modules.items()):
            if name.startswith('trellis.'):
                if hasattr(module, 'unique_rows'): module.unique_rows = cpu_unique
                if hasattr(module, 'count_indices'): module.count_indices = cpu_counts
        sys.path.insert(0,str(ROOT/'extensions/3D-Model'))
        from ssui_3dmodel.trellis_mps_runner import main as run_mesh
        sys.argv = [sys.argv[0],'--stage','mesh','--output',str(args.reference_mesh or args.audit_mesh)]
        run_mesh()
        return
    if args.compare_mesh:
        import numpy as np
        import trimesh
        before, after = [trimesh.load(ROOT/p, force='mesh', process=False) for p in args.compare_mesh]
        assert np.array_equal(before.faces, after.faces), 'Mesh faces changed'
        np.testing.assert_allclose(before.vertices, after.vertices, rtol=1e-5, atol=1e-6)
        color_error = int(np.abs(before.visual.vertex_colors.astype(int)-after.visual.vertex_colors.astype(int)).max())
        assert color_error <= 1
        result = dict(vertices=len(after.vertices), faces=len(after.faces), faces_exact=True,
                      vertex_max_abs_error=float(np.abs(before.vertices-after.vertices).max()), color_max_error=color_error)
        print(json.dumps(result, indent=2))
        (ROOT/args.output).write_text(json.dumps(result,indent=2)+'\n')
        return
    assert torch.backends.mps.is_available()
    torch.manual_seed(17)
    # Large signed 64-bit, duplicate, empty, noncontiguous and column cases.
    for dtype in (torch.int32, torch.int64):
        for cols in (2, 3, 4):
            rows = torch.randint(-30, 30, (200, cols), dtype=dtype)
            if dtype == torch.int64:
                rows = rows * 2**40 + torch.randint(-(2**31), 2**31, rows.shape)
            rows = torch.cat((rows, rows[:50]))
            for case in (rows, rows[:0], rows.T.contiguous().T, rows[:1].expand(50,-1)):
                expected = torch.unique(case, dim=0, return_inverse=True, return_counts=True)
                actual = unique_rows(case.to('mps'))
                for a,b in zip(actual, expected):
                    torch.testing.assert_close(a.cpu(), b, rtol=0, atol=0)
    extremes = torch.tensor([[2**63-1, -2**63], [-2**63, 2**63-1], [2**31, -2**31], [2**63-1, -2**63]], dtype=torch.int64)
    for a,b in zip(unique_rows(extremes.to('mps')),torch.unique(extremes,dim=0,return_inverse=True,return_counts=True)):
        torch.testing.assert_close(a.cpu(),b,rtol=0,atol=0)
    for coords in (torch.tensor([[0,0,0,0],[0,1,0,0],[1,0,0,0],[1,2,1,0]], dtype=torch.int32),
                   torch.tensor([[0,2**30,0,0],[0,2**30+1,0,0],[1,0,0,0]], dtype=torch.int64)):
        for dilation in ((1,1,1), (2,1,3)):
            conv = SparseConv3d(1,1,3,dilation=dilation)
            expected = conv._pairs(SparseTensor(torch.zeros(len(coords),1), coords))
            actual = neighbor_pairs(coords.to('mps'), (3,3,3), dilation)
            for (a,b),(c,d) in zip(actual,expected):
                torch.testing.assert_close(a.cpu(),c,rtol=0,atol=0)
                torch.testing.assert_close(b.cpu(),d,rtol=0,atol=0)
    for size in (0, 1, 8, 1000):
        idx = torch.randint(0, max(size,1), (10000,)) if size else torch.empty(0,dtype=torch.long)
        torch.testing.assert_close(count_indices(idx.to('mps'),size).cpu(),torch.bincount(idx,minlength=size),rtol=0,atol=0)
    for invalid in (torch.tensor([[0,-1,0,0]]),torch.zeros(2,4,dtype=torch.int32)):
        try:
            neighbor_pairs(invalid.to('mps'),(3,3,3),(1,1,1))
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid coordinates accepted')
    assert len(neighbor_pairs(torch.empty(0,4,dtype=torch.int32,device='mps'),(3,3,3),(1,1,1))) == 27
    # Regression for >2**24 flattened neighbor positions: old MPS nonzero
    # rounded odd indices and silently changed the generated mesh.
    found = torch.full((27, 630000), -1, dtype=torch.int32, device='mps')
    found[:, 629997] = 17
    found[:, 629999] = 29
    for src,dst in compact_pairs(found):
        assert src.cpu().tolist() == [17,29]
        assert dst.cpu().tolist() == [629997,629999]
    del found
    if args.check_only:
        print('Exact GPU topology edge cases passed')
        return
    coords = torch.load(ROOT/'output/trellis-mac/coords.pt', weights_only=True).cpu()
    records = []
    def bench(name, cpu, gpu):
        expected, actual = cpu(), gpu()
        if isinstance(actual, list):
            for oi,(a,b) in enumerate(zip(actual,expected)):
                for ci,(aa,bb) in enumerate(zip(a,b)):
                    aa,bb=aa.cpu(),bb.cpu()
                    if not torch.equal(aa,bb):
                        bad=(aa!=bb).nonzero().flatten()[:10]
                        print(name,oi,ci,bad.tolist(),aa[bad].tolist(),bb[bad].tolist(),flush=True)
                    torch.testing.assert_close(aa,bb,rtol=0,atol=0)
        elif isinstance(actual, tuple):
            for a,b in zip(actual,expected): torch.testing.assert_close(a.cpu(),b.cpu(),rtol=0,atol=0)
        else: torch.testing.assert_close(actual.cpu(),expected.cpu(),rtol=0,atol=0)
        cpu_ms = timed(cpu,args.repeats)
        gpu_ms = timed(gpu,args.repeats)
        row = dict(name=name,cpu_ms=cpu_ms,gpu_ms=gpu_ms,speedup=cpu_ms/gpu_ms,exact=True)
        records.append(row)
        print(json.dumps(row),flush=True)
    for scale in (1,8,64):
        c = coords.clone()
        if scale > 1:
            factor = round(scale**(1/3))
            offsets = torch.cartesian_prod(*[torch.arange(factor)]*3)
            c = torch.cat((c[:,None,:1].expand(-1,scale,-1),c[:,None,1:]*factor+offsets),2).reshape(-1,4)
        cm = c.to('mps')
        conv = SparseConv3d(1,1,3)
        def cpu_pairs():
            x = SparseTensor(torch.zeros(len(c),1),cm.cpu())
            return [(a.to('mps'),b.to('mps')) for a,b in conv._pairs(x)]
        bench(f'neighbors_{len(c)}',cpu_pairs,lambda: neighbor_pairs(cm,(3,3,3),(1,1,1)))
        offsets = torch.cartesian_prod(*[torch.arange(2)]*3)
        rows = (c[:,None,1:]+offsets).reshape(-1,3).to('mps')
        bench(f'unique_{len(rows)}',lambda: tuple(t.to('mps') for t in torch.unique(rows.cpu(),dim=0,return_inverse=True,return_counts=True)),lambda: unique_rows(rows))
        _,idx,_ = unique_rows(rows)
        size = int(idx.max())+1
        bench(f'counts_{len(idx)}',lambda: torch.bincount(idx.cpu(),minlength=size).to('mps'),lambda: count_indices(idx,size))
    path = ROOT/args.output
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(dict(torch=torch.__version__,device='mps',records=records),indent=2)+'\n')
    print('All exact checks passed:',path)

if __name__ == '__main__':
    main()
