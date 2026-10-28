"""Integer topology on MPS, without copying coordinate arrays to the CPU.

Torch 2.4 MPS unique(dim=0) is unavailable and int64 sort loses high bits.
Sort int32 columns stably instead; gather original rows to preserve their dtype.
Only dynamic output sizes / validation scalars cross the device boundary.
"""
import itertools
import math
import torch


def unique_rows(rows):
    """Lexicographically sorted rows, inverse map and exact integer counts."""
    if rows.device.type != 'mps':
        return torch.unique(rows, dim=0, return_inverse=True, return_counts=True)
    if rows.ndim != 2 or rows.dtype not in (torch.int32, torch.int64):
        raise ValueError('Expected a matrix of int32 or int64 coordinates')
    n = len(rows)
    if n > 2**24:
        raise ValueError('MPS row uniqueness is limited to 2**24 rows to preserve exact indices')
    if not n:
        empty = torch.empty(0, dtype=torch.long, device=rows.device)
        return rows.clone(), empty, empty.clone()
    # Split int64 columns into signed high and unsigned low words. Sorting the
    # latter after flipping its sign bit gives unsigned order using int32 sort.
    columns = []
    for c in rows.unbind(1):
        if rows.dtype == torch.int64:
            words = c.contiguous().view(torch.int32).reshape(-1, 2)
            columns.extend([words[:, 1], words[:, 0] ^ (-2**31)])
        else:
            columns.append(c)
    order = torch.arange(n, device=rows.device)
    for col in reversed(columns):
        order = order[torch.argsort(col[order], stable=True)]
    sorted_rows = rows[order]
    starts = torch.ones(n, dtype=torch.bool, device=rows.device)
    starts[1:] = (sorted_rows[1:] != sorted_rows[:-1]).any(1)
    groups = starts.int().cumsum(0, dtype=torch.int32) - 1
    inverse = torch.empty(n, dtype=torch.long, device=rows.device)
    inverse[order] = groups.long()
    boundaries = starts.nonzero().flatten()
    ends = torch.cat((boundaries[1:], boundaries.new_tensor([n])))
    return sorted_rows[boundaries], inverse, ends - boundaries


def count_indices(indices, minlength):
    """bincount for known nonnegative topology indices; int32 accumulation."""
    if indices.device.type != 'mps':
        return torch.bincount(indices.long(), minlength=minlength)
    if indices.numel() >= 2**31:
        raise ValueError('MPS topology counts must fit int32')
    if minlength <= 32:
        # Batch-layout histograms have very few bins and extreme contention.
        bins = torch.arange(minlength, device=indices.device)
        return (indices.unsqueeze(0) == bins.unsqueeze(1)).sum(1, dtype=torch.int32).long()
    result = torch.zeros(minlength, dtype=torch.int32, device=indices.device)
    result.index_add_(0, indices.long(), torch.ones_like(indices, dtype=torch.int32))
    return result.long()


def neighbor_pairs(coords, kernel, dilation):
    """Submanifold neighbors using GPU integer search (no dense feature grid)."""
    if not len(coords):
        e = torch.empty(0, dtype=torch.long, device=coords.device)
        return [(e, e) for _ in range(math.prod(kernel))]
    if bool((coords < 0).any()):
        raise ValueError('Sparse convolution coordinates must be nonnegative')
    dims = (coords.long().amax(0) + 1).tolist()
    # int32 search keys are exact on MPS, unlike int64 sorted values.
    compact = math.prod(dims) < 2**31
    if compact:
        strides = [math.prod(dims[i+1:]) for i in range(4)]
        stride = torch.tensor(strides, dtype=torch.int32, device=coords.device)
        keys = (coords.int() * stride).sum(1, dtype=torch.int32)
        order = torch.argsort(keys, stable=True)
        sorted_keys = keys[order]
        if bool((sorted_keys[1:] == sorted_keys[:-1]).any()):
            raise ValueError('Sparse coordinates must be unique')
    else:
        if len(unique_rows(coords)[0]) != len(coords):
            raise ValueError('Sparse coordinates must be unique')
    if compact:
        from .metal import extension
        offsets = torch.tensor([[0] + [(o-k//2)*d for o,k,d in zip(off,kernel,dilation)]
                                for off in itertools.product(*(range(k) for k in kernel))],
                               dtype=torch.int32, device=coords.device)
        found = extension().neighbors(coords.int().contiguous(), sorted_keys.contiguous(),
                                      order.int(), offsets, coords.new_tensor(dims).int(), stride)
        return compact_pairs(found)
    coords = coords.long()
    pairs = []
    limits = coords.new_tensor(dims)
    for off in itertools.product(*(range(k) for k in kernel)):
        delta = coords.new_tensor([0] + [(o-k//2)*d for o,k,d in zip(off,kernel,dilation)])
        query = coords + delta
        valid = ((query >= 0) & (query < limits)).all(1)
        # Unbounded coordinate domains: lexicographic GPU join, no packing.
        _, inverse, _ = unique_rows(torch.cat((coords, query)))
        lookup = torch.full((2*len(coords),), -1, dtype=torch.long, device=coords.device)
        lookup[inverse[:len(coords)]] = torch.arange(len(coords), device=coords.device)
        found = lookup[inverse[len(coords):]]
        dst = (valid & (found >= 0)).nonzero().flatten()
        src = found[dst]
        pairs.append((src, dst))
    return pairs


def compact_pairs(found):
    """Pack a KxN neighbor matrix without MPS large-flat-index rounding."""
    # Torch 2.4 MPS nonzero / flat-index handling loses integer precision
    # above 2**24. Compact bounded tiles; all local indices remain exact.
    # Read only K counts for Python slices, never the coordinate arrays.
    pairs = []
    for first in range(0, found.shape[1], 2**22):
        width = min(2**22, found.shape[1]-first)
        tile_pairs = []
        for block in found[:,first:first+width].split(max(1,2**23//width)):
            block = block.contiguous()
            flat = (block.flatten() >= 0).nonzero().flatten()
            src = block.flatten()[flat].long()
            counts = (block >= 0).sum(1,dtype=torch.int32).tolist()
            dst = [part - i*width + first for i,part in enumerate(flat.split(counts))]
            tile_pairs.extend(zip(src.split(counts),dst))
        if not pairs:
            pairs = tile_pairs
        else:
            pairs = [(torch.cat((a,c)),torch.cat((b,d)))
                     for (a,b),(c,d) in zip(pairs,tile_pairs)]
    return pairs
