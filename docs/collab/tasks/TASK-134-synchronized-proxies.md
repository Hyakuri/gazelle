# TASK-134：5 Hz 同步代理视频

状态：ready（依赖 TASK-133）
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude
依据：[作业数据分析](../analysis/2026-10-15-workdata-analysis.md) §4、§6；[验证集规范 r2](../../superpowers/specs/2026-10-15-workdata-validation-set-design.md)；[多摄像机设计提案](../../superpowers/specs/2026-10-15-multicamera-attention-design.md) §3.1。
决策：D13（5 Hz、1080p）尚待用户批准。本任务只生成标注与评估所需的数据，参数可配置；若用户改选其他频率，重新运行即可，不需要改代码。
授权：2026-10-14 本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

为每次录制的三机重叠时段生成三段同步代理视频：同一帧号在三台摄像机中对应同一画面时钟时刻。

### 必须实现

代码放在 `tools/workdata/proxies.py`，复用 TASK-132 的清单与 TASK-133 的时间映射。

1. **时间网格**：`t_k = t0 + k × step`，默认 `step = 0.2` 秒；`t0` 为重叠起点向上取整到 `step` 的倍数；帧数 `N` 使网格完全落在重叠时段内。`--step-hz` 与 `--size` 可配置，默认 5 与 1920×1080。
2. **取帧**：对每台摄像机、每个 `t_k`，选择映射后时钟时刻最接近 `t_k` 的源帧，可跨分段。最近源帧与 `t_k` 相差超过 `0.5 × step` 时仍取最近帧，但标记为缺口。
3. **解码与编码**：按分段顺序流式解码，不把整段视频读入内存；由 FFmpeg 缩放后经管道传给 Python，或使用 OpenCV。编码使用现有 FFmpeg 的 libx264（CPU），CRF 20、`yuv420p`、恒定帧率等于 `step-hz`、不含音频；先写临时文件，校验后原子改名。
4. **旁注文件**：每段代理一个 `proxy_<cam>.frames.json`，逐帧记录 `k`、`t_k`、源文件、源 PTS、时间差、缺口标记。会话文件 `session.json` 记录网格参数、`t0`、`N`、三台摄像机、时间映射版本、代码提交 SHA。
5. **可恢复**：按会话与摄像机断点续跑；已有且校验通过的输出跳过；`--force` 才重做。长时间运行时进程优先级低于正常。
6. **测试**（默认隔离）：网格计算；跨分段的最近帧选择与缺口标记；旁注 schema；FFmpeg 命令参数；原子发布；不读真实视频，不调用真实 FFmpeg。
7. **真实运行**（仅 CPU，预计数小时）：全部 7 次录制。输出到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\proxies\<会话>\`。实施报告记录每次录制的 `N`、各摄像机缺口数、用时、输出大小。
8. **抽查**：每次录制随机抽 3 个 `k`（种子固定），用 TASK-133 的识别工具读三段代理视频该帧的画面时钟，三者与 `t_k` 的差都不超过 1 秒。

### 非目标

不做标注界面（TASK-121）；不运行感知或 Gaze-LLE；不改 `gazelle/` 下的代码。

### 依据材料

TASK-132 的清单与重封装结果；TASK-133 的时间映射与重叠时段。

### 不可变约束

源目录只读；代理视频只写数据根，不进 Git，不上传；默认测试隔离。

### 允许动作

新建与修改 `tools/workdata/proxies.py` 及其测试 `tests/test_workdata_*.py`；读取源目录与数据根；写数据根；按协作方案 §4 提交并推送，并在 draft PR 发英中双语评论。

### 禁止

写入源目录或用户独立目录；提交视频、帧或数据；修改 `gazelle/`；新建分支或 PR、合并、force push；修改环境；下载。

### 验收标准

1. 新增测试通过；完整离线门通过，无新增 skip。
2. 生成 21 段代理视频（7 次录制 × 3 台摄像机）；同一次录制的三段帧数相同，均为 `N`。
3. 缺口比例逐会话报告；抽查全部通过。
4. 用仓库的 `VideoFrameReader` 读取任一代理视频的前 300 帧，时间戳严格递增，间隔约 200 ms。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-134-pycache"
& $py -m unittest discover -s tests -p "test_workdata_*.py" -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（同步正确性）。
- 需真实运行：是，仅 CPU。
- 文档同步：四份用户文档不变，原因同 TASK-132；用法写入 `tools/workdata/README_CN.md`。
- 风险与回退：编码耗时长，与用户的其他实验争用 CPU，以低优先级运行；代理视频可删除重建。
- 依赖：TASK-133。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实运行结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：
