# 文本生成与 LoRA

打开官方示例 `examples/basic/workflow-text-chat.py` 可直接使用会话窗口。
`examples/basic/workflow-text.py` 保留通用函数界面，选择 `chat`（单次对话）或
`complete`（续写、代码、翻译等文本任务）。模型参数使用
`ssui_llm.Text.TextModel.load`，与其他模型一样通过工作流模型描述符加载。
已有 `ssui_llm.Qwen` 和 `workflow-chat.py` 接口保持兼容。

## 共用运行环境

LLM 扩展使用 `venv: shared`，复用 SSUI 的 PyTorch、Transformers、设备与精度选择、
执行器和参数面板。PEFT 0.17.1 在统一依赖清单和各平台锁文件中声明，
无需额外模型服务或另一套 Torch。用已有 `yarn install-requirements` 安装当前平台的依赖。
`yarn build:extension_builder` 后运行 `yarn ext:package_LLM` 可单独打包该扩展，
完整 `yarn ext:package` 也包含 LLM。

## 模型与适配器

```python
from ssui_llm.Text import TextModel, Chat, Generate
from ssui.config import SSUIConfig

model = TextModel.load(
    model_path="D:/Models/my-text-model",
    lora_path="D:/Models/my-text-lora",  # 不需要 LoRA 时留空
    lora_weight=0.8,
    local_files_only=True,
)
config = SSUIConfig()("Text")
config["max_new_tokens"] = 256
config["temperature"] = 0  # 贪心解码；大于零时启用采样
response, history = Chat(config, model, "你好", system_prompt="用中文回答")
response, history = Chat(config, model, "请继续", history=history)
# 没有 chat_template 的基础模型使用 Generate(config, model, prompt)。
```

`model_path` / `lora_path` 接受本地目录或 Hugging Face 仓库 ID。
下载并解压完整模型后也可以直接选择本地目录；`local_files_only=True` 禁止远程查找。
Hub 下载沿用已有 `HF_HOME` 缓存，受访问权限和模型许可约束。

通过 `AutoConfig` 自动选择 causal LM 或 encoder-decoder 模型加载器。
支持范围以当前共享 Transformers 版本的内置架构为准，例如该版本支持的
Qwen、Llama、Mistral、Gemma 和 T5 系列；不能将“同系列”视为所有新版本都兼容。
对话使用模型自身的 chat template，并传递历史与可选 system 消息；
模型模板不支持的角色组合会由模板报错。

LoRA 目录需包含 PEFT 的 `adapter_config.json` 和对应权重，且适配当前基础模型。
本实现每个模型加载一个 LoRA，支持权重缩放（含负值）；权重为零时跳过适配器加载。
每次加载拥有独立模型实例，避免一个工作流修改另一实例的权重。
DoRA 目前仅支持权重 1；这里不提供训练、多 LoRA 混合或图像 LoRA 转换。
图像 LoRA 与文本 LoRA 的权重格式、目标层不同，不能直接互换。

设备默认复用 `TorchDevice` 自动选择，也可指定 `cpu`、`cuda` 或 `mps`。
AMD 使用已配置的 ROCm PyTorch。模型整体放入目标设备；当前没有自动显存卸载、
量化或流式输出。会话窗口复用相同的工作流执行接口，完整回复生成后显示。
本入口不执行模型仓库自定义代码，也不加载 GGUF；需要这些能力的模型会报错。

## 验证

`yarn test_on text_generation_test` 覆盖参数、模板、历史、准备阶段、工作流加载，
以及本地随机微型 GPT-2 + 实际 PEFT LoRA 的保存、加载、缩放和推理，
并测试微型 Qwen2、Llama、T5 的加载与生成。
`yarn test_on qwen_chat_test` 检查原有 Qwen 对话接口。
微型随机模型用于验证执行路径，不证明任何预训练模型的输出质量或显存需求。
本次依赖锁刷新还将原先 Linux/macOS 中落后于统一清单的部分版本对齐；
跨平台安装和真模型运行仍需对应平台验证。

API 依据：[Transformers chat templates](https://huggingface.co/docs/transformers/v4.52.3/chat_templating)、
[PEFT LoRA](https://huggingface.co/docs/peft/v0.17.0/package_reference/lora)。

## 自动会话界面

会话 UI 是独立视图，与 Functional UI 和代码编辑器并列，可随时切换。
首次打开且未指定视图时会默认选择会话窗口，条件是脚本恰好注册一个 `@workflow`，
且其标注能明确识别文本输入、上下文输入及文本回复。无需指定特殊函数名称或新建服务。

- 文本输入为 `str`；多个文本参数时优先选择唯一的 `prompt`、`message`、`text`、`query` 或 `input`。
  `system_prompt` / `system` 留在设置区。
- 上下文为 `List[Tuple[str, str]]`（允许 `Optional`），返回 `Tuple[str, List[Tuple[str, str]]]`。
  如果只返回 `str`，界面自动追加本轮问答作为下一轮历史。
- 也支持名为 `history` 或 `context` 的字符串上下文（允许 `Optional[str]`），
  此时必须返回 `Tuple[str, str]`，第二项是完整的下一轮上下文。
- 多个工作流、无上下文或含糊的签名默认打开函数界面；显式选择 Functional UI 始终打开函数界面。类型别名由后端解析；
  沙盒脚本建议使用 `typing.List` / `typing.Tuple` / `typing.Optional`。

左侧复用模型、LoRA、系统提示和生成参数；右侧显示消息记录。
Enter 发送、Shift+Enter 换行，中文输入法组词时不会误发送。
生成期间禁用重复发送和参数修改。失败或上下文格式错误时保留草稿和原上下文，可重试。
模型返回的上下文会原样传给下一轮（允许工作流压缩历史），界面仍保留完整可见消息。
context 和消息记录由独立的共享会话状态层管理，按项目内脚本、函数和会话 ID 隔离，
复用项目 UI 状态服务的 `sessions` 存储域。两种运行界面执行前自动注入 context，
成功后更新 context；失败保留旧值，过期会话结果不能覆盖重置后的状态。
Functional UI 提供“查看／编辑上下文”和“重置上下文”，无需用户逐轮手工回传。
模型、LoRA、生成参数也跨视图共享；草稿和界面布局分别保留。
切换代码编辑器不会清空会话；刷新后可继续。函数上下文协议改变时建立新的空会话。
“新对话”清空消息与上下文，保留模型设置。离开页面会停止等待回复，不代表取消后端推理。

`yarn test_on conversation_test` 验证签名检测和真实执行器双轮调用；
`yarn test:ui tests/ui/conversation.spec.ts --workers=1` 验证浏览器交互，
包含上下文回传、重试、刷新恢复、脚本切换、模型/LoRA 参数、明暗主题和窄屏布局。
`yarn test:ui tests/ui/shared-session.spec.ts --workers=1` 验证三种视图之间的完整续聊、编辑与重置流程。
