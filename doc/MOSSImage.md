# MOSS-Image（共享运行环境）

MOSS-Image 的推理实现在主仓库 `backend/moss_image/`，Image 扩展只提供节点。
无需新建虚拟环境，也无需升级到 Transformers 5 或 Torch 2.9。
此次移植没有修改共享依赖约束或平台锁文件。

## 使用

打开 `examples/basic/workflow-moss-image.py`，模型输入使用
`ssui_image.MOSSImage.MOSSImageModel.load`：

- `model_path`：完整的本地 Hugging Face Base/SFT 模型目录，或
  `OpenMOSS-Team/MOSS-Image-Base` / `OpenMOSS-Team/MOSS-Image-SFT`。
- `cpu_offload=True`：在文本编码、去噪、解码阶段之间将组件移回 CPU。
- `revision`：Hub 分支、标签或 commit；生产使用建议固定 commit。
  本次核对 Base 的版本为 `85975793d8b3d432f1b6e27f352abaa4c2a4c0d3`。

节点默认 1024×1024、50 步、CFG 3、shift 5，负分支跳过第 22 层。
负提示词可以为空。正提示词可输入自然语言或官方布局 JSON，布局坐标必须
与生成尺寸一致。尺寸必须是 16 的倍数。

也可直接调用后端：

```python
from backend.moss_image.pipeline import MOSSPipeline

pipe = MOSSPipeline.from_pretrained(
    "/path/to/MOSS-Image-SFT", device="cuda", cpu_offload=True,
)
image = pipe("一张写着「你好世界」的海报", negative_prompt="", seed=42)
image.save("moss.png")
pipe.close()
```

本地目录需包含 `transformer/`、`text_encoder/`、`vae/` 的配置和
safetensors 权重，以及 `tokenizer/tokenizer.json`。支持 safetensors 分片索引。
Hub 加载只下载配置、tokenizer 和 safetensors，不执行模型仓库里的 Python。
配置内的 `auto_map` 等远程代码入口不会被使用。

## 运行范围与内存

- CUDA/ROCm 使用 BF16 文本编码器和 DiT；VAE 固定 FP32。
- 无 CUDA 时使用 CPU FP32，速度慢，完整模型需要较大系统内存。
  当前节点尚未启用 MPS，也未验证真实 ROCm 硬件。
- 组件卸载仍会把完整 DiT 放到 GPU，所有组件权重常驻系统内存。
  **本实现不是官方 minimal/hybrid 模式**，不能沿用官方约 4GB 显存的数据。
  文本编码器的 BF16 权重约 17GB、DiT 约 10GB，推理还需要激活内存。
- 暂未接入 LoRA、FP8、逐层/磁盘卸载、图生图或额外的 SLG 控制。
  布局输入是文本条件生成，不等同于像素级编辑。
- 模型节点缓存加载结果；切换多个模型前可调用
  `MOSSImageModel.clear_cache()` 释放缓存引用和 GPU 权重。

## 验证

本次兼容验证环境为 Torch **2.4.1+cpu**、Transformers **4.55.4**、
Diffusers **0.38.0**、Accelerate **1.10.1**。后端推理不依赖 Diffusers Pipeline，
Diffusers 仅用于 VAE 对齐测试。

```bash
yarn test_on moss_image_test
yarn test_on moss_image_nodes_test
yarn test_on moss_image_e2e_test
yarn test_on flow_operator_discovery_test
yarn test_on diffusers_compat_test
```

测试覆盖 Qwen3.5 上游 FP32 数值基线（含跨 64-token 分块）、独立循环式
Gated DeltaNet 方程、训练网格时间表、文本掩码、负分支跳层、FLUX.2 VAE
解码对齐、分片校验，以及小尺寸本地模型目录加载到图片输出的完整链路。
基线来源和修改点记录于 `backend/moss_image/NOTICE`；许可证见同目录 `LICENSE`。

`moss_image_e2e_test` 使用正常的 Image 扩展导入路径，通过 HTTP 接口、真实
本地 WebSocket 调度器和沙盒执行示例工作流。它在三个组件各含两个
safetensors 分片的模拟模型上，覆盖准备阶段无权重运行、文本与布局输入、
第 22 层负分支跳层、种子复现、改变种子、PNG 落盘和失败后继续执行。
该测试需要允许本地 loopback socket，不需要访问互联网。
设置 `SSUI_MOSS_TEST_OUTPUT=/path/to/output` 可以保留测试 PNG。

本次补齐了测试环境缺失的 ONNX Runtime、ONNX、Spandrel、GGUF、Compel、
TorchSDE 等依赖；`pip check` 通过，Torch/Transformers 主版本未变。
MOSS、节点发现、Diffusers 兼容、FLUX.2、工作流编译和执行器相关验证共
37 项通过；另一个旧的可选集成测试未启用。完整模型权重测试未运行。

端到端测试发现并修复了工作流字符串注解解析、调度器 IPv4 地址解包，
以及同秒保存多个 PNG 时文件名碰撞的问题。

真模型测试需已有模型目录和 CUDA GPU：

```bash
SSUI_RUN_MODEL_TESTS=1 SSUI_MOSS_IMAGE_MODEL=/path/to/MOSS-Image-SFT \
  yarn test_on moss_image_model_test
```

该测试不会自动下载完整权重。CPU 数值和小模型测试不能代替真实 Base/SFT
画质、显存峰值、速度和各平台硬件验证。
