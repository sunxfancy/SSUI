# SSUI 3D Model extension

## TRELLIS and TRELLIS.2 GPU workflows

Use `examples/advance/workflow-trellis.py` for the original TRELLIS model, or
`examples/advance/workflow-trellis2.py` for TRELLIS.2. Both expose model and image
inputs, defer weights until execution, and return a GLB through the Mesh output.
Use an RGBA object PNG to supply a foreground mask without an additional
background-removal model.

On Windows ARM64, TRELLIS defaults to the official mesh decoder's vertex colors.
Other platforms retain the existing Gaussian-texture default. Its optional
`gaussian_texture` mode retains the older Gaussian-rendering/UV-baking path and
needs its additional native dependencies. TRELLIS.2 also defaults to vertex colors;
its optional `pbr_texture` mode offers texture-size and remeshing controls, but
still has visual-quality/performance issues on the tested Windows ARM64 build.

See [TRELLIS GPU validation](../../doc/TrellisGpu.md) for the native Windows ARM64
CUDA environment, commands, results and remaining limitations.

## Pixal3D GPU image-to-3D

Open `examples/advance/workflow-pixal3d.py`, enter the local Pixal3D snapshot path
in the model input, and choose `ImageUploader` for an object PNG with a foreground
alpha mask. The workflow returns a textured GLB through the standard Mesh output.
Model loading happens during execution, so preparing the workflow does not download
or initialize model weights.

The Windows ARM64 CUDA development setup, operator checks, real-model acceptance
command, and auxiliary model access requirements are documented in
[Pixal3D GPU](../../doc/Pixal3DGpu.md).

## WorldClaw-compatible scene generation

WorldClaw is an agentic scene-construction framework, not a released model
checkpoint. SSUI exposes its stable workflow boundary as `WorldClawModel` and
`GenWorldClawScene`: prompt/specification, region-aware terrain, editable object
instances, and a standard GLB-exportable `Mesh` result.

The default mode is offline and deterministic, intended for fast game-level
blockouts:

```python
from ssui import Mesh, Prompt, workflow
from ssui.config import SSUIConfig
from ssui_3dmodel.WorldClaw import WorldClawModel, GenWorldClawScene

config = SSUIConfig()

@workflow
def build_game_world(prompt: Prompt) -> Mesh:
    return GenWorldClawScene(
        config("Generate WorldClaw Scene"),
        WorldClawModel.load(),
        prompt,
    )
```

For an agentic planner, set `SSUI_WORLDCLAW_PLANNER_URL`. The endpoint receives:

```json
{"prompt": "a snowy mountain village", "seed": 42}
```

It may return a world-spec object directly or under a top-level `spec` field.
Set `SSUI_WORLDCLAW_API_KEY` to add a Bearer token. Unsupported or missing fields
are repaired conservatively before scene construction. The resulting GLB keeps
terrain and each generated instance under separate names such as `terrain` and
`asset.house.000`, so a game editor can select, replace, or remove them.

The adapter is intentionally not presented as Tencent's unreleased reference
implementation. Its public workflow signature can remain stable when an official
runtime or compatible planner endpoint becomes available.
