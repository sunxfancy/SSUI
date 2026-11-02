import os
import sys
import torch

SPCONV_ALGO = 'auto'                                # 'auto', 'implicit_gemm', 'native'
# Windows ROCm's installed Triton cannot execute the upstream autotuner.
# Explicit GEMM retains GPU execution through PyTorch, at higher memory cost.
FLEX_GEMM_ALGO = os.environ.get(
    'FLEX_GEMM_ALGO',
    'explicit_gemm' if sys.platform == 'win32' and torch.version.hip
    else 'masked_implicit_gemm_splitk',
)
FLEX_GEMM_HASHMAP_RATIO = 2.0                       # Ratio of hashmap size to input size
