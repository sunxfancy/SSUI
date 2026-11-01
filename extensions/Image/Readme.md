This is an example project for custom modules.

## Editable Canvas

Canvas uses the Rust/WASM WebGPU kernel in `packages/canvas-engine` for isolated
layer composition, bitmap textures and retained eraser strokes. The toolbar shows
the actual renderer and falls back to Canvas2D when WebGPU is unavailable.
Choose **编辑笔触** to pick a line, drag its sample handles, change width/color,
smooth or delete it. **笔触列表** also selects eraser records; deleting one restores
content. Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z undo/redo edits.

Brush presets include **钢笔、马克笔、水彩笔、铅笔**. All GPU brushes retain editable
pressure points rather than per-line images. A user's layer shares sparse 256x256
cache tiles between strokes; only touched visible regions are cached, and old tiles
are reclaimed on deletion/movement. The toolbar displays tile count/cache payload.

New strokes automatically fit to cubic Bezier curves on pointer-up with an independent
compressed pressure profile. In **编辑笔触**, drag white anchors or purple handles to
correct a stroke; undo restores each drag. Existing polylines can use **贝塞尔拟合**.
Fitting removes dense source points from the current document; explicit conversion
remains undoable. The selected-stroke summary shows original count, anchors and
pressure knots. See `scripts/test_canvas_bezier.py` for compression/GPU validation.

Run `yarn workspace @ssui/canvas-engine setup` once, then `yarn build:components`
and `yarn dev:canvas`. See [kernel documentation](../../packages/canvas-engine/README.md)
for rendering contracts, browser verification and current limits.

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
