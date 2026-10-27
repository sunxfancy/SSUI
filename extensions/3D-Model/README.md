# SSUI 3D Model extension

## AMD / Pixal3D status

The AMD path is Pixal3D. Use `examples/advance/workflow-pixal3d.py` to
avoid importing unrelated image-generation workflows. Legacy TRELLIS currently
requires CUDA-only native dependencies and reports this explicitly on ROCm.

Windows ROCm uses Transformers 4.57.6 / Tokenizers 0.22.2 for DINOv3 and
compatibility with PyTorch builds without distributed support. Pixal3D defaults
to PyTorch SDPA on ROCm. Windows ROCm also defaults to FlexGEMM `explicit_gemm`,
which uses GPU PyTorch operations instead of the incompatible Triton autotuner.
This can consume more memory than the fused algorithm. Explicit `ATTN_BACKEND`,
`SPARSE_ATTN_BACKEND` and `FLEX_GEMM_ALGO` settings take precedence.
Windows ROCm inference chunks explicit-GEMM im2col into at most 64 MiB blocks
and 65,536 rows to avoid multi-GB temporary allocations and tall-GEMM corruption.
Sparse linear layers and decoder ConvNeXt MLPs also process at most 65,536 rows
per inference call. Training retains the upstream path.
The four sequential condition extractors share one frozen DINOv3 backbone,
while retaining separate projection grids, avoiding three duplicate weight copies.
Windows ROCm with `low_vram=True` also loads main models on demand and discards
their storage after each stage, reloading reused decoders from the local cache.
Checkpoint loading initializes empty parameters and assigns tensors individually
in the model's configured dtype, avoiding full random FP32 initialization and
CPU offload copies. This trades additional local disk reads for lower host RAM.

Run `yarn probe:3d --output test-artifacts/amd-3d-probe.json` before downloading
weights. It runs real dense/sparse attention, compares sparse convolution with
dense convolution, reads a CuMesh triangle, and rasterizes a triangle through
the native nvdiffrast plugin. Import success alone is not a GPU test. This
command returns a nonzero status if any stage fails and does not download models.
Use `yarn test:3d` for the CPU-compatible adapter/configuration regression tests.

Verified on 2026-10-27 with Radeon AI PRO R9700 (gfx1201), Windows, PyTorch
2.9.1+rocm7.2.1: pipeline import, attention, convolution, CuMesh readback and
rasterization pass after installing the locally built nvdiffrast ROCm wheel.
The native probe additionally passes interpolation, antialiasing gradients and
bilinear texture sampling/gradients at triangle resolutions 16, 64 and 256.
**Full image-to-textured-GLB generation passed on this configuration.** The pinned
nvdiffrast 0.3.3.1 Windows wheel still fails to load its native plugin; use the
local build below. Pixal3D fails before loading weights if the runtime check fails.
The retained RGBA building-image run completed all four sampling stages with
12 steps each, 1024 geometry resolution, mesh decoding, UV unwrapping and 4096
texture export. The repaired output restores the roof, walls, windows, entrance,
awning and base; the earlier missing-building/floating-fragment result was
caused by runtime corruption, not the 30-degree camera setting. The same seed
(42), camera and sampling settings were retained. This validates this
manual-camera single-image path on this
machine, not every input or the automatic-camera/background-removal paths.
Earlier attempts hit host allocation failures; stage loading, empty parameter
initialization and chunked convolution enabled the successful run. Final output
and log are `test-artifacts/pixal3d-final.glb` and `test-artifacts/pixal3d-final.log`.
The final run took 192.0 seconds and exported 38,421,528 bytes, 741,945 vertices,
934,960 triangles and 4096x4096 textures. Four GPU views and an independent
CPU geometry rendering were inspected; the building is complete in those views.
The AMD dependency profile still contains legacy CUDA wheels; those are not
evidence of compatibility. Installing CUDA is not a fix for the AMD export path.

`yarn probe:glb` additionally verifies CuMesh remeshing/UV unwrapping and a
textured GLB export/readback on a small procedural sphere. Its sparse sampler
is compared with normalized dense PyTorch interpolation, including missing
voxels, out-of-bounds coordinates, batches and chunk boundaries. Windows ROCm
export uses native HIP neighbor lookup plus chunked PyTorch reduction because
the installed Triton HIP driver expects Linux runtime discovery.
Windows ROCm checkpoint loading streams tensors through safetensors 0.8's
`pread` backend; its mmap storage path access-violated during full model loading
on the tested runtime.

Remaining validation includes additional inputs and GPU architectures. Automatic camera
estimation additionally requires MoGe-2; disable `auto_camera` to use a manual
field of view when MoGe is unavailable. The opt-in real-model test is gated by
`SSUI_RUN_MODEL_TESTS=1`; normal adapter tests do not certify generation quality.

