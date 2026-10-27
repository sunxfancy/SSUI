# Motion extension

The Motion extension provides both NVIDIA Kimodo text-to-motion generation and
MediaPipe video pose recognition with BVH/Blender reconstruction.

The Motion extension runs NVIDIA Kimodo in an isolated child environment. This
keeps Kimodo's pinned `transformers==5.1.0` dependency from replacing the
versions used by SSUI's Image and Video extensions, while reusing the project's
verified CUDA/ROCm PyTorch installation. The installer only installs Kimodo's
inference/export dependencies; its optional demo and native motion correction
are separate.

## Windows ARM64 CUDA workflow

The native ARM64 CUDA path is validated with SOMA-RP-v1.1. Select the parent GPU
environment explicitly when installing:

```powershell
./extensions/Motion/install_kimodo.ps1 `
  -ProjectPython .build/cuda-arm64-venv/Scripts/python.exe `
  -EnvironmentPath .build/motion-gpu/installed-venv
$env:SSUI_KIMODO_PYTHON = "$PWD/.build/motion-gpu/installed-venv/Scripts/python.exe"
```

Open `examples/advance/workflow-motion.py`, enter a motion description, and run.
The `MotionClip` output supports playback, scrubbing, camera rotation, zoom,
following the moving character, and NPZ/BVH/JSON downloads. Generated motion uses
its actual skeleton hierarchy and Y-up world coordinates in meters, independently
of the MediaPipe pose-recognition format.

The original `KimodoTextToMotion` function still returns the NPZ path for existing
Python callers. The workflow uses `GenerateKimodoMotion` to return the typed clip.

See [native GPU validation](../../doc/KimodoGpu.md) for the actual model sources,
acceptance command, BVH roundtrip results, and remaining limitations.

## Apple Silicon / 16GB Mac

The existing `txt2motion_kimodo` workflow now supports `device=auto|mps|cuda|cpu`
and `text_encoder_device=auto|mps|cuda|cpu`. Auto selects CUDA first, then MPS,
then CPU. On MPS, text encoding and motion inference run sequentially on GPU.
The original CUDA/ROCm CLI path is retained.

```bash
yarn install:kimodo
yarn test:kimodo:smoke --download-only
yarn test:kimodo:smoke --workflow --duration 2 --steps 20 --output output/kimodo-mac-workflow
yarn test:kimodo:preview
SSUI_RUN_MOTION_RUNTIME_TESTS=1 yarn test
```

The Python installer creates `.venv/kimodo` using the current interpreter;
Python 3.12 / macOS arm64 is verified. Core versions are constrained in
`kimodo-macos-constraints.txt` (PyTorch 2.14.1, Transformers 5.1.0). It installs
Kimodo source `1aece8c124d73d255ceff5086d983b844c9f4e94` and omits optional native
motion correction. It does not update SSUI's main PyTorch 2.4.1 environment.

The default small-memory model files need approximately 16.3GB of disk space:

- Official `nvidia/Kimodo-SOMA-RP-v1.1`, revision `6c9233af1180b8151e3c4703477104af5dce9dd5`.
- Community `raducius/Llama-3-8B-Instruct-LLM2Vec-mntp-merged`, revision
  `61c9d7b02d40b7a770807c0a4e17a3ece59ccd27`. This is a community distribution of
  the Llama-3 Instruct + MNTP text base, not an NVIDIA-supported checkpoint;
  the Llama license still applies. Official gated Meta weights were unavailable
  to this machine, so the actual Mac run used this explicitly pinned artifact.
- Official McGill supervised LLM2Vec adapter, revision
  `baa8ebf04a1c2500e61288e7dad65e8ae42601a7`.

`--download-only` downloads these public artifacts, verifies LFS SHA-256 hashes,
and writes `models/kimodo-mac/provenance.json`. The downloaded licenses remain
alongside the files. `SSUI_KIMODO_MODEL_DIR` changes the root folder;
`SSUI_KIMODO_TEXT_ENCODER_BASE` and `SSUI_KIMODO_TEXT_ENCODER_ADAPTER` can select
compatible local safetensors directories. The streaming reader currently
expects a single `model.safetensors` base file; arbitrary sharded/raw gated
checkpoints require preparation before use.

The text encoder uses the upstream LlamaBiModel and PEFT forward implementations.
Weights are memory mapped and only one transformer block plus its LoRA weights
is resident on GPU at a time. Blocks return to meta storage immediately after
execution; text weights are released before loading the motion network. No
quantization or fabricated embeddings are used. Model construction converts
float64 statistics/schedule buffers to float32 before MPS placement; learned
motion inference stays on MPS. CPU fallback is disabled in runtime tests.

Verified result on this 16GB Mac: a walking prompt, 2 seconds, 30 FPS, 60 frames,
77 joints, 20 denoising steps. Text encoding took about 14 seconds; a full SSUI
sandbox workflow call took 18.85 seconds, including approximately 3.51 seconds
for motion model loading, inference and export (single runs, not performance
benchmarks). Outputs include `motion.npz`, `motion.bvh`, metadata, and optional
`preview.gif` / `preview.mp4`. NPZ coordinates are in meters; the preview follows
the root horizontally to keep the character visible. This is a skeleton preview,
not a skinned character render.

