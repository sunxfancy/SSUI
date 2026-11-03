# 本地模型的量化与 CPU offload

本地模型加载入口提供两个独立参数：

```python
model = Wan2T2VModel.load(quantization="int8", cpu_offload=True)
```

可以单独启用其中任意一项，也可以同时启用。既有默认值保留；新量化默认关闭。

| 模型 | 量化选项 | CPU offload 入口 |
| --- | --- | --- |
| SD1 / SDXL / FLUX | `none` / `int8` | `.load(..., cpu_offload=True)`，缓存解锁后卸载 |
| Wan / Wan2 / Wan2.2 | `none` / `fp8` / `int8` | `.load(cpu_offload=True)`，DiffSynth 分阶段卸载 |
| Hunyuan T2V / I2V | `none` / `fp8` / `int8` | `.load(cpu_offload=True)`，DiffSynth 分阶段卸载 |
| CogVideoX | `none` / `int8` | `.load(cpu_offload=True)`，提示词、去噪、VAE 分阶段卸载 |
| AnimateDiff | `none` / `int8` | 构造函数 `AnimateDiffModel(cpu_offload=True)` |
| TRELLIS | `none` / `int8` | `.load(path, cpu_offload=True)`，按组件调用卸载 |
| Qwen | `none` / `int8` | `.load(path, cpu_offload=True)`，生成调用之间卸载 |
| CosyVoice2 | `none` / `int8` | `.load(path, cpu_offload=True)`，LLM、flow、HiFT 调用之间卸载 |
| MiniMax H3 | `none` / `int8` / 既有 `nf4` | 节点新增 `cpu_offload` 开关；runner 支持 `--cpu-offload` / `--no-cpu-offload` |
| LTX2 | 既有 `none` / `fp8-cast` | 既有节点 `offload=none/cpu/disk` |

此表仅列本次接入 CPU offload 的加载入口；其他现有 3D、Audio、Motion、视频适配器保持原有运行策略。
原有 `backend.quantization.workflow.int8_quantizer` 也切换到同一自实现后端，因此其已有调用方无需改接口。
FP8 沿用原有细粒度卸载／计算精度转换路径，关闭 offload 时请选择 none 或 int8。
TRELLIS 的独立 MPS runner 保留原平台限制；H3 NF4 后端保留自动 CPU offload。
LoRA、ControlNet、IP-Adapter 等辅助权重不单独提供这组主模型加载参数。

## 安装与使用

通用 INT8 使用仓库自己的 `ssui/native_quantization.py`，只依赖 PyTorch，
不安装或导入 TorchAO、bitsandbytes 等量化库。H3 的 INT8 也复用该文件，
通过路径传入独立虚拟环境。LTX2 保留其原生 `fp8-cast` 实现。

量化采用每输出通道对称 INT8：`scale=max(abs(weight))/127`，
`q=clamp(round(weight/scale), -127, 127)`。全零通道使用 scale=1。
持久存储为普通 INT8 张量、FP32 scale 和原精度 bias；不保留全精度权重副本。
正向计算按输出行分块恢复浮点权重，再调用普通 `linear`；不依赖专用整数矩阵乘内核。
这使实现可使用 PyTorch 支持的设备，但不代表所有平台或模型已实测，也不承诺推理加速。

只转换普通 `torch.nn.Linear` 权重，保留卷积、Embedding、归一化和激活精度；
已有量化不重复转换；通用入口跳过未知 Linear 子类，Trellis 适配器保留 SparseLinear.forward 并压缩其权重。与 Embedding 等未转换层共享的权重保持原样，
避免破坏词表权重绑定。线性层之间的权重和模块别名在转换时保留共享关系。
`weight` 属性兼容直接读取，但返回临时反量化视图；不能通过修改该视图合并权重。
图像 LoRA 使用 sidecar。DiffSynth 通用／PEFT LoRA 也保留低秩 sidecar，
不改写压缩基底；Civitai 路径已经生成的稠密增量按块合并后重新量化，会引入额外舍入。
直接读取 `weight` 的模型路径会把原生 sidecar 加入临时视图；压缩检查点保存并恢复这些 sidecar。

量化在模型权重加载后执行，因此不会消除首次读取完整权重的 RAM 峰值。
保存的 state_dict 包含压缩缓冲区；重新加载时需先对相同结构执行量化，再加载 state_dict。
缓存可直接计算普通参数和缓冲区大小，不再需要第三方张量子类的特殊处理。

CPU offload 将非活动权重留在 RAM，并在需要计算时搬到 GPU，会增加 RAM 和传输开销。
通用组件卸载按完整组件进行，Qwen 的生成调用仍需装下整模型；它不是逐层卸载。
Wan/Hunyuan 的未量化默认路径保留原有细粒度显存管理，INT8 路径按阶段搬运。
CosyVoice 构造期间仍由原生加载器决定初始设备；卸载策略在其权重加载完成后生效。

工作流可使用同一组 UI 控件：

```python
from ssui.model_memory import model_memory

memory = model_memory(config("Model Memory"), cpu_offload_default=True)
if config.is_prepare():
    model = Wan2T2VModel()
else:
    model = Wan2T2VModel.load(**memory)
```

`examples/advance/workflow-video-local.py` 和 `workflow-3d.py` 已接入。
其余脚本可以把 `memory` 传给对应 `.load()` 或 AnimateDiff 构造函数。
图像缓存按策略分别创建，避免不同量化或卸载设置复用同一份缓存。

## 验证边界

`yarn test_on native_quantization_test` 验证量化误差界限、分块计算、零值／极值、
共享权重、dtype 变换、压缩检查点往返、biasless LoRA 和 H3 复用。
CUDA 与 MPS 测试仅在实际设备可用时执行，否则标为跳过。

`yarn test_on model_memory_test` 覆盖真实 CPU INT8 的存储压缩、数值误差和状态字典恢复，
以及组件卸载的嵌套调用、异常、装饰器包裹的流式生成、关闭与耗尽。
加载入口测试使用小型真实 Torch 模块和替代下载器，检查不同策略的参数传递。

`yarn test_on native_model_quantization_test` 另行覆盖小型 Qwen2 的缓存生成、
Diffusers UNet 的交叉注意力、仓库 Wan DiT 的完整前向以及 DiffSynth 的通用／PEFT／Civitai LoRA。
这些结构使用随机权重、不下载检查点，验证执行路径和误差，不验证内容生成质量。

这些测试不代表各大模型已完成 CUDA 实测，也不代表量化后图像、视频、3D 或语音质量已验收。
完整验收需在可用 GPU 上逐模型比较峰值 RAM/VRAM、速度、固定 seed 输出与原精度输出。
