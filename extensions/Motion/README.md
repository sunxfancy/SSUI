# MDM 文本生成动作

`ssui_motion.MDM` 使用独立进程执行官方 MDM，不在 SSUI 主进程加载旧骨骼资产。
`MDMTextToMotion` 返回 20 FPS、HumanML3D 22 关节的 XYZ 轨迹，并保留
`motion.npz`、官方 `results.npy` 和 MP4 骨骼预览。NPZ 用
`numpy.load(path, allow_pickle=False)` 读取，`joints` 的轴顺序是帧、关节、XYZ，
坐标单位为米；它尚不是 FBX/BVH 或已重定向到具体角色的动画。

## 环境

先安装仓库的 Python 3.12/CUDA 基础环境，再安装动作兼容依赖：

```bash
node dependencies/venv.cjs python -m pip install wheel setuptools==69.5.1
node dependencies/venv.cjs python -m pip install --no-build-isolation -r extensions/Motion/requirements.txt
```

基础环境的 `setuptools==70.2.0` 与旧 `clip-anytorch` 不兼容，动作环境使用
69.5.1。NumPy、Chumpy 和 Matplotlib 的旧 API 兼容仅在 `mdm_runner.py`
的子进程内启用。可用 `MDMModel.load` 的 `python_path` 指定独立动作环境解释器。

## 模型与数据

按 [MDM 官方说明](https://github.com/GuyTevet/motion-diffusion-model) 安装
50 步 HumanML 模型、SMPL 资产和 HumanML3D 文本数据；文本推理不需要动作捕捉训练数据。
本次验证使用 MDM `ef8edce6a53c6ab19e53b4d4dcf15bc0bc60a778`、
HumanML3D `9176e8fb446b71c7d2a725eb5cf6fec1ae3b3c23`，以及官方
`humanml_enc_512_50steps/model000750000.pt` 和相邻 `args.json`。

```bash
export SSUI_MDM_REPO=/absolute/path/to/motion-diffusion-model
export SSUI_MDM_CHECKPOINT=save/humanml_enc_512_50steps/model000750000.pt
export SSUI_MODEL_OUTPUT_DIR="$PWD/output/model-validation"
SSUI_RUN_MODEL_TESTS=1 yarn test_on model.mdm_model_test
```

`examples/advance/workflow-motion.py` 提供 SSUI 工作流。模型输入需指定官方源码目录和
checkpoint；生成后显示动作视频，轨迹文件保存在输出目录的独立 `mdm-*` 子目录中。
模型权重、SMPL 资产和数据集遵循各自上游许可。
