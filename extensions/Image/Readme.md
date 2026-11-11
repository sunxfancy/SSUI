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


## FLUX.2 Klein LoRA

FLUX.2 Klein 模型面板支持可选本地 LoRA 文件与权重，参数会随面板状态保存。
Python 调用为 `Flux2KleinModel.load(model_path, lora_path="adapter.safetensors", lora_weight=0.8)`。
留空或权重为 0 时沿用基础模型；非零适配器使用独立 Pipeline，不修改缓存的基础模型。
适配器由 Diffusers 的 FLUX.2 加载器处理，必须匹配 Klein 的架构与版本，不能直接使用 FLUX.1 LoRA。
当前入口接收一个本地权重文件，不提供训练。预训练模型搭配真实适配器的图像质量尚需单独验证。
