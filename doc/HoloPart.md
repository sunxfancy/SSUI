# HoloPart 部件补全

`examples/basic/workflow-holopart.py` 提供 P3-SAM 分割 → HoloPart 补全 →
独立 QuadriFlow 重拓扑，返回三阶段的 Mesh 预览和导出文件。
原有 `workflow-retopology.py` 不启用生成式补全。

HoloPart 接收分割后的部件场景，推断遮挡面和缺失几何，可能改变原始形状。
补全结果不等同于原始网格的精确保真修复，也不保证任意输入都闭合。
保留分割结果、补全 GLB、逐部件补全报告，以及 QuadriFlow 的四边面 OBJ、
GLB 和边界检查报告，便于逐阶段复核。

## 原生 Windows ROCm

模型推理要求 Windows ROCm PyTorch 和可用 HIP GPU，不提供静默 CPU 回退。
HoloPart 使用独立 Python 子进程，P3-SAM 推理结束后释放模型，避免两套权重同时占用显存。
不依赖 Blender，不启动 WSL。曲面提取使用源码编译的 `diso` HIP 内核；
FPS 和近邻使用源码编译的 `torch-cluster` HIP 内核，注意力使用 PyTorch GPU SDPA。
模型部件采样和 MeshLab 简化等网格预处理/后处理仍使用 CPU。

本次固定外部源码版本：

- HoloPart：`48dd632c9a7412e6688573bb4f153e0ade7e7325`，https://github.com/VAST-AI-Research/HoloPart
- torch-cluster：`e9a855c284b45edcbf0282cf70ac09bee0ce4e49`，https://github.com/rusty1s/pytorch_cluster
- diso：`9792ad928ccb09bdec938779651ee03e395758a6`，https://github.com/SarahWeiii/diso
- 官方权重：`VAST-AI/HoloPart`，revision `29cdb1417121842c4c4d59b9d283cc734f8c3aec`。

