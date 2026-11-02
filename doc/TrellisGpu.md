# TRELLIS GPU workflows

The focused workflows are `examples/advance/workflow-trellis.py` and
`examples/advance/workflow-trellis2.py`. Model loaders accept a local snapshot or
a Hugging Face model ID. Preparing the workflow does not initialize GPU weights.
The dedicated image uploader preserves the alpha mask. RGB inputs still need
the corresponding segmentation dependencies and model access; TRELLIS.2's
configured BRIA model requires authorization. Validation used an RGBA input.

## Native Windows ARM64 CUDA setup

Validation uses the isolated `.build/cuda-arm64-venv` described in
[Pixal3D GPU](Pixal3DGpu.md), Python 3.13, NVIDIA's CUDA 13.4 PyTorch nightly,
and the RTX Spark N1X. This is a development environment, not a published
Windows ARM64 CUDA dependency lock or installer profile.

The original TRELLIS uses FlexGEMM on Windows ARM64 and SDPA attention. Its
checkpoint adapter preserves the original `conv.weight` keys and tensor layout.
The port also corrects resolution-cache scaling during subdivision, uses Python
float sampler timesteps for NumPy 2, and replaces a Kaolin-only tensor-shape
check with the equivalent local check. Official full/window attention and mesh
decoding were exercised. Other checkpoints requiring inverse sparse convolutions
or serialized `vox2seq` attention are outside this validation.

Model snapshots used:

| Model | Official revision |
| --- | --- |
| `microsoft/TRELLIS-image-large` | `25e0d31ffbebe4b5a97464dd851910efc3002d96` |
| `microsoft/TRELLIS.2-4B` | `af44b45f2e35a493886929c6d786e563ec68364d` |

DINOv2 source is pinned to `7764ea0f912e53c92e82eb78a2a1631e92725fc8`.
TRELLIS.2 uses the vendored pipeline's existing DINOv3 mirror configuration.

## Verification

In PowerShell, select the GPU environment before starting server and executor:

```powershell
$env:SSUI_VENV_PATH = "$PWD/.build/cuda-arm64-venv"
$env:HF_HOME = "$PWD/.build/pixal3d-gpu/hf-cache"
$env:TORCH_HOME = "$PWD/.build/pixal3d-gpu/torch-cache"
$env:TRITON_CACHE_DIR = "$PWD/.build/pixal3d-gpu/triton-cache"
$env:FLEX_GEMM_AUTOTUNE_CACHE_PATH = "$PWD/.build/pixal3d-gpu/flex-autotune.json"
yarn start:server
# A second shell with the same environment:
yarn dev:executor
```

GPU checks and real model acceptance:

```powershell
yarn probe:trellis-gpu --output .build/other-3d-gpu/trellis-operators-final.json
yarn test:3d-gpu-workflow --engine trellis --model .build/other-3d-gpu/models/TRELLIS --image .build/pixal3d-gpu/input.png --output .build/other-3d-gpu/trellis-acceptance
yarn test:3d-gpu-workflow --engine trellis2 --export-mode vertex_colors --model .build/other-3d-gpu/models/TRELLIS.2 --image .build/pixal3d-gpu/input.png --output .build/other-3d-gpu/trellis2-colors-acceptance
```

The acceptance command discovers and prepares the workflow over HTTP, submits it
to the scheduler/executor, downloads the resulting GLB, and verifies nonempty
geometry. Its JSON report includes the device, duration, mesh counts, input hash
and output hash. A structurally valid GLB alone does not establish visual quality;
the resulting mesh also needs a multiview inspection.

On Windows ARM64, TRELLIS defaults to `vertex_colors`; other platforms retain
the existing `gaussian_texture` default. Select `vertex_colors` explicitly to
use this export on another platform.

TRELLIS completed in 46.581 seconds: 505,664 vertices, 1,007,544 faces,
20,182,140 bytes. The vertex-color GLB passed multiview inspection. The optional
`gaussian_texture` export was not validated on ARM64 and still requires the old
Gaussian rasterizer and UV-baking dependencies.

TRELLIS.2 defaults to vertex colors sampled from the generated color volume at
the decoded vertices. This mode exports the learned surface without UV packing
or remeshing. It does not retain metallic/roughness textures. `pbr_texture` remains
the only mode affected by `max_faces`, `texture_size` and `remesh`. It is
available for further validation: a 1024-resolution remeshed GLB completed with
497,874 faces but failed multiview inspection due to striped geometry; the direct
PBR export was cancelled after 791 seconds without phase progress in native UV
parameterization. Neither
PBR run is considered a validated production path. Remeshing defaults off.

The TRELLIS.2 vertex-color run completed in 331.055 seconds: 4,313,400 vertices,
8,672,102 faces, 173,080,620 bytes. Its raw surface passed multiview inspection
without the striped geometry seen in the remeshed export. It intentionally
retains the full decoded mesh, so files are larger than the simplified PBR path.

Recorded reports: [TRELLIS](windows-arm64-cuda-trellis-workflow.json),
[TRELLIS.2](windows-arm64-cuda-trellis2-workflow.json), and
[GPU operators](windows-arm64-cuda-trellis-operators.json). The local acceptance
artifacts and multiview previews are under `.build/other-3d-gpu/`.

Regression validation: 143 Python tests (131 passed, 12 skipped), three model-input
component tests, shared-component and functional-UI production builds, and five
native GPU compatibility checks passed. The 3D acceptance runs above exercised
actual weights independently of the default unit-test suite.

## Remaining models

StdGEN is not validated end to end. The vendored code currently provides
canonicalization and multiview functions, without an SSUI multiview-to-mesh node.
Importing its mesh model in the native environment fails at `loratorch`; `xatlas`,
`rembg` and `pytorch_lightning` are also absent. The current test manifest still
uses manually supplied paths for its image-stage weights. Unit-test stubs are
not evidence of successful StdGEN inference.

WorldClaw's current integration is a procedural scene/blockout adapter and is
not a validated neural GPU model generator.