Run `yarn run:pixal3d path/to/input.png --output test-artifacts/pixal3d.glb`
for retained real-model output (downloads required weights; manual 30-degree
camera, 1024 cascade). RGBA foreground masks are preserved and skip background
removal. RGB inputs require access to the configured RMBG model. If a stale
Hugging Face token blocks public downloads, use `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`
for that run; gated models still require valid authorized credentials.

### Build nvdiffrast for Windows ROCm / gfx1201

Requires the project's Python 3.12 Windows ROCm environment, ROCm SDK core/devel,
Visual Studio C++ build tools, Git, setuptools, wheel and ninja. From the repo root:

```powershell
yarn prepare:nvdiffrast-rocm
yarn build:nvdiffrast-rocm
.venv/Scripts/python.exe -m pip install --no-deps --force-reinstall .build/nvdiffrast-repro/source/dist/nvdiffrast-0.4.0+ssui.rocm72-cp312-cp312-win_amd64.whl
yarn probe:nvdiffrast --output test-artifacts/nvdiffrast-rocm-probe.json
yarn probe:3d --output test-artifacts/amd-3d-probe.json
```

Preparation refuses to overwrite existing source checkouts. For a new build use
`--directory` on the prepare command, then pass matching `-Source` and
`-DevelInclude` paths to the build command. The default build folder is ignored
by Git. Published wheels and SHA256 checksums are available in the
[ROCm wheel release](https://github.com/sunxfancy/SSUI/releases/tag/rocm-wheels-20261027).
The Windows AMD dependency profile pins these artifacts, including NATTEN and CuMesh.

Sources are pinned in `dependencies/prepare_nvdiffrast_rocm.py`: NVIDIA nvdiffrast
`253ac4f`, plus selected source patches from
[Painter3000's ROCm port](https://github.com/Painter3000/amd-nvdiffrast-rocm72-gfx1201/tree/7ad5076e27bf2722f8f19c9f6a2bb42021f00b70).
The script enumerates the applied patches; this is not the complete v52 stack.
Windows HIP binding compilation follows the approach in
[CuMesh.rocm72](https://github.com/sunxfancy/CuMesh.rocm72/tree/bb2ed49f4170a267ecb90c41b48daab1ddce7830).
Additional adaptations compile host bindings through HIP and fix `.inl` includes
that PyTorch hipify does not rewrite. Only gfx1201 is currently accepted by the
build script; other architectures remain untested.

### Large-mesh correctness on Windows ROCm

Two independent silent failures were reproduced on the tested runtime:

- CuMesh's narrow-pitch `hipMemcpy2D` transfers truncated beyond 1,048,576 rows.
  A 5,000,000-vertex/7,000,000-face round trip corrupted 3,951,424 vertex rows
  and 5,951,424 face rows. The source patch bounds each transfer to 65,536 rows.
- Tall `F.linear` calls produced incorrect values after row 524,288 (FP32)
  or 1,048,576 (FP16/BF16) in the 2,000,000-by-32 to 7-channel reproduction.
  Sparse linear/MLP inference now bounds each call; original dtypes and weights
  are preserved. `yarn probe:large-sparse` checks all three precisions against
  exact constants and independent CPU references, including boundary rows.

The startup runtime check rejects a CuMesh build that corrupts a 1,048,577-row
round trip before loading weights. Rebuild and install the patched wheel:

```powershell
yarn prepare:cumesh-rocm
yarn build:cumesh-rocm
.venv/Scripts/python.exe -m pip install --no-deps --force-reinstall .build/cumesh-rocm/source/dist/cumesh-0.0.1+ssui.rocm72-cp312-cp312-win_amd64.whl
yarn probe:cumesh
yarn probe:large-sparse
```

The preparation script pins the existing CuMesh ROCm port and Eigen source,
then applies `dependencies/patches/cumesh-rocm.patch`. A fresh preparation and
wheel build were verified. The Windows AMD lock pins this repaired wheel with a SHA256 checksum.

For future CUDA-to-ROCm ports, validate native arithmetic and memory transfers
at production sizes and boundary sizes, not only imports or tiny meshes.
Retain pre/post-processing geometry and compare with an independent CPU
reference before changing camera or model settings to compensate for corruption.

### NAF / NATTEN on Windows ROCm

The local NATTEN port uses version 0.17.4 at `c198e15`, without CUTLASS.
The gfx1201 native 2D QK/AV forward and backward operators pass comparison with
a direct PyTorch reference for 9x9 neighborhoods at dilation 1 and 2 (FP32).
This does not certify every NATTEN dtype, dimension or optimized backend.

```powershell
yarn prepare:natten-rocm
yarn build:natten-rocm
.venv/Scripts/python.exe -m pip install --no-deps --force-reinstall .build/natten-rocm/source/dist/natten-0.17.4+ssui.rocm72-cp312-cp312-win_amd64.whl
yarn probe:natten
```

If GitHub API rate limits prevent torch.hub from loading NAF, clone the official
`https://github.com/valeoai/NAF.git` repository and set `PIXAL3D_NAF_SOURCE` to
that local checkout. The tested source revision is
`37f2dfc180f2de53d98bd601109c0da0dd6b0f43`. NAF still downloads its pretrained
checkpoint on first use. `HF_HUB_DISABLE_XET=1` selects standard HTTP if Xet
downloads stall. These environment settings apply only when explicitly selected.

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

## Mac 图像转网格

新增 `TripoSRModel` / `TripoSRImageToMesh`，以及
`examples/advance/workflow-3d-mac.py` 中的 `img2mesh_mac` 工作流。
准备参数阶段不加载模型。实际执行使用 MPS/CPU/CUDA 自动选择、float32 推理，
CPU scikit-image 提取网格，输出带顶点颜色的 SSUI `Mesh`。

## 运行

在仓库根目录运行（脚本定义见根 package.json）：

```bash
yarn install-requirements
yarn test:3d:smoke --download-only
yarn test:3d:smoke --local-files-only --device mps
```

下载约 1.7GB 的官方 TripoSR 权重，固定版本并校验 SHA-256；DINO 只额外下载配置，
其参数已包含在 TripoSR 权重内。默认使用官方椅子示例，64³ 网格采样，
实际经过 SSUI 沙盒工作流执行，并重新载入 GLB 检查几何和颜色。

可使用 `--image /绝对路径/input.png` 指定图片，`--resolution 96` 增加网格细节。
优先输入透明背景 PNG；脚本会居中缩放主体并合成灰色背景。
RGB 输入应事先去除复杂背景，此入口不会自动下载背景分割模型。

输出位于 `output/3d-mac/`：`mesh.glb`、三视角 `preview.png`、`report.json`。
已在 16GB Apple Silicon / Torch 2.4.1 上完成真实权重验证，椅子能辨认座面、靠背和腿。
64³ 采样的表面较粗，单张图片不可见部分由模型推断；不保证任意输入均产生闭合网格。

## 支持边界

- TripoSR 与下述 TRELLIS MPS 路径分别验证；各自使用原始真实权重。
- 当前导出顶点颜色，不做 UV 纹理烘焙，不依赖 torchmcubes、xatlas 或 CUDA 光栅化。
- Torch 2.4 MPS 不支持 DINO 的双三次插值，因此仅小型位置编码表转到 CPU 插值。
- 上游版本、许可证及补丁说明位于 `vendor/tsr/SSUI_PATCHES.md`。

验证：`SSUI_RUN_3D_RUNTIME_TESTS=1 yarn test_on mesh_runtime_test`。

## TRELLIS MPS 移植

已新增官方 `microsoft/TRELLIS-image-large` 的 MPS 稀疏后端，入口为
`examples/advance/workflow-trellis-mac.py` 的 `img2mesh_trellis`。与 TripoSR 是独立模型。

```bash
yarn test:trellis:smoke --download-only
yarn test:trellis:smoke --workflow --output output/trellis-mac-workflow
```

总权重约 3.9GB，固定 TRELLIS 版本并校验四份模型及官方 DINOv2 register-4 权重的 SHA-256。
默认每阶段 8 步，用于低成本验证。单独调试可用 `--stage encode|structure|slat|mesh`，
中间结果保存在输出目录；改变图片或采样参数后必须从相应上游阶段重新生成。
`--model-dir` / `SSUI_TRELLIS_MODEL_DIR` 可指定同一官方模型的本地目录。

图像编码、稀疏结构采样、SLAT、网格解码和 FlexiCubes 数值运算在 GPU 上进行；
整数邻接映射使用自定义 Metal 内核，坐标/边去重和计数在 MPS 上完成；CPU 仅读取少量尺寸元数据。首次运行需 Xcode 编译工具和 ninja。小窗口注意力合批，长序列按查询分块，
各阶段释放模型，避免全模型持续驻留。首次实测生成 228,766 顶点、455,764 三角面的椅子；
原始网格并非闭合，局部有碎片/孔洞，不能当作已修复的生产模型。
当前导出顶点颜色 GLB，尚未移植 CUDA UV 烘焙、Gaussian/RF 渲染及所有实验分支。
更详细的支持边界见 `vendor/trellis/MPS_PORT.md`。

SSUI 沙盒工作流复测：两阶段各 8 步，节点执行约 176 秒，完整命令约 180 秒，
产物位于 `output/trellis-mac-workflow/mesh.glb`。全量回归 79 项：68 通过、11 跳过，
包括真实 MPS 稀疏卷积、完整小型 SLatFlow、合批注意力和 FlexiCubes 数值对比。