将三个仓库分别检出到 `.build/holopart/HoloPart`、`pytorch_cluster`、`diso`。
构建脚本将 C++ 绑定也交给 HIP clang 编译，保持 Windows ROCm PyTorch ABI 一致，
并让 PyTorch hipify 转换 CUDA 内核。补丁入口为 `scripts/prepare_holopart_rocm.py`。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_holopart_rocm.ps1 -RuntimeVenv C:/path/to/rocm-venv -DevelInclude C:/path/to/rocm-devel-headers
```

现有运行环境提供匹配的 ROCm SDK、开发头文件、PyTorch、diffusers、transformers、
omegaconf、einops、peft 和构建工具。隔离环境复用其只读包目录，新增包和 wheel 安装于
`.build/holopart/env`；不覆盖共享 CUDA/ROCm 包。上游旧的 NumPy 1.22.3 固定值不适用于
当前 Python 3.12，因此不直接安装其整个 requirements.txt。

下载官方权重到 `.build/holopart/weights`，运行时仅本地加载：

```powershell
.build/holopart/env/Scripts/python.exe scripts/download_holopart.py
```

该入口固定权重 revision 并检查三份 safetensors 的 SHA256；`--verify-only` 可离线复核。

在本机 `.ssui-dev.json` 或环境变量配置绝对路径：

```json
{
  "SSUI_HOLOPART_ROOT": "C:/SSUI/.build/holopart/HoloPart",
  "SSUI_HOLOPART_PYTHON": "C:/SSUI/.build/holopart/env/Scripts/python.exe",
  "SSUI_HOLOPART_WEIGHTS": "C:/SSUI/.build/holopart/weights"
}
```

P3-SAM 与 QuadriFlow 配置沿用 [Retopology.md](Retopology.md)。节点默认 50 步、
seed 42、octree depth 8，逐部件 batch 1。整场景先统一归一化，生成后恢复坐标，
避免单独归一化丢失部件相对位置；报告记录归一化参数。

原始生成保存在 `completed.glb`。`prepared.glb` 显式移除重复/非流形面、拆分奇异顶点，
并清理小于部件总面积 0.1% 或少于 8 面的生成碎片；如果总移除面积超过任一部件的
2.5%，任务失败并保留原始结果。`preparation.json` 记录实际损失和剩余边界。
准备阶段不封口。QuadriFlow 对保留的连通曲面分别求解，再恢复部件分组；
每曲面至少请求 32 个面，困难曲面最多采用三个固定面预算/seed 重试，记录每次结果。
这一可选路径关闭锐边约束并保留边界约束，原有重拓扑节点的设置保持不变。

`QuadRemeshCompleted` 随后显式闭合输出边界，逐部件保留原始 QuadriFlow 报告和网格。
已闭合部件保持原网格；开放部件先拆分奇异顶点，逐连通曲面执行 MeshLab 局部相交检查补洞。
不安全、零面积或近乎零体积的封盖被拒绝，改为保留原曲面的薄壳闭合：
原顶点沿单位法线向两侧各偏移部件对角线的 0.002%，边界连接成侧壁。
不删除失败曲面，不跨部件连接；薄壳代表闭合表面，不代表实心体重建。
开放部件的每个三角曲面以共享边中点细分为三个四边面，处理奇数边孔环并避免 T 接缝。
因此实际四边面数可能明显超过 QuadriFlow 的目标面预算。
最终 OBJ、float32 GLB 及 SSUI 序列化导出均检查闭合性、退化面和分组；`closure.json`
记录封盖面积、薄壳厚度、保留曲面数、修复前后边界和面数。
局部封盖检查不等于整个模型已通过全局自交检测。

## 验证

```powershell
yarn test_on holopart_test
yarn test:dev-config
.build/holopart/env/Scripts/python.exe tests/holopart_rocm_kernel_check.py
node dependencies/venv.cjs python scripts/validate_holopart.py --steps 50 --depth 8
```

最后一条复用已有真实 R9700 P3-SAM 分割产物，对全部 23 个部件补全、重拓扑和序列化。
GPU 算子数值检查包含 dense GPU 近邻参考、贪心 FPS 参考和球面 SDF 曲面提取。
本地证据位于 `output/holopart-rocm-validation/`，源码与权重、机器配置不纳入 Git。

### 2026-10-28 初版实测（闭合修复前）

原始模型 499,588 个三角面，复用之前原生 ROCm P3-SAM 的 23 部件分割。
R9700 上 HoloPart 50 步、depth 8 完成全部 23 部件约 504 秒，峰值显存约 4.70 GiB。
原始生成仅 4/23 个部件被判定为 watertight，不能把生成完成等同于闭合修复成功。
准备阶段单部件移除面积最大约 1.75%，原始生成文件完整保留。
组件重拓扑及导出约 7–8 秒，最终 23 个部件、4,597 个四边面，
实际 GLB 退化三角面 0、非流形边 0，仍有 288 条开放边界，200 条按近似距离检查需复核。
表面采样近邻距离 P95 相对原模型约 2.78% 包围盒对角线；生成补全改变了原始形状。

独立浏览器验收页面使用真实 UploadLoader / MeshArtifact 组件及 SSUI 上传/文件路由，
验证四阶段预览、旋转、部件选择、缩放及 8 个文件的实际下载 SHA256，未覆盖完整 Tauri 桌面自动化。
证据包括 `pipeline-browser.png`、`browser-validation.json`、`geometry-validation.json`、
`verification.json`，以及 `browser-downloads/` 内的原始补全、准备网格、OBJ、GLB 和报告。
`--completed-job <任务目录>` 可复用已完成的真实 GPU 补全，单独重跑后续重拓扑与导出。

### 边界闭合验证

对初版同一批原始 QuadriFlow 输出验证：288 条开放边界降到 0，23 个部件名称与分组
全部保留，退化三角面和非流形边为 0；四边面从 4,597 增至 17,288。
原始输出与之前验收证据保留在 `output/holopart-rocm-validation/`。
新一轮完整 ROCm 补全、重拓扑、闭合和浏览器导出证据保存到
`output/holopart-closed-validation/`。

完整重跑复用原 P3-SAM GPU 分割，但重新执行 HoloPart 50 步、depth 8，
用时约 487 秒，R9700 峰值显存约 4.69 GiB；重拓扑、闭合及导出约 8.6 秒。
本批次原始 QuadriFlow 有 262 条边界，闭合后为 0，输出 16,289 个四边面。
23/23 个 GLB 部件及 SSUI 序列化副本均为 watertight，非流形边、退化三角面为 0。
其中 17 个已闭合部件的坐标和四边面索引逐项未变，6 个部件加密，9 个曲面使用薄壳。
相对本轮闭合前输出的采样距离 P95 约 0.66% 包围盒对角线；相对原始输入模型约 3.78%。
两者都是独立表面点近邻近似值，不能当作精确 Hausdorff 距离。
上游条件点采样使用未固定的 NumPy generator，相同扩散 seed 不保证相同生成网格，
因此原批次 288→0 与完整重跑 262→0 分开记录。

新版浏览器验收通过四阶段预览、原生上传、旋转、部件选择、缩放和 9 个导出文件的
独立 SHA256 校验。`closure-comparison.json` 记录分组保持和已闭合部件不变的独立复核。
补洞回归覆盖已闭合网格不变、普通孔洞、奇数边孔环、有界薄片厚度、奇异接触点拆分、
非流形拒绝和 23 分组实际 GLB 导出。在含 MeshLab 的隔离环境执行：

```powershell
$env:SSUI_VENV_PATH = (Resolve-Path .build/holopart/env).Path
yarn test_on holopart_closure_test
```

## 许可证

HoloPart 代码和官方权重标注 MIT，torch-cluster 为 MIT。
**diso 为 CC BY-NC 4.0，存在非商业使用限制**；因此不能把整条依赖链笼统称为 MIT，
商用需另行解决该依赖的许可或替换曲面提取实现。本 PR 不分发第三方源码、权重或编译二进制。
参见各固定源码仓库的 LICENSE，以及 https://huggingface.co/VAST-AI/HoloPart 。
