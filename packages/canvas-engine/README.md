# SSUI Canvas Engine

Rust + wgpu 26 drawing kernel, integrated into `extensions/Image/canvas` through
WASM. React owns editable layers and source pressure samples; Rust retains a
render projection and disposable GPU caches. Konva handles image transforms,
pointer input and stroke control handles, not document painting.

## Build and run

Install Rust, then run `yarn workspace @ssui/canvas-engine setup` once to install
the WASM target and pinned wasm-pack tool. Build shared components with
`yarn build:components` on a clean checkout. `yarn dev:canvas` starts the editor
at `http://localhost:7420/extension/ImageExtension/canvas/`; its predev/prebuild
scripts compile WASM automatically.

- `yarn build:canvas-engine`: optimized WASM, ES module and TypeScript bindings in `pkg/`.
- `yarn build:canvas`: complete TypeScript/Vite Image editor build, including WASM.
- `yarn test:canvas-engine`: portable document and incremental-projection tests.
- `yarn workspace @ssui/canvas-engine test:gpu`: actual native GPU pixel readback;
  explicitly enabled because headless CI may have no GPU. Uses Vulkan on Windows.
- `yarn workspace ssui-image test --runInBand`: editor geometry/picking tests.
- Inside this package, `yarn check:wasm` and `yarn format` check target compatibility/style.

This package is independent of Tauri. `yarn build:wasm` emits raw release WASM;
browser bindings require the normal `build` command. Generated files are ignored
and included in the Image Vite bundle, not committed as binaries.

