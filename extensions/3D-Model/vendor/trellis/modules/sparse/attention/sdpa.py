"""Variable-length attention using device-native PyTorch SDPA."""
import torch
import torch.nn.functional as F


def packed_attention(q, k, v, q_lengths, kv_lengths, query_chunk=512):
    if len(q_lengths) >= 4 and min(q_lengths) > 0 and min(kv_lengths) > 0 and max(q_lengths + kv_lengths) <= 512:
        # Batch small windows instead of launching one GPU kernel per window.
        from collections import defaultdict
        groups = defaultdict(list)
        qs, ks, vs = q.split(q_lengths), k.split(kv_lengths), v.split(kv_lengths)
        for i, (qn, kn) in enumerate(zip(q_lengths, kv_lengths)):
            groups[((qn-1).bit_length(), (kn-1).bit_length())].append(i)
        results = [None] * len(q_lengths)
        for indices in groups.values():
            for start in range(0, len(indices), 32):
                batch = indices[start:start+32]
                qb = torch.nn.utils.rnn.pad_sequence([qs[i] for i in batch], batch_first=True).transpose(1, 2)
                kb = torch.nn.utils.rnn.pad_sequence([ks[i] for i in batch], batch_first=True).transpose(1, 2)
                vb = torch.nn.utils.rnn.pad_sequence([vs[i] for i in batch], batch_first=True).transpose(1, 2)
                lengths = torch.tensor([kv_lengths[i] for i in batch], device=q.device)
                mask = torch.arange(kb.shape[2], device=q.device)[None, :] < lengths[:, None]
                out = F.scaled_dot_product_attention(qb, kb, vb, attn_mask=mask[:, None, None, :]).transpose(1, 2)
                for j, i in enumerate(batch):
                    results[i] = out[j, :q_lengths[i]]
        return torch.cat(results, dim=0)
    outputs = []
    qi = ki = 0
    for qn, kn in zip(q_lengths, kv_lengths):
        qb = q[qi:qi+qn].transpose(0, 1).unsqueeze(0)
        kb = k[ki:ki+kn].transpose(0, 1).unsqueeze(0)
        vb = v[ki:ki+kn].transpose(0, 1).unsqueeze(0)
        # All keys remain visible; chunking queries preserves exact attention.
        chunks = [F.scaled_dot_product_attention(qb[:, :, start:start+query_chunk], kb, vb)
                  for start in range(0, qn, query_chunk)]
        out = torch.cat(chunks, dim=2) if chunks else qb.new_empty((1, qb.shape[1], 0, vb.shape[-1]))
        outputs.append(out.squeeze(0).transpose(0, 1))
        qi += qn
        ki += kn
    return torch.cat(outputs, dim=0)
