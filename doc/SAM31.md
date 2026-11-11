# SAM 3.1 图片分割

SAM 3.1 使用独立的 Python 环境运行，避免改变 SSUI 当前锁定的 PyTorch 2.4.1 和 CUDA 12.4 依赖。

1. 按 [官方安装说明](https://github.com/facebookresearch/sam3#installation)创建 Python 3.12、PyTorch 2.7+、CUDA 12.6+ 的环境，并安装最新版 `facebookresearch/sam3`。
2. 在 [facebook/sam3.1](https://huggingface.co/facebook/sam3.1)申请权重访问权限，并在独立环境中登录 Hugging Face。也可以下载 `sam3.1_multiplex.pt` 到本地，通过 `--checkpoint` 指定路径。
3. 在仓库根目录运行：

   ```bash
   python scripts/sam31_image.py input.jpg "red car" output_masks
   ```

脚本写入 `results.json` 和每个实例的灰度 PNG 掩码。`--threshold` 可设置置信度阈值，默认 0.5。该入口只处理图片文本提示；视频追踪和 SSUI 工作流节点仍需独立接入。
