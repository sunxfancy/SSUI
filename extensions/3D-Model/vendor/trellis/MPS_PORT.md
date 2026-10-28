# SSUI MPS backend

The opt-in `SPARSE_BACKEND=torch`, `SPARSE_ATTN_BACKEND=sdpa`, `ATTN_BACKEND=sdpa`
path replaces spconv/xformers for the official TRELLIS image-large flow and mesh decoder.
These are also the defaults when CUDA is unavailable. CUDA machines retain existing defaults.

- Sparse features, learned weights, convolutions, residual blocks, attention and decoder operations stay on the selected GPU.
- Submanifold convolution keeps spconv checkpoint keys and `[out, kx, ky, kz, in]` weights. Cached integer neighbor maps are built on GPU using a fused Metal binary-search kernel; gather, matrix multiplication and accumulation also run on GPU. No dense voxel feature grid is built by convolution.
- SDPA chunks long queries without dropping keys, and batches small variable-length windows with a padding mask. This is exact attention rather than an approximate sparse mask.
- MPS pooling and cube attribute aggregation use index_add. Pooling preserves the original include_self=True mean semantics; mesh attribute aggregation uses include_self=False semantics.
- Row uniqueness uses stable lexicographic int32 sorts on MPS; int64 columns are split into two words to avoid Torch 2.4 MPS int64 sort corruption. Inverse maps and counts stay on GPU. Counts use integer index_add, with reductions for small, highly contended histograms. Only validation and dynamic-size metadata are read by the CPU.
- Compact coordinate domains (product of dimensions below 2**31) use Metal neighbor search. Larger domains use an exact GPU lexicographic join. No CPU coordinate-array fallback is used.
- The Metal bridge builds lazily using PyTorch cpp_extension, Xcode clang and ninja; the compiled library is cached under the system temporary directory, keyed by source/PyTorch/Python/architecture. First-build time is excluded from warm benchmarks. Build failures are explicit; install Xcode command-line tooling and ninja before running this path.
- Mesh extraction initializes FlexiCubes on the actual feature device; its small shape-check helper no longer requires Kaolin. Scalar index_select inputs become one-element index vectors for MPS.
- Top-level imports are lazy so unrelated CUDA renderers do not block inference.

Limitations: only odd-kernel stride-1 submanifold sparse convolution is implemented. Strided/inverse convolutions raise explicitly. The selected official models use separate sparse pooling/subdivision instead. Serialized Morton/Hilbert attention still requires vox2seq; official tested models use full/windowed attention. Gaussian/radiance-field rendering and CUDA UV texture baking remain outside this port. Export uses mesh-decoder vertex colors. GPU utilization is not claimed as a percentage; evidence consists of actual MPS tensors, numerical tests, and real-weight inference.

## Topology benchmark (16GB Mac, PyTorch 2.4.1)

`yarn test:trellis:topology` uses the saved 10,828-point real TRELLIS structure,
then subdivides it 2x/4x per axis. CPU baselines include the original CPU
coordinate transfer and return-to-MPS costs. Each result is checked exactly;
reported times are medians of three synchronized runs after warmup, without
neighbor-map caching or first-time compilation.

| Operation / input size | CPU ms | GPU ms | Speedup |
| --- | ---: | ---: | ---: |
| Neighbors / 10,828 points | 33.91 | 4.26 | 8.0x |
| Neighbors / 86,624 points | 223.94 | 8.65 | 25.9x |
| Neighbors / 692,992 points | 1777.32 | 50.94 | 34.9x |
| Row uniqueness / 5,543,936 rows | 4545.49 | 145.26 | 31.3x |
| Counts / 5,543,936 indices | 5.27 | 1.89 | 2.8x |

Torch 2.4 MPS large flat indices above 2**24 can silently round during
nonzero/index handling. Neighbor compaction uses bounded tiles to avoid this;
the regression suite includes odd positions above that boundary. Tests also
cover signed int64 extremes, duplicate/noncontiguous/empty rows, multiple
batches, dilation, invalid coordinates, and large-domain GPU joins.

```
SSUI_RUN_3D_RUNTIME_TESTS=1 yarn test_on trellis_runtime_test
# Same decoder + saved SLAT, with CPU-only topology as a controlled reference:
yarn test:trellis:topology --reference-mesh output/trellis-cpu-topology-reference
# Audit each GPU topology call against CPU during real mesh decoding:
yarn test:trellis:topology --audit-mesh output/trellis-topology-audit
```

The last two commands require `slat.pt` in their output directories and the
previously downloaded official weights. CPU reference and audit are diagnostic
modes only; normal model execution uses the GPU implementations.

The final real-weight mesh run (same saved SLAT) took 49.24 s for the mesh
stage, compared with 66.83 s for the CPU-topology reference (single runs, not a
multi-run model benchmark; neural computation uses MPS in both). The mesh has
228,766 vertices and 455,764 faces. Face indices match exactly; maximum vertex
absolute error is 1.19e-7, and the largest 8-bit color difference is 1, within
floating-point accumulation / color quantization tolerance. A separate
instrumented decode compared every topology call to CPU with zero tolerance.
Normal execution was then tested separately, without audit synchronization.

Row uniqueness explicitly rejects more than 2**24 rows rather than risking
Torch 2.4 large-index corruption. The tested full decoder needs 5,543,936 rows.
MPS CPU fallback is disabled in the topology and TRELLIS regression checks.
