# Additional text-to-motion models

The Motion extension now exposes three additional workflows. Kimodo's existing
workflow and environment are unchanged.

| Workflow | Validated model | Output | Deployment characteristics |
| --- | --- | --- | --- |
| `examples/advance/workflow-motion-ardy.py` | ARDY-SOMA-RP-30FPS-Horizon60 | 77 joints, 30 FPS | Reuses the existing LLM2Vec encoder weights; separate Transformers 5.8.1 environment |
| `examples/advance/workflow-motion-msflow.py` | MotionSpaceFlow MMDiT XYZ | 22 joints, 20 FPS | Small DistilBERT encoder; no gated encoder or FlashAttention required for this inference path |
| `examples/advance/workflow-motion-hy.py` | HY-Motion 1.0 Lite | 52 joints, 30 FPS | Requires Qwen3-8B and CLIP; larger download and memory requirement |

All three return `MotionClip` for the existing 3D skeleton player, timeline and
JSON/NPZ downloads. This integration generates clips using ARDY's autoregressive
model; it does not yet expose its live prompt-streaming interface. BVH/FBX export,
mesh skinning and retargeting are not implemented for these new workflows.
Use English motion descriptions for the validated path. HY-Motion prompt
rewriting and duration prediction are disabled; the selected duration is used.

## Install

Select a parent SSUI environment with a working GPU PyTorch build. Each installer
creates a separate child environment and inherits the parent's native packages
through a `.pth` file. It does not install or replace the parent's PyTorch.
Git is required; HY-Motion also uses Git LFS for its static body assets and
normalization data. Retain the source checkout after installation.

```powershell
$env:SSUI_VENV_PATH = "$PWD/.build/cuda-arm64-venv"
yarn install:ardy
yarn install:msflow
yarn install:hy-motion
yarn download:motion-model msflow --root models/msflow
yarn download:motion-model hy-motion --root models/hy-motion
```

Defaults are `.venv/ardy`, `.venv/msflow`, `.venv/hy-motion`. Installers accept
`--path` and `--source` for custom locations. New source clones are checked out
at pinned revisions; existing source directories must already match the pin.
The generic downloader pins model revisions and writes `provenance.json`.

ARDY downloads its official motion checkpoint on first use. The default text
encoder uses the upstream gated Meta/LLM2Vec path, requiring access. Explicit
local encoder overrides are `SSUI_ARDY_TEXT_ENCODER_BASE` and
`SSUI_ARDY_TEXT_ENCODER_ADAPTER`. This machine reuses the community merged MNTP
snapshot already documented for Kimodo in [KimodoGpu.md](KimodoGpu.md), plus the
official supervised adapter. This does not validate access to, or identical
outputs from, the gated encoder.

## Runtime configuration

The workflows resolve `SSUI_ARDY_PYTHON`, `SSUI_MSFLOW_PYTHON` and
`SSUI_HY_MOTION_PYTHON`, falling back to their default child environments.
`SSUI_MSFLOW_MODEL_DIR` and `SSUI_HY_MOTION_MODEL_DIR` override the default
`models/msflow` and `models/hy-motion` weight roots.

Optional machine-local settings live in the ignored `.build/motion-runtimes.json`.
Each engine can specify `python` and an `env` object; process environment
variables take precedence. Example:

```json
{
  "msflow": {
    "python": "C:/path/to/SSUI/.build/msflow/venv/Scripts/python.exe",
    "env": {
      "SSUI_MSFLOW_MODEL_DIR": "C:/path/to/SSUI/.build/msflow/models",
      "HF_HUB_OFFLINE": "1"
    }
  }
}
```

This machine has entries for all three installed runtimes, including ARDY's
existing local encoder and cache paths. Starting SSUI from this checkout uses
those settings automatically. Do not copy that file to another machine without
updating its absolute paths.

## Windows ARM64 adaptation and validation

Validated on RTX Spark N1X, CPython 3.13.15, native PyTorch
`2.16.0.dev20261026+cu134`, NumPy 2.5.4. ARDY uses Transformers 5.8.1/PEFT 0.19.0;
HY-Motion and MSFlow use the existing Transformers 4.57.6. Upstream NumPy 1.x,
old PyTorch/x86 wheel pins and MSFlow's Python 3.10.9 training environment cannot
be installed unchanged on this host. These adapters use the native stack and
only the inference dependencies. ARDY is installed with `--no-deps` to allow
this explicitly validated NumPy 2 adaptation; upstream package metadata still
declares `numpy<2`. The inherited Image/Video packages are not intended to run
inside these child environments.

ARDY's optional C++ motion correction and TensorRT are disabled. Its validated
SOMA checkpoint supports at most **10 denoising steps**, reflected in the UI.
MSFlow uses the official XYZ demo's `myheun2` sampler and sigma 0.01; HY-Motion
uses 50 Euler steps with CFG 5.0. Static WoodenMesh buffers excluded from the
HY checkpoint are loaded from its pinned source assets; missing learned
parameters are rejected. No randomly initialized model fallback is permitted.

```powershell
$env:SSUI_VENV_PATH = "$PWD/.build/cuda-arm64-venv"
yarn test:motion-model ardy --output .build/ardy/workflow-acceptance
yarn test:motion-model msflow --output .build/msflow/workflow-acceptance
yarn test:motion-model hy-motion --output .build/hy-motion/workflow-acceptance
yarn preview:motion-model .build/ardy/workflow-acceptance/motion.motion.json
```

The test prepares each sandboxed SSUI workflow, executes real generation,
serializes the executor result, and checks frame counts, finite moving joints,
hierarchy validity and JSON/NPZ agreement. It checks rotation orthogonality when
rotation matrices are present, and confirms CUDA when requested. Reports and
artifacts are saved in the selected directories. See
[the recorded acceptance results](windows-arm64-motion-models.json).

`preview:motion-model` renders a root-following GIF and four-frame contact sheet
using Pillow. Previews for all three validated clips are available beside their
local acceptance reports as `preview.gif` and `contact-sheet.png`.

All three passed with a four-second prompt and seed 42. The recorded elapsed
times include interpreter startup and model loading; they are not steady-state
generation benchmarks. This validates the workflow-to-artifact path, not HTTP/UI
operation, subjective action fidelity, CPU/MPS inference or every model variant.
