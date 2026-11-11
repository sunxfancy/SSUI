# 原生场景布局 backend

`backend/scenesmith.py` 在 SSUI 共享 Python 环境中运行，不使用 Docker、WSL 或 SceneSmith 服务。可选的本机 Qwen 规划器通过 Windows ARM64 CUDA Python 子进程运行模型；几何生成和场景导出仍在共享 backend 中完成。工作流入口是 `GenSceneSmithScene`，示例为 `examples/advance/workflow-scenesmith.py`。

## 使用

准备一个包含静态 GLB 的目录，并将节点的 `asset_dir` 指向它，或设置 `SSUI_SCENE_ASSETS`。相对目录层级去掉 `.glb` 后成为资产 ID，例如 `furniture/chair.glb` → `furniture/chair`。

默认文字模式按资产 ID、文件名或资产旁 `同名.json` 的 `category`/`tags` 匹配，再把匹配到的资产按固定间距摆成一行。资产元数据可含 `description`、`category`、`tags`，供本地模型选择。可设置 `planner_model` 为本地 Qwen2 模型目录，并设置 `SSUI_SCENE_PLANNER_PYTHON` 为 Windows ARM64 CUDA 虚拟环境的 Python；此时 backend 调用本机模型生成布局 JSON，再进行格式与资产校验、接地和静态 AABB 碰撞修正。明确的中英文“左/右/前/后/上”关系会作为硬约束校正模型坐标。这个规划器是 Windows ARM64 替代实现，**尚未达到 SceneSmith 上游的多代理空间推理与物理仿真**。

精确摆放时，将节点的 `spec_path` 指向以下 JSON（或设置 `SSUI_SCENE_SPEC`）：

```json
{
  "schema": "ssui.scene-layout/1",
  "objects": [
    {"id": "chair-1", "asset": "furniture/chair", "position": [1, 2, 0], "rotation_deg": 90, "scale": 1}
  ]
}
```

位置单位与资产的 GLB 单位相同；Z 为上，旋转绕 Z 轴。可选的 `room: {"size": [宽, 深, 高], "openings": [{"wall": "front", "kind": "door", "width": 1, "height": 2}]}` 会生成独立的地板与墙体，并在指定墙上留矩形门窗洞。对象可指定 `relation` 为 `floor`、`on`、`left_of`、`right_of`、`front_of`、`behind`、`wall_left/right/front/back` 或 `ceiling`；对象间关系用 `relative_to` 指向前面已放置的对象。后端验证资产 ID、物体 ID、有限坐标和缩放范围，对 `floor` 避免穿地，在房间及支撑面边界内消除静态包围盒重叠；无法满足边界时明确报错。输出是 `output/scenesmith/scene_*/scene.glb` 与 `scene.json`。GLB 保留独立节点，SSUI 通过原有 path-backed `Mesh` 返回。当前实现针对静态几何；蒙皮、动画和复杂层级保真仍需单独验证。

验证命令：`yarn test:scenesmith` 和 `yarn test:scenesmith:planner`。前者在当前 Windows ARM64 共享 Python 环境创建真实 GLB 资产、生成场景并重新载入；后者使用本地 Qwen2 权重完成真实文字推理、GLB 导出和 SSUI 沙盒工作流执行，仅验证这一个固定提示词，不代表泛化质量或完整上游效果。

节点的 `stop_stage` 可设为 `floor_plan`、`furniture`、`wall_mounted`、`ceiling_mounted` 或 `manipuland`。每阶段输出保存在 `output/scenesmith/scene_*/stages/<stage>/`，包括 `scene.glb`、`scene.json` 与 backend CPU 生成的 `preview.png`；最终目录也有预览图。预览采用简单三角形投影和着色，用于检查位置，不代表材质真实渲染。将旧阶段目录或 `scene.json` 填入 `resume_from`，再提供新增对象规格即可继续；重复物体 ID 会报错。快照记录资产 SHA-256，续接时若资产内容已变会报错。阶段快照目前保存静态几何和位置，不包含上游代理对话或物理状态。可选的 `backend/scenesmith_blender.py` 能调用原生 Blender 导出 `.blend` 和 PNG，但当前机器的商店版后台启动没有产出文件，尚未通过真实渲染验收。

## 与上游 SceneSmith 的关系

此模块只移植了“资产目录 → 场景规格 → 独立实例”的集成边界。上游 SceneSmith 提交 `67cc408fd38334b4a926efef45e284302ed5055b` 的代理规划、检索服务、Blender 渲染和 Drake 物理求解尚未进入 SSUI backend。上游限制 Python 3.11/Torch 2.5，Drake 1.47.0 没有 Windows ARM64 wheel；SSUI 当前共享环境是 Windows ARM64/Python 3.12。要得到完整上游效果，需要把这些依赖的职责逐一替换为本机兼容实现，不能通过复制上游包直接完成。

后续顺序：原生语言规划器输出 `ssui.scene-layout/1`；资产语义索引；碰撞、支撑面及落地校正；桌面 UI 的逐物体编辑；最后做真实提示词质量和速度验收。当前这些项目尚未验收。
