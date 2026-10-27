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
