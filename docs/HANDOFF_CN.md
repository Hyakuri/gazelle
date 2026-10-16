# 跨电脑与跨 Agent 交接指南

[English](HANDOFF.md) | [当前项目快照](handoff/CURRENT_STATE.md) |
[共用协作流程](AGENT_WORKFLOW_CN.md) | [完整使用指南](USAGE_CN.md)

## 1. 阅读顺序

1. 根目录 `AGENTS.md`：长期规则、范围、环境与验证边界。
2. `handoff/CURRENT_STATE.md`：分支/PR 快照、已完成能力、证据、未提交修改、
   已知问题和未包含在迁移包中的资源。
3. 换电脑阅读本指南；切换或协作 agent 阅读 `AGENT_WORKFLOW_CN.md`。
4. 开展下一项具体任务时再按需读取 `USAGE_CN.md`、相关代码和设计。

交接包转移项目文件和证据，不转移聊天记忆、客户端权限、已安装 skills、凭据，
也不自动连接另一个 agent。流程适用于新电脑、同机两个客户端，以及仅接收快照的
审查者，不需要额外开发模型 API 集成。

## 2. 保留完整源码状态

配套便携压缩包包含：

| 内容 | 用途 |
| --- | --- |
| `repository/` | 已跟踪源码、明确纳入的交接文件及当前未提交文档修改 |
| `history.bundle` | 当前交接分支可达的 Git 历史，截止记录的 HEAD |
| `working-tree.patch` | tracked 文件相对 HEAD 的 binary-capable diff；新文件在 `repository/` |
| `MANIFEST.json` | SHA、branch、文件大小和哈希、overlay 路径、排除项、检查证据 |
| `Restore-Handoff.ps1` | 离线恢复到全新目标目录，验证 payload 哈希并恢复 Git 和 overlay |
| `TRANSFER_README.md` | 压缩包入口与准确恢复方法 |

压缩包另附 SHA-256 文件，用于发现传输损坏，不是签名。目标机器通过验收前保留
原始 checkout。不要直接复制正在使用的 `.git`、整个 Conda 环境或所有隐藏目录。

**离线路线：** 解压到新的普通目录，审阅 `TRANSFER_README.md` 和恢复脚本后，
在 PowerShell 中使用以下模板：

```powershell
Get-FileHash 'D:\transfer\gazelle-handoff.zip' -Algorithm SHA256
& 'D:\transfer\gazelle-handoff\Restore-Handoff.ps1' -Destination 'D:\work\gazelle'
```

替换为实际 zip、解压目录和目标路径，并与交付的 `.sha256` 比对。恢复需要 Git 和
PowerShell，目标目录必须不存在；脚本从本地 bundle clone、恢复校验过的修改和新文件，
未改动的已跟踪文件保留目标 Git checkout 的换行格式；原始逐字节源码快照仍在
`repository/` 中。
再将 `origin` 设置为 GitHub URL。不会连接 GitHub、安装依赖或运行项目。
若 PowerShell 阻止脚本，使用已获批准的本地签名/执行方式，不关闭全局安全控制。
恢复失败会保留半成品目录供检查；重试应选另一个新路径。

**GitHub 路线：** 在目标机器独立登录，clone 快照记录的分支，并核对远端是否更新。
不要以为远端已有未提交的 AGENTS 和本次资料。要恢复准确快照，优先采用离线路线，
之后再审查和整合远端新增内容。拥有交接包不等于获得 push、新 PR 或新分支授权。

## 3. 目标环境

记录的基线是 Windows、Python 3.14、PyTorch CUDA 13.0 wheels。先读
`environment.yml` 和快照中的源环境版本。不同 OS、架构或 GPU 需要另行批准环境
方案；该文件不是跨平台 lock。不要复制旧 Conda 安装目录或照搬 `C:\Users\yun\...`。

首先只读检查：

```powershell
conda env list
Get-Command git, conda, ffmpeg -ErrorAction SilentlyContinue
```

已有 `Gazelle-next` 就激活并检查，不重新创建或 prune。确实不存在时，先获得目标机器
新建环境授权，再执行：

```powershell
conda env create -f environment.yml
conda activate Gazelle-next
```

创建会下载依赖并写入新环境，本轮交接未执行。已有环境升级仍走 AGENTS 规定的
sandbox-first 流程；`environment_py311.yml` 保留上一版 Python 3.11 的 `Gazelle`
环境定义；回退时激活本机保留的旧环境，不存在时须获准后再用该文件重建。
`environment_1.0.yml` 是更早的 NumPy 1.26 参考；二者都不是降级当前环境的命令。

从仓库根目录运行 `python main.py` 可直接使用源码。确有 editable 安装需要时，
单独授权 `python -m pip install --no-deps -e .`，该命令会修改环境。

```powershell
conda activate Gazelle-next
python -B -c "import os,sys; print(os.environ.get('CONDA_DEFAULT_ENV')); print(sys.executable); print(sys.version)"
python -m pip check
```

