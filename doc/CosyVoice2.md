# CosyVoice2

CosyVoice2 使用根目录的共享 `.venv`。第三方代码已经随 Voice/vendor 提供，无需单独克隆 CosyVoice 或创建另一套环境。

在根目录运行 `yarn` 安装依赖。已有环境在更新仓库后运行 `yarn install-requirements`。依赖源位于 `dependencies/dependencies.yaml`，requirements 和 lock 均由项目命令生成。Linux / Windows x64 CUDA 目标集中声明 CosyVoice2 所需依赖；其他目标保留上游的平台专用运行时和约束。首次运行需要下载数 GB 模型。

```bash
yarn test:cosyvoice --prompt /absolute/path/reference.wav \
  --prompt-text "参考录音中实际说出的文字。" \
  --text "你好，欢迎使用语音合成。" --device cuda
```

参考音频不超过 30 秒，建议使用清晰、单人、有声录音。程序将其转成单声道 16 kHz，`--prompt-text` 必须与录音一致。默认下载 `FunAudioLLM/CosyVoice2-0.5B` 到根目录 `models/CosyVoice2-0.5B`；已有权重可通过 `--model /absolute/path/model` 指定。

默认输出 `artifacts/cosyvoice2/output.wav` 和同名 JSON，记录 PyTorch 版本、三个合成子模型的设备、ONNX provider、采样率和时长。`--device cuda` 要求三个模型以及语音 tokenizer 都启用 CUDA，否则报错。`--device cpu` 可在没有 GPU 的机器上验证真实合成；`auto` 自动选择可用设备。CPU 输出不能作为 CUDA 验证结果。

完整测试系统中的真模型测试：

```bash
SSUI_RUN_MODEL_TESTS=1 SSUI_COSYVOICE_DEVICE=cuda yarn test_on model.cosyvoice_model_test
```

真模型测试使用独立进程，默认下载上游示例参考音频，保留生成结果到 `TEST_DATA_DIR/cosyvoice2-artifacts`（默认 `~/.ssui_test_data`）。可通过 `SSUI_COSYVOICE_MODEL`、`SSUI_COSYVOICE_PROMPT`、`SSUI_COSYVOICE_PROMPT_TEXT` 指定本地输入。

SSUI 接口为 `CosyVoiceModel.load(model_path)` 与 `GenVoice(config, model, text, prompt_audio, prompt_text)`。`prompt_audio` 使用 `Audio('wav', wav_bytes)`；结果是 WAV 字节形式的 `Voice`，保留全部合成分段。

共享 WeTextProcessing wheel 沿用 Windows 已使用的发行包；Linux CUDA 显式声明 pynini，避免旧版 PyPI WeTextProcessing 强制安装不适合 Python 3.12 的 pynini 2.1.5。无需 TensorRT、DeepSpeed 或 vLLM 即可运行此推理路径。

HyperPyYAML 的 ruamel.yaml 与配置加载所需的 pyarrow 已固定兼容版本，避免最新依赖与当前加载器 API / NumPy 1.x 不兼容。

为控制内存，验证命令默认跳过文本规范化，请传入已规范化文本（数字、日期等需先转为读法）。需要完整文本规范化时显式传入 `--text-frontend`，首次 FST 编译可能占用较多内存。正常 SSUI 接口保留文本规范化默认行为，按需加载单一语言并复用 FST 缓存。验证时只启动一个推理进程。

本次 Linux / RTX 3090 验证通过：PyTorch 2.4.1+cu124，三个合成子模型位于 cuda:0，ONNX tokenizer 使用 CUDAExecutionProvider，生成 24 kHz / 2.64 秒 WAV。单进程在 4 GiB MemoryMax、MemorySwapMax=0 的 systemd scope 下完成，迁移到最新 dev 后复测最大 RSS 4,377,880 KiB（RSS 包含共享映射，与 cgroup 内存计费不同）。未验证 Windows/macOS 实机推理，也未运行首次 FST 编译。

复测复用了已安装的 Python 环境和模型缓存，未重新安装整个最新 dev 依赖集合。Linux/Windows CUDA 锁文件已按最新配置源重新解析；其他目标保持上游约束。
