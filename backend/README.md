# Backend

`backend/` 放置供服务端与扩展使用的 Python 推理和模型工具，不是独立启动的服务。`model_manager/` 提供模型配置、扫描、探测与加载；其公开导出见 `model_manager/__init__.py`。`stable_diffusion/` 包含图像推理辅助代码，`ip_adapter/` 包含 IP Adapter 实现，`util/` 包含设备、张量等共用函数。`native_tools.py` 配置特定平台的原生工具路径。

运行入口在 [server](../server/README.md) 与 [executor](../ss_executor/Readme.md)。根目录的 `yarn test` 运行常规 Python 测试；真实模型测试需要模型文件与相应硬件，设置 `SSUI_RUN_MODEL_TESTS=1` 后运行。模型运行目标见 [Runtime Targets](../doc/RuntimeTargets.md)，测试边界见 [测试指南](../doc/Testing.md)。