激活后的第一条 Python 命令仅报告身份，`pip check` 检查依赖元数据，不下载或
构建模型。记录真实冲突，不自动升级包掩盖问题。确认解释器属于目标环境。
FFmpeg 是外部程序，不由 `environment.yml` 安装；`avc1` 需要可用 H.264 encoder，
`mp4v` 保留 OpenCV 路线。安装 encoder/driver 也需要对应授权。

## 4. 可选缓存与研究媒体

- `models/checkpoints`、`models/mediapipe`、`models/torch_hub` 不在普通源码包中。
  有需要时在无写入进程的情况下单独复制，记录相对路径、大小和 SHA-256，目标端
  逐项核对；不复制临时 `.downloads` 或 lock 文件。
- Torch Hub 缓存包含可执行 Python，除了权重还有代码；只使用已审查的源缓存。
  缓存存在不代表目标机器已验证。
- 缺失资源可能在 `--prepare-only` 或首次推理时下载；需要授权并记录真实网络/缓存活动。
- 原视频、标注和结果独立迁移，只复制选定资料及对应 run config、JSONL。保留原始
  文件，生成结果不进 Git。旧 run_config 中的绝对路径描述旧运行，不适用于新机器。
- 不批量迁移 `.codex`、`.claude` 私有设置、`.aws`、tokens、全局配置或私有 agent
  记忆；目标端独立登录并授予必要仓库权限。项目 `CLAUDE.md` 可迁移，机器配置不可照搬。

## 5. 验收关卡

Gate A：源码身份。核对恢复后的 branch/HEAD、manifest 哈希、工作区差异、可见
规则与排除资源。初始工作区应带有记录的未提交 overlay；“干净但旧”的 clone 并非完整交接。

Gate B：确认环境身份后执行离线验收：

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'gazelle-destination-pycache'
python -m compileall main.py gazelle tests
python -m unittest discover -s tests -v
python main.py --help
python main.py --list-models
git diff --check
git status --short
```

协作时各任务使用独立 pycache 路径，结束后恢复原环境变量值。测试可产生临时文件，
但默认不得下载模型、构建 DINOv2、执行真实 FFmpeg 或 CUDA。记录退出码、测试数、
warnings 和 skips。

Gate C：另行授权的真实 smoke test。先确认已激活 `Gazelle-next`、实际 CUDA/FFmpeg
能力。准备示例可能下载资源和构建 DINOv2，不进行媒体推理：

```powershell
python main.py --prepare-only --head-source mediapipe --pose-model full --model gazelle_dinov2_vitb14_inout --cache-dir models
```

真实视频模板中的 `USER_INPUT_PATH` 必须替换为已有视频，`USER_OUTPUT_ROOT`
替换为新输出根目录。命令会运行模型，可能使用 CUDA/下载缺失资源，写 JSONL、
config 和视频，并执行真实 FFmpeg：

```powershell
python main.py --input USER_INPUT_PATH --output-dir USER_OUTPUT_ROOT `
  --head-source mediapipe --max-heads 1 --pose-model full `
  --model gazelle_dinov2_vitb14_inout --device auto --cache-dir models `
  --max-frames 5 --save-rendered --video-codec avc1 `
  --face-pose-ray --pose-head-ray `
  --gazelle-head-mode eligible --gaze-render-mode valid-only
```

确认两份 JSONL 行数与 `frames_written` 一致，核对帧索引/时间戳、`run_config.json`
以及解码后的视频帧数。`no_head`、`no_gaze`、`skipped` 可以是正确结果，不强行改为
`ok`。使用可见头部的素材确认至少真正运行一次 Gazelle；全空输出不能验证模型路径。
对比时使用另一个输出根目录，以及 `--gazelle-head-mode all --gaze-render-mode all-predictions`。
这是包含活动桥接 head 的诊断模式，不能恢复过期轨迹，也不能证明视线准确率。
源机器和目标机器测试结果分别记录。

Gate D：agent 接手。核对指令加载，再以一个真实小任务演练实现/审查交接。文件
已复制或历史测试通过不能证明新 Codex/Claude 会话遵循全部规则，具体流程见协作文档。

## 6. 可直接发送给接手 Agent 的提示

```text
你正在接手 Hyakuri/gazelle。先读取 AGENTS.md、
docs/handoff/CURRENT_STATE.md、docs/HANDOFF_CN.md、docs/AGENT_WORKFLOW_CN.md。
检查实际分支、HEAD、工作区修改和指令来源，区分版本元数据、历史验证和本轮证据。
保留已有修改；没有对应授权时不要创建分支/PR、合并、force push、安装依赖、
下载模型、运行真实推理或发布。
你的角色是：<实现负责人 或 只读审查者>。
本次任务、允许修改文件与验收是：<具体目标、范围、验收>。
先给出简洁接手报告，只报告相关阻塞；然后持续完成已授权任务和适当验证。
```

使用前填写角色和任务两行；仅接管时将任务填为“只读检查”。多阶段任务采用
[TASK_TEMPLATE](handoff/TASK_TEMPLATE.md)，无需重复粘贴完整历史对话。
