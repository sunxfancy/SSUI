# 图片文字识别

Image 扩展提供三个 `Image -> str` 工作流节点，分属 RapidOCR 与 EasyOCR 两套方案。示例见 [`examples/advance/workflow-ocr.py`](../../examples/advance/workflow-ocr.py)：

| 节点 | 模型与用途 | 可选依赖 |
| --- | --- | --- |
| `RapidOCRText` | PP-OCRv6 small，适合中文、英文截图与普通照片 | `requirements-ocr-rapid.txt` |
| `RapidOCRMediumText` | PP-OCRv6 medium，更大的检测与识别模型 | `requirements-ocr-rapid.txt` |
| `EasyOCRText` | CRAFT 检测与 CRNN 识别，适合中文、英文图片的另一种识别方案 | `requirements-ocr-easy.txt` |

按需把对应 requirements 文件安装到 Image 扩展所用 Python 环境。RapidOCR 3.10 包含 small 权重；medium 权重会在首次运行时下载。EasyOCR 可运行 `python scripts/download_ocr_weights.py --model-dir .build/ocr-models` 从 ModelScope 镜像获取 CRAFT 和 `zh_sim_g2` 权重，脚本会按 EasyOCR 官方配置校验 MD5。运行 EasyOCR 节点前，将 `SSUI_OCR_MODEL_DIR` 设为这个权重目录。离线部署需要预先缓存权重。三个节点输出按检测顺序拼接的纯文本；需要版面、表格或坐标时应使用结构化文档 OCR 流程。

真模型回归测试：设置 `SSUI_RUN_OCR_MODEL_TESTS=1` 后运行根目录的 `yarn test_on tests.ocr_model_test`。测试会生成写有 `SSUI OCR TEST 2026` 的图片，检查 small 和 medium；设置 `SSUI_OCR_MODEL_DIR` 后还会检查 EasyOCR 的中文识别结果。

本机 Windows ARM64 验证：RapidOCR small 和 medium 的 ONNX 权重、EasyOCR 的 CRAFT 与 `zh_sim_g2` 权重均已完成真实图片推理；根目录 `yarn test_on tests.ocr_model_test` 的三项测试通过。其他平台需分别验证。

模型依据：[RapidOCR 使用文档](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/install_usage/rapidocr/usage.en.md)、[EasyOCR 文档](https://github.com/JaidedAI/EasyOCR)。
