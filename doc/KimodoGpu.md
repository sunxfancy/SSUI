# Kimodo motion generation on native Windows ARM64 CUDA

Validated on the NVIDIA RTX Spark N1X with Python 3.13.15 and PyTorch
`2.16.0.dev20261026+cu134`. The parent environment remains on Transformers
4.57.6. `extensions/Motion/install_kimodo.ps1` creates an isolated child with
Transformers 5.1.0, PEFT 0.18.1 and the minimal inference/export requirements,
reusing the parent's GPU PyTorch without replacing the Image/Video dependencies.
It supports explicit `-ProjectPython` and `-EnvironmentPath` arguments and honors
`SSUI_VENV_PATH` when selecting the parent environment. No new custom Python
wheel was built or published for this work; PyGLM 2.8.2 has a public native
Windows ARM64 CPython 3.13 wheel.

## Workflow

`examples/advance/workflow-motion.py` accepts a text prompt and returns
`ssui.base.MotionClip`. The frontend plays the generated 3D joint positions,
offers frame scrubbing, camera rotation/zoom and root following, and downloads
the original NPZ, BVH and preview JSON. The JSON records the actual joint names,
parent hierarchy, frame rate, Y-up world coordinates and generation metadata.
This is skeletal motion, not automatic rigging of an arbitrary generated mesh.

`KimodoTextToMotion` retains its original NPZ-path API. The new
`GenerateKimodoMotion` produces the typed artifact. Workflow preparation does not
load weights or require the child environment. File names are unique per run.

## Model provenance

| Component | Revision |
| --- | --- |
| Official `nv-tlabs/kimodo` source | `1aece8c124d73d255ceff5086d983b844c9f4e94` |
| Official `nvidia/Kimodo-SOMA-RP-v1.1` | `6c9233af1180b8151e3c4703477104af5dce9dd5` |
| `raducius/Llama-3-8B-Instruct-LLM2Vec-mntp-merged` | `01417d622e8a85d6f4b308dac0e37d478a9a87d1` |
| `McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp-supervised` adapter | `baa8ebf04a1c2500e61288e7dad65e8ae42601a7` |

The test machine had no Hugging Face login. This run explicitly opted into the
previously documented community merged text-encoder snapshot via
`SSUI_KIMODO_TEXT_ENCODER_BASE`; it does not establish access to, or identical
outputs from, the official gated Meta encoder. The community snapshot uses the
Llama 3 license. Default model downloads still follow Kimodo's normal sources.

## Reproduction

Install using the command in [Motion README](../extensions/Motion/Readme.md), then
start SSUI server and executor in separate shells with these variables:

```powershell
$env:SSUI_VENV_PATH = "$PWD/.build/cuda-arm64-venv"
$env:SSUI_KIMODO_PYTHON = "$PWD/.build/motion-gpu/installed-venv/Scripts/python.exe"
$env:HF_HOME = "$PWD/.build/pixal3d-gpu/hf-cache"
# Optional: only when using the downloaded community snapshot listed above.
$env:SSUI_KIMODO_TEXT_ENCODER_BASE = "$PWD/.build/motion-gpu/models/Llama-3-8B-Instruct-LLM2Vec-mntp-merged"
yarn start:server
# In a second shell with the same variables:
yarn dev:executor
```

Run actual HTTP-to-artifact acceptance:

```powershell
yarn test:kimodo-gpu-workflow --output .build/motion-gpu/acceptance
```

The test discovers/prepares the workflow, executes real generation, downloads
JSON/NPZ/BVH, verifies the recorded denoiser device is CUDA, checks finite moving
joint positions and orthonormal local rotations, and checks matching frame counts.
The child writes its actual model frame rate rather than assuming a fixed rate.

## Results and limitations

The prompt `A person walks forward and waves their right hand.` generated
120 frames at 30 FPS (four seconds), 77 joints, with 50 diffusion steps and seed 42.
The full HTTP-to-download run took 37.575 seconds. The actual denoiser reported
`cuda:0`. Root displacement was 5.985 meters; rendered frames showed walking and
a raised waving hand. Downloads were approximately 0.78 MB NPZ and 0.28 MB BVH.
See [acceptance report](windows-arm64-cuda-kimodo-workflow.json).

BVH was independently read back using bvhio, evaluated through forward kinematics,
converted from centimeters to meters and compared with the generated joint
positions. The report records the error over all 120 frames and 77 joints.
The maximum position error was 0.136 mm and RMSE was 0.0094 mm.
This verifies hierarchy, timing, rotations and export units, independently of
the preview JSON.

The native `motion_correction` postprocessor is not installed or enabled; this
run does not validate foot-skating correction. G1 and other offered checkpoints,
longer/multiple-prompt clips and official gated-encoder generation are not part
of this acceptance. No character mesh skinning or retargeting is performed.

Regression checks on the standalone motion branch: 143 Python tests (131 passed,
12 skipped), four frontend motion
tests, shared-component and functional-UI production builds passed. The installer
was tested against the native CUDA parent; its final probe confirmed the child
GPU and Transformers versions. It intentionally omits optional web-demo packages;
inherited packages for other SSUI extensions are not intended to run in the child.