Native Windows ARM64 builds skip wasm-pack's optional `wasm-opt` pass because
its binary downloader does not support that host. Rust release optimization
still runs. Building wasm-pack/wasm-bindgen from source on this host also needs
MSVC ARM64 build tools and `clang` on PATH (including ring's assembly step).

## Editor controls

Import a bitmap with **导入图片**, draw with **画笔**, and erase with **橡皮擦**.
Each eraser gesture is a retained object in its own layer, so deleting it restores
the underlying content. Use **编辑笔触** to click a line or choose a stroke/eraser
from **笔触列表**. New gestures fit to cubic Bezier segments on pointer-up. White
anchors move the curve and attached handles; purple handles adjust curvature.
Each drag is one undo step. The action bar changes width/color, smooths, refits or
deletes the stroke. Legacy polylines remain supported and expose sample handles
until converted with **贝塞尔拟合**.

Geometry and pressure compress independently. Packed anchors store
`[x,y,inX,inY,outX,outY,t]`; pressure stores `[t,value]` knots. `t` is a normalized
source chord/arc parameter. Pressure stays attached to that parameter during edits.
Endpoint-tangent least-squares fitting splits at large paired-sample and interval
midpoint errors. Default tolerance is 0.5 document units, tightened for drawing
zoom/DPR; sparse corners retain straight segments when needed. Pressure has maximum
sampled approximation error `min(0.01,0.25/brushWidth)`; stationary taps retain maximum
pressure. This is approximate compression, not lossless input-event retention.
Fitting removes the dense point array; the original sample count is metadata only.

The brush properties selector offers pen, marker, watercolor and pencil alongside
the normal, airbrush and grain brushes. Pen responds strongly to pressure; marker
has flat ends and translucent overlap; watercolor uses pooled pigment and soft
paper edges; pencil uses fine graphite grain. Selecting a preset sets its initial
width. Selected strokes can change brush type without losing curve/pressure data.

Undo/redo use Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z (also Ctrl/Cmd+Y). Delete/Backspace
deletes the selected object. Keyboard actions leave form inputs alone. Image drag,
point drag and a drawing gesture each form one undo step. Image movement retains
the existing grid snap. Middle-button dragging pans; the wheel zooms.
Hidden/locked/zero-opacity layers cannot be picked with the stroke tool.

## Rendering contract

- Layer and object IDs are unique. Layers are ordered bottom to top, objects in
  replay order. Source points and widths are document units. Image rotation is
  clockwise degrees about its top-left corner.
- Normal pressure strokes use lyon tessellation and cached GPU vertex/index buffers.
- Cubics go directly to lyon's Bezier path builder, split at pressure knots so
  intermediate pressure peaks survive. Coverage/picking use temporary adaptive
  approximations. Dense polylines are not retained beside the canonical curve.
  Fingerprints include handles and pressure, invalidating edited tiles/meshes.
- Each layer owns sparse 256x256 physical-pixel RGBA8 cache tiles, shared by all
  strokes touching the same tile. Coverage follows individual pressure-aware
  segments, including long diagonals, rather than the stroke bounding rectangle.
  Only visible occupied tiles are allocated; deleting/moving/hiding strokes or
  moving the camera prunes old tiles and offscreen meshes. Eraser-only regions
  allocate nothing. Source vectors reconstruct tiles when they return to view.
  Tile coverage is conservative (including caps, feather and a two-pixel gutter),
  not an exact nonzero-alpha pixel mask; fully erased touched tiles can remain
  until their source objects leave that region.
- Ordered destination-out
  erasing affects earlier images/strokes in that layer, never layers below it.
- One shared 260x260 4x MSAA scratch attachment resolves dirty tiles, irrespective
  of viewport size and layer count. Composition excludes gutters, so tile seams
  do not double-apply opacity. Fingerprints include geometry, brush and camera.
- Packed RGBA8 mesh colors and 16-bit indices where possible reduce mesh payloads.
  Tile-coverage metadata is cached between camera/geometry changes. All user layers
  share a fixed pair of Konva overlay layers instead of viewport canvases per layer.
  Unused fallback and image-upload scratch canvases release their large backing stores.
- Premultiplied source-over composition applies layer opacity once to RGBA. Imported
  images use straight RGBA uploads and source-over blending within the layer.
- The JS adapter sends geometry only for layers whose immutable object array changed.
  Visibility, opacity, reorder and camera changes reuse the retained projection.
  Failed projection validation does not replace the previous scene.
- CSS colors and transforms are converted explicitly. All brush types, including
  feather, airbrush and grain, use procedural GPU shading of pressure-aware meshes.
  There are no per-stroke bitmap textures or persistent stamp canvases. Paper grain
  uses stable document coordinates and a per-stroke seed, continuous across tiles.
  Canvas2D fallback uses bounded shared 128x128 paper patterns and a reusable layer
  scratch canvas. Imported bitmaps retain their original source texture resources.
- World coordinates map to physical pixels with device pixel ratio applied once;
  pointer events transform back to document space. Coalesced pen samples and pointer
  capture preserve drawing gestures.
- React history retains up to 64 structurally shared layer snapshots. The separate
  `Engine` document API remains available to native consumers; the editor does not
  maintain a second independently editable Rust document.
  Explicit conversion retains old points in undo history until eviction; automatic
  pointer-up fitting adds no raw-stroke undo snapshot. Complex scribbles or noisy
  pressure may require many segments/knots.

WebGPU requires a compatible browser and secure context. The action bar reports
the actual backend. Initialization, upload/render errors or unavailable WebGPU
fall back to isolated-layer Canvas2D painting without dropping source data. Lost
surfaces are reconfigured once; device errors trigger fallback on the next draw.

## Browser regression and performance evidence

Install Python `playwright` and `pillow`, and use an installed Edge browser. With
`yarn dev:canvas` running, execute `python scripts/test_canvas_browser.py`.

The script uses real headless Edge (`--channel` overrides the installed browser),
uses ordinary WebGPU without override flags by default, reports the actual adapter, and saves
screenshots and `results.json` under `test-artifacts/canvas/`. Only the unrelated AI
script-list endpoint is mocked; painting is real WASM/WebGPU. Assertions use
browser-composited screenshot pixels, not a synthetic renderer.

Coverage includes imported images, opacity, eraser isolation and deletion/replay,
stroke picking, point drag, style edits, smoothing, undo/redo, locks, visibility and
Canvas2D fallback, high-DPI resize, image movement, zoom and panning. Benchmarks use
1280x720, four layers, four 512x512 images, 100/1000
strokes and 64 pressure samples per stroke. Each case measures 30 frames after five
warmups: cached composition, editing one stroke and camera movement. Timings include
the actual SceneAdapter, incremental serialization, WASM and a GPU completion fence;
they exclude React input handling and are not an end-to-end input latency or FPS claim.
Cold timings include image upload and initial mesh construction. Use current results,
not a cross-machine performance promise.

Pass `--skip-benchmark --url <production-preview-url>` to run the interaction/pixel
suite against a built Vite preview. The optional `--unsafe-webgpu` flag is only for
test hosts where the browser blocks WebGPU; its use is recorded in the results.

Run `python scripts/test_canvas_brushes.py` against the dev server for brush
appearance, retained editing, sparse memory accounting and reclamation checks.
Screenshots/results go to `test-artifacts/canvas-brushes/`. It verifies that 100
overlapping strokes share one tile, a 4096-square diagonal does not allocate its
whole rectangle, and offscreen/deleted content releases its render cache. Native
GPU tests also read back both sides of tile boundaries to check seamless opacity.

The action bar reports tile count and requested GPU cache payload bytes: RGBA tiles,
shared MSAA, mesh/uniform buffers and image textures. This is not process RSS or
total GPU allocation: output surfaces, driver/bind-group allocation overhead and
CPU/JS source/history are excluded. The old 4096x4096 single-layer viewport-cache
budget was 320 MiB (64 MiB layer + 256 MiB MSAA); the sparse short-stroke test uses
one tile and about 1.29 MiB including its shared MSAA scratch and mesh.

`python scripts/test_canvas_bezier.py` tests handle dragging/undo in real Edge,
compares serialized source geometry and GPU mesh buffers, and checks rendered
pressure peaks before/after edits. Evidence goes to `test-artifacts/canvas-bezier/`.
One 4001-point smooth fixture fits to seven anchors and five pressure knots; this
is not a universal compression ratio. JSON bytes do not measure total CPU heap.

## Remaining scope

This implements the requested painting/editor slice, not full Photoshop parity.
PSD import, selection masks, blend modes beyond normal/erase, color management,
Document persistence and flattened image export remain separate work.
Dense full-viewport painting still needs tiles over its full coverage. Cold loads
construct meshes for visible strokes; repeated camera movement rebuilds visible
coverage. Curve/pressure data and up to 64 undo snapshots still consume CPU
memory, and imported image textures are not sparsified. Canvas2D fallback retains
one viewport layer scratch surface. Tablet-device compatibility and long-session
memory/performance have not been established.

API references: [wgpu](https://docs.rs/wgpu/26.0.1/wgpu/),
[lyon](https://docs.rs/lyon_tessellation/1.0.22/lyon_tessellation/).
