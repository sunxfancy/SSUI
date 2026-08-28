# Motion extension

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
