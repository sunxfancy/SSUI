# 内存、显存和模型 offload

功能 UI 顶部每 2 秒显示服务端机器的系统内存与各 CUDA 显卡的已用 / 总量。
内存按 total - available 计算；CUDA 显存按驱动 free / total 计算，包含其他进程占用。
未检测到 CUDA 与读取失败分别显示。Apple 共享内存设备当前只显示系统内存，不提供独立显存读数。
远程服务时显示服务端机器，非浏览器机器。

图片模型的 ModelLoaderService 和 load_model_from_path 已启用现有 CUDA 部分加载：
缓存会清理未锁定模型，保留默认 3 GiB 执行空间，按剩余显存加载权重，其余留在 CPU，
由现有自定义层按需转移。保留空间是估算，不保证任何分辨率和批次都不会 OOM。

进入缓存时发现主存余量不足（预留至少 1 GiB 或总内存 10%），会发起一次性磁盘确认。
允许后将 CPU 权重写入临时文件并 mmap 映射，仍使用同一部分加载与卸载路径。
拒绝、180 秒未答复、服务端不可达或磁盘空间不足都会停止加载。
磁盘至少需要权重大小加 1 GiB 可用空间；模型缓存释放后临时目录随对象回收。
进程异常退出可能留下 ssui-offload-* 临时目录，可在关闭应用后清理。

执行器默认连接 http://localhost:7422，通过 SSUI_SERVER_URL 指定其他服务端地址。
SSUI_OFFLOAD_DIR 可指定磁盘缓存根目录；默认为用户缓存目录下的 SSUI/offload。
请把它放在有足够空间的真实磁盘上：Linux /tmp 可能是 tmpfs，无法缓解主存不足。
授权仅适用于本次请求，不会记住为永久许可。

## 当前覆盖范围

| 入口 | 自动 CPU offload | 经确认的磁盘 offload |
| --- | --- | --- |
| 图片 ModelCache | 现有 CUDA 部分加载 | CPU 权重 mmap |
| 视频 Wan / Wan2 / Wan2.2、CogVideo、Hunyuan、AnimateDiff | DiffSynth 加载前预算 + Accelerate 逐层钩子 | mmap CPU 权重 + 同一逐层钩子 |
| TRELLIS 3D | 每个组件加载前预算 + 逐层钩子，执行设备独立保存 | 同一授权与 mmap 路径 |
| LTX 独立进程 | 主进程预检后设置原生 --offload cpu | 原生 --offload disk，仅授权后传入 |
| H3 独立进程 | Hub 文件大小预检 + ComponentsManager CPU offload / int8 组卸载 | 检查 diffusers 原生磁盘组卸载能力后启用 |

视频按整个模型组估算后再加载首个组件；TRELLIS 逐个组件检查实时余量。
本地权重文件统计会去重，目录仅统计权重文件；仓库未提供可靠大小时停止自动加载。
H3 使用 Hub 文件大小元数据，不会为估算预先把权重读进 RAM。
逐层钩子与原有阶段 .to/.cpu、Wan 显存管理保持互斥；VAE 的执行设备不从 meta 权重推断。
加载器先在 CPU 上完成 LoRA / INT8 转换，再安装卸载策略；原生 INT8 保留组件方法和生成器的驻留包装。
FP8 保留框架原生存储/计算精度转换；当前自动磁盘路径对 FP8 明确拒绝，请使用 none/int8。
DiffSynth 的 LoRA 更新会暂时恢复 CPU 权重，更新后重新安装同一卸载模式；更新仍可能产生内存峰值。
推理异常会释放失败层权重，支持随后重试。
TRELLIS 通过 empty-weights 初始化和 assign 加载权重，避免保留初始化权重的重复副本。

语音、LLM 及尚无可运行节点的 Motion / StdGEN 不在本次适配范围内。
首次反序列化、精度转换、LoRA 更新和写入映射文件仍可能出现主存峰值；
预检基于权重大小和预留空间，不代表能预测所有运行时激活开销。
超大单层、框架绕过模块调用、自定义量化 Tensor 或缺少原生卸载能力可能无法安全卸载，
会报告错误；不会偷偷降低精度、分辨率或帧数，也不会绕过授权尝试磁盘卸载。
mmap 还需要运行内存和 OS 页缓存，不能保证所有模型均可在任意内存大小运行。

## 验证边界

`yarn test_on tests.runtime_offload_test` 检查真实 CPU Tensor 的钩子生命周期、
磁盘映射输出一致性、失败恢复、LoRA 风格更新，以及实际适配器源代码的策略传递。
这些检查不需要下载巨型模型，不代表真实视频或 3D 模型的 GPU 推理、导出或质量验收。

接口：GET /api/resources/；POST/GET /api/resources/disk-requests；
GET/POST /api/resources/disk-requests/{id}。确认记录保留 180 秒，最多 128 条。
