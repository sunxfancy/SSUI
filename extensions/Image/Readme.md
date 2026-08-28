This is an example project for custom modules.

## Pixel-art workflows

`ssui_image.PixelArt` provides two deterministic paths:

- `FinalizePixelArt` converts a generated image to an exact native grid,
  bounded palette, hard alpha, and optional nearest-neighbor preview scale.
- `AgentPaintAsset` / `RenderAgentPaint` validate and render `.apx` or a frame
  from `.apxa` using the external `agentpaint` CLI.
- `PixelSrcAsset` / `RenderPixelSrc` validate and render `.pxl` sources using
  the external `pxl` CLI, including animation spritesheet output.

The CLI adapters do not download or bundle third-party executables. Install the
chosen CLI on `PATH`, or pass its absolute executable path to the asset loader.
Commands are executed without a shell and source files are validated before
rendering.
