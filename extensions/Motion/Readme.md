# Motion / 人体骨骼识别

Motion 扩展从单人视频中提取 MediaPipe Pose 33 关键点，并输出：

- 带骨骼叠加层的 `Video`，用于快速检查识别质量；
- `SkeletonAnimation`，包含逐帧时间戳、图像归一化坐标、相对 3D/世界坐标和置信度；
- 执行完成后写入的 JSON 文件，可从骨骼预览器直接下载。

## 工作流

```python
from ssui import SkeletonAnimation, Video, workflow
from ssui_motion import PoseRecognitionOptions, recognize_pose

@workflow
def video_to_skeleton(video: Video) -> tuple[Video, SkeletonAnimation]:
    options = PoseRecognitionOptions(sample_fps=24, smoothing=0.45)
    return recognize_pose(video, options)
```

完整示例见 `examples/advance/workflow-pose.py`。

节点系统会显示两个可执行工作流：

- `video_to_skeleton`：上传视频后输出骨骼叠加视频与可逐帧检查的骨骼动画；
- `video_to_blender_comparison`：在上述输出之外调用 Blender，追加源骨骼/BVH 并排比对视频。

节点详情面板可调整采样 FPS、平滑强度、检测/跟踪置信度、断帧补偿和本地模型路径。
Blender 输出节点同时提供 `.blend`、BVH、误差报告和重定向报告下载。

## 模型与离线使用

MediaPipe 旧版环境使用内置 Solutions Pose；新版 Tasks 环境会在首次识别时下载官方
`pose_landmarker_full.task`，并缓存到 `~/.cache/ssui/mediapipe/`。可以通过以下任一方式改用本地模型：

```python
PoseRecognitionOptions(model_path="D:/models/pose_landmarker_full.task")
```

或设置 `SSUI_MODEL_CACHE`，让 SSUI 从指定的模型缓存目录读取。

## BVH 与 Blender 对比

执行器在保存骨骼 JSON 时会同时生成：

- `.bvh`：21 关节人形层级、固定中位骨长、局部 XYZ 旋转和连续欧拉角；
- `.retarget.json`：原始目标、前向运动学重建结果、逐关节平均误差、RMSE 与最大误差。

将结果在 Blender 中重建并逐帧比对：

```powershell
blender --background --factory-startup `
  --python extensions/Motion/blender/reconstruct_and_compare.py -- `
  --bvh output/skeleton_xxx.bvh `
  --retarget output/skeleton_xxx.retarget.json `
  --output-dir output/blender-comparison `
  --render
```

输出包括 `pose-comparison.blend`、无损 PNG 帧序列和
`blender-comparison.json`。渲染画面左侧为原始关键点，右侧为 BVH 重建；数值报告则直接读取
Blender 导入后的 PoseBone 位置，不依赖渲染图像颜色或抗锯齿。

Windows 上从 Microsoft Store 安装的 Blender 位于受保护的 `WindowsApps` 目录，不能直接通过其
实际 `blender.exe` 路径启动。此时使用随扩展提供的 MSIX 启动脚本，把相同的后台参数传给 Blender：

```powershell
$script = (Resolve-Path 'extensions/Motion/blender/reconstruct_and_compare.py').Path
$bvh = (Resolve-Path 'output/skeleton_xxx.bvh').Path
$retarget = (Resolve-Path 'output/skeleton_xxx.retarget.json').Path
$output = Join-Path (Get-Location) 'output/blender-comparison'
$arguments = '--background --factory-startup --python "{0}" -- --bvh "{1}" --retarget "{2}" --output-dir "{3}" --render' `
  -f $script, $bvh, $retarget, $output

./extensions/Motion/blender/run_msix_blender.ps1 -Arguments $arguments -Wait
```

该脚本只调用 Windows 的 MSIX 应用激活 API，不进行桌面自动化。默认应用 ID 对应官方 Store
版 Blender；普通 ZIP、MSI 或 Steam 版本仍使用前面的 `blender --background` 命令。

### 从真实视频一键生成 Blender 比对

仓库依赖安装完成后，可以用一个命令执行识别、导出和 Blender 渲染：

```powershell
./extensions/Motion/blender/video_to_blender.ps1 `
  -Video D:/videos/person.mp4 `
  -OutputDir output/person-motion
```

它会生成 `skeleton.json`、`pose-overlay.mp4`、`motion.bvh`、
`motion.retarget.json`、`pipeline-summary.json`，并在 `blender-comparison/` 中保存
Blender 场景、误差报告和 PNG 帧。脚本优先使用 PATH 中的普通 Blender；找不到时自动使用官方
Store/MSIX 版本。通过 `-SkipBlender` 可以只执行视频识别与 BVH 导出。

### 数据边界

MediaPipe 单目世界坐标以髋部为局部原点，无法恢复真实的全局位移。本扩展用画面中的髋部轨迹估计
相机平面根运动；深度方向根运动、稳定脚底锁定和目标角色的蒙皮骨架重定向仍需要额外约束。