Validation includes a tiny same-code LLM2Vec/LoRA fixture: streamed FP32 differs
from ordinary MPS by at most 2.38e-7 and BF16 matches exactly. An official trained
Kimodo root-stage transformer matches CPU within a maximum absolute error of
2.56e-6. These tests do not claim an in-memory 8B CPU comparison. Combined tests:
156 total, 144 passed and 12 skipped, with real motion/video/TRELLIS MPS enabled.

For debugging, use `--stage encode`, `--stage motion`, or `--stage check`.
Motion-only execution verifies that `text.pt` belongs to the requested prompt.
Only the SOMA-RP-v1.1 short text-to-motion path is verified on Mac; G1, constraints,
multiple prompts and native motion correction are not claimed as validated.
The MPS node currently handles one prompt/sample and disables native correction;
foot sliding/contact cleanup may still be needed for production animation.

## Windows AMDGPU setup

From the repository root, after the normal `yarn` installation:

```powershell
powershell -ExecutionPolicy Bypass -File extensions/Motion/install_kimodo.ps1
```

The installer creates `.venv/kimodo`, installs the official Kimodo source at a
pinned commit, and reuses `.venv/Lib/site-packages` for PyTorch/ROCm. It skips
the optional native `motion_correction` postprocessor; text-to-motion generation
and NPZ/BVH export remain available.

Kimodo's text encoder uses the gated
`meta-llama/Meta-Llama-3-8B-Instruct` model. Request access on Hugging Face, then
authenticate inside the child environment:

```powershell
.venv\kimodo\Scripts\hf.exe auth login
```

If Meta access is still pending, a compatible community snapshot may be used
temporarily by setting `SSUI_KIMODO_TEXT_ENCODER_BASE` to its downloaded local
snapshot directory. The tested fallback is
`raducius/Llama-3-8B-Instruct-LLM2Vec-mntp-merged` at revision
`01417d622e8a85d6f4b308dac0e37d478a9a87d1`. It is a community artifact under
the Llama 3 license, not an NVIDIA-supported Kimodo dependency. Unset the
variable to return to the official gated encoder.

Generated files are written under the project `output/` directory. Set
`SSUI_KIMODO_PYTHON` to use a different Kimodo interpreter. For cards with less
than 16 GB VRAM, select `cpu` for `text_encoder_device`; the Kimodo denoiser will
still run on the GPU.

The bundled node exposes the SOMA and Unitree G1 checkpoints. SMPL-X needs the
additional upstream SMPL-X/SOMA setup and is intentionally not offered by the
default Windows installer.

## Workflow node

```python
from ssui import Prompt
from ssui.config import SSUIConfig
from ssui_motion.Kimodo import KimodoTextToMotion

config = SSUIConfig()
motion_path = KimodoTextToMotion(
    config("Kimodo Text To Motion"),
    Prompt("A person walks forward and waves."),
)
```

## Blender preview

The generated SOMA BVH can be turned into a rendered skeleton preview with the
bundled Blender script:

```powershell
blender --background --factory-startup `
  --python extensions/Motion/render_bvh_blender.py -- `
  --input output/motion.bvh --output-dir output/blender_preview `
  --ffmpeg path/to/ffmpeg
```

The script converts Kimodo's centimeter BVH units to meters and produces a PNG
preview, an H.264 MP4 animation, and an editable `.blend` scene.

## Video pose recognition

The pose workflow extracts MediaPipe Pose's 33 landmarks from a single-person
video and returns:

- a `Video` with a skeleton overlay for visual quality checks;
- a `SkeletonAnimation` containing timestamps, normalized image coordinates,
  relative 3D/world coordinates, and landmark confidence;
- JSON, BVH, and retarget reports written by the executor.

```python
from ssui import SkeletonAnimation, Video, workflow
from ssui_motion import PoseRecognitionOptions, recognize_pose

@workflow
def video_to_skeleton(video: Video) -> tuple[Video, SkeletonAnimation]:
    options = PoseRecognitionOptions(sample_fps=24, smoothing=0.45)
    return recognize_pose(video, options)
```

See `examples/advance/workflow-pose.py` for the complete node workflow. The
node editor exposes sampling FPS, smoothing, detection/tracking confidence,
missing-frame interpolation, and local MediaPipe model path controls.

MediaPipe Solutions Pose uses its bundled model. MediaPipe Tasks downloads the
official `pose_landmarker_full.task` once into `~/.cache/ssui/mediapipe/`. Set
`SSUI_MODEL_CACHE`, or pass `PoseRecognitionOptions(model_path=...)`, for an
offline model.

## BVH and Blender comparison

Skeleton results are exported as a 21-joint humanoid BVH with fixed median bone
lengths, local XYZ rotations, continuous Euler angles, and a `.retarget.json`
forward-kinematics error report. The `video_to_blender_comparison` workflow also
creates a `.blend` scene, comparison frames/video, and a Blender-side numeric
report.

To run the complete video-to-Blender pipeline from a script:

```powershell
./extensions/Motion/blender/video_to_blender.ps1 `
  -Video D:/videos/person.mp4 `
  -OutputDir output/person-motion
```

The script uses a normal Blender executable when available and falls back to
the official Microsoft Store/MSIX launcher without desktop automation. Use
`-SkipBlender` to perform recognition and BVH export only.

MediaPipe monocular world coordinates are hip-relative and cannot recover true
global translation. The extension estimates camera-plane root motion from the
hip trajectory; robust depth translation, foot locking, and skinned-character
retargeting require additional constraints.
