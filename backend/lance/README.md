# Lance 原生后端

在 SSUI 进程内运行 ByteDance Lance，默认 **NF4 4-bit 权重量化**，也支持
`int8`、`none`。不启动外部 Lance/vLLM 服务，不要求 flash-attn 或 bitsandbytes。

```python
from backend.lance import LancePipeline

with LancePipeline.from_pretrained(
    "bytedance-research/Lance",  # 也可传本地完整 bundle 目录
    variant="image",
    quantization="nf4",  # nf4 / int8 / none
    device="cuda",
) as model:
    result = model("一只坐在窗边的橘猫", task="t2i", seed=42)
    result.images[0].save("cat.png")
```

图片编辑：`model("去掉背景", task="image_edit", image="input.png")`。
图片理解：`model("图里有什么？", task="x2t_image", image="input.png").text`。

视频需要单独加载 `variant="video"`：

```python
with LancePipeline.from_pretrained(
    "models/Lance", variant="video", quantization="int8", device="cuda"
) as model:
    clip = model(
        "海边的日落",
        task="t2v",
        width=848,
        height=480,
        num_frames=61,
        num_inference_steps=30,
    )
    # clip.frames 是 PIL 帧列表，交给 SSUI 现有视频导出器。
    clip = model(
        "让相机缓慢向右移动",
        task="i2v",
        image="input.png",
        width=848,
        height=480,
        num_frames=61,
    )
```

另支持 `video_edit`、`x2t_video`，用 `video=` 传路径、THWC 数组或 PIL 帧列表；
`origin_fps=` 指定源帧率。图片输出 `images`，视频输出 `frames`，理解输出 `text`。
视频帧数必须为 `4n+1`，最多 121；图生视频至少 5 帧。尺寸须为 16 的倍数且
不超过 1024。图片编辑和视频编辑按照参考媒体预处理后的尺寸输出，不使用传入
的宽高。理解任务默认启用采样，避免原模型贪心解码立即输出 EOS。

## 量化实现与内存边界

- 两套 MoT 专家的注意力投影和 MLP 都量化，包括 `*_moe_gen`，不是只量化文本分支。
- NF4：标准 16 值 normal-float 码表、64 元素分块、两个 4-bit 编码打包为一个
  `uint8`，FP32 块尺度。INT8：每输出通道对称量化、`int8` 权重和 FP32 尺度。
- safetensors 逐张量读取，meta 构造模型，CPU 上逐层量化后传到目标设备；不会
  先把整套浮点主模型复制到显卡。支持单文件和分片索引，加载前严格检查键和尺寸。
- 默认保留 embedding、LM head、时间/潜空间投影、ViT 和 VAE 的计算精度。
  `quantize_vision=True` 可进一步量化 ViT 线性层；其质量影响需实测。
- 使用 PyTorch 逐投影反量化后执行 GEMM，**没有低位融合算子加速**。常驻主干
  权重显著缩小，但当前投影会临时分配计算精度权重。KV 缓存、激活、潜空间位置表
  和 VAE 内存不随量化位数同比缩小，不能据此承诺 8/16GB 显存运行视频。
- 输入为官方浮点 checkpoint，运行时量化；不直接读取第三方 GGUF、AWQ、GPTQ
  或 bitsandbytes 预量化文件。不支持训练。没有量化失败后静默退回全精度的路径。
- `unload()` 或 `with` 退出释放模型及 VAE 引用。推理串行执行，退出时恢复随机数状态。

## 依赖与权重布局

复用 SSUI 已有 torch、transformers、safetensors、huggingface-hub、numpy、Pillow、
torchvision、einops；视频路径读取另外使用 imageio。无需降级主环境 diffusers。
CPU 默认 FP32，CUDA 默认 BF16；旧显卡可显式设 `torch_dtype=torch.float16`。
CPU 可用于小模型验证；真实权重的 CPU/AMD/MPS 性能和完整 CUDA 生成尚未在本移植中验证。

```text
models/Lance/
  Lance_3B/llm_config.json, model.safetensors, tokenizer 文件…
  Lance_3B_Video/llm_config.json, model.safetensors, tokenizer 文件…
  Qwen2.5-VL-ViT/config.json, vit.safetensors
  Wan2.2_VAE.pth
```

只需下载所选 variant 及共享组件。传 Hugging Face repo ID 时自动选择下载路径；
可用 `revision=` 固定权重版本。两套 checkpoint 不自动相互替代。

## 来源与验证

推理预处理、分段 KV 缓存、mRoPE、VAE 参考与噪声的位置重叠、CFG、首帧潜变量
固定和 Wan2.2 VAE 移植参考：

- [vLLM-Omni Lance](https://github.com/vllm-project/vllm-omni/tree/8acdba5770b2287329294e165c013fd545da9f7e/vllm_omni/diffusion/models/lance)
- [vLLM-Omni BAGEL](https://github.com/vllm-project/vllm-omni/tree/8acdba5770b2287329294e165c013fd545da9f7e/vllm_omni/diffusion/models/bagel)
- [ByteDance Lance](https://github.com/bytedance/Lance/tree/4baeee086648996f6ab12e673cbe461b0b149997)

MoT 主干在此实现为兼容原始权重键名的单请求 PyTorch SDPA 模型；vLLM 的张量并行、
序列并行、CacheDiT 和在线服务未移植。保留 Apache-2.0 来源标识和同目录 LICENSE。

运行：`yarn test_on tests.lance_test`。测试使用实际 CPU 小张量和小模型，检查量化
误差、实际压缩存储、双专家路由、缓存等价性、严格流式加载和首帧固定。
这些测试不能替代官方完整权重的图像质量、视频质量及 GPU 峰值显存验证。
