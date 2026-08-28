# Motion extension

The Motion extension provides both NVIDIA Kimodo text-to-motion generation and
MediaPipe video pose recognition with BVH/Blender reconstruction.

The Motion extension runs NVIDIA Kimodo in an isolated child environment. This
keeps Kimodo's pinned `transformers==5.1.0` dependency from replacing the
versions used by SSUI's Image and Video extensions, while reusing the project's
ROCm-enabled PyTorch installation.

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
