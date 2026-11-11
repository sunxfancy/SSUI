# SceneSmith 完整原生移植检查表

上游固定版本：`nepfaff/scenesmith@67cc408fd38334b4a926efef45e284302ed5055b`。本文件记录完整移植所需的工作，不把当前 `backend/scenesmith.py` 的静态 GLB 摆放实现视为完成。

## 上游功能与 SSUI 对应项

| 上游阶段/子系统 | 完整移植的验收产物 | 当前状态 |
|---|---|---|
| `floor_plan` | 文字生成多房间墙、门、窗、地面及可恢复状态 | 单房间矩形地面/四墙和每墙一个门窗开口可由 JSON 创建；文本生成多房间、状态恢复未完成 |
| `furniture` | 语义检索/生成资产、约束摆放、尺度与碰撞校正 | 结构化 GLB 摆放、Qwen2 单提示词规划（含 SSUI 工作流执行）、多条明确文字关系的依赖排序与循环检测、接地和受房间边界约束的 AABB 碰撞修正已验证；语义检索/生成、复杂碰撞未完成 |
| `wall_mounted` | 墙面支撑和挂装校正 | 静态房间边界定位已测试；真实墙洞/挂装碰撞未完成 |
| `ceiling_mounted` | 天花支撑和悬挂校正 | 静态房间顶面定位已测试；悬挂稳定性未完成 |
| `manipuland` | 桌面小物、堆叠、装填和物理稳定性 | 单物体 `on` 支撑及支撑面边界检查已测试；堆叠、装填、仿真未完成 |
| 资产服务 | HSSD、Objaverse、生成模型与材质索引 | 用户 GLB 目录及名称/类别/标签描述索引；HSSD、Objaverse、资产生成和材质索引未完成 |
| 渲染/物理 | Blender 观察反馈、Drake 投影/仿真 | backend 已为每阶段生成 CPU 静态 PNG 预览，真实 Qwen2 场景画面已检查；原生 Blender 导入/渲染代码已接入，但商店版后台启动未产出文件，Drake 等价物理仿真未完成 |
| 状态/导出 | 五阶段保存/恢复、Blender、Drake、可编辑 GLB | 五阶段静态 GLB/JSON 快照和续接已测试；代理对话、物理状态、Blender/Drake 输出未完成 |

## 已确认的平台阻碍

- 当前 SSUI 共享 backend：Windows ARM64 / CPython 3.12；上游 `pyproject.toml` 要求 Python `>=3.11,<3.12` 和 Torch `>=2.5,<2.6`。
- 当前共享 backend 中没有 `pydrake`、`bpy`、Torch、Transformers 或 OpenAI Agents；上游至少 34 个 Python 文件直接导入 `pydrake`。
- Drake 官方支持表不包含 Windows；1.47.0 的 PyPI 文件没有 Windows ARM64 wheel。完整上游算法若坚持在 Windows ARM64 原生运行，需要移植/替换 Drake 几何、碰撞、优化与仿真接口，并验证行为等价。
- 当前环境没有 `OPENAI_API_KEY` 或 `SSUI_SCENE_ASSETS`；上游完整流程还需要模型权重、资产和相应许可。

## 完成判据

使用官方或明确等价的依赖，依次跑通五阶段的真实文字输入；保留资产来源和阶段状态；导出可编辑场景；检查物体语义、位置、墙/顶/支撑面约束、碰撞与物理稳定性；通过 SSUI 工作流和桌面实际运行。仅代码导入、模拟测试或静态 GLB 合成不能作为完整移植验收。
