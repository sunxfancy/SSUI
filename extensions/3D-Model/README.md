# SSUI 3D Model extension

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
