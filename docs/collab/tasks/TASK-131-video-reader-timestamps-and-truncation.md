# TASK-131：视频读取器的容器时间戳、严格递增与截断检测（GZ-07、GZ-21）

状态：ready
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
依据：[作业数据分析](../analysis/2026-10-15-workdata-analysis.md) §3.1、§3.2；问题登记表 GZ-07（升为 P0）与 GZ-21（新增）。
决策：D4（时间戳时钟）因作业数据证实为 P0 阻塞而按 Claude 的建议实施，用户可以否决。
授权：2026-10-14 本地修改与本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

让运行时在可变帧率 MP4 上不中止，保留容器给出的真实时间戳；解码提前停止时不再报告成功。

### 背景（已实际运行的事实）

- 作业数据的 29 个 MP4 分段中有 12 个在下标 2 中止。OpenCV 对下标 0 与 1 都返回 `POS_MSEC = 0`；`VideoFrameReader` 把下标 1 改为 `1000 / fps`（50 或 40 ms），而下标 2 的真实值只有 18 到 35 ms；`mediapipe_backend._video_timestamp` 拒绝取整后不递增的值。
- 原始 AVI 只能解出 1 帧，而 `CAP_PROP_FRAME_COUNT` 为 108219；`run_video_pipeline` 以 `frames_read = 1` 正常完成。

### 必须实现

1. `gazelle/runtime/media.py` 中 `VideoFrameReader.__iter__` 的时间戳规则：
   - R1：输出的 `timestamp_ms` 有限、非负，按整数毫秒取整（`int(round(x))`）后严格递增。
   - R2：`POS_MSEC` 有限、非负且取整后大于上一帧时，原样使用，保留可变帧率的真实间隔。
   - R3：个别不递增的值（包括下标 1 重复的 0）用满足 R1 的最小增量修补，且不推后之后的正常值。示例：原始 `[0, 0, 30, 98, 130]` 输出 `[0, 1, 30, 98, 130]`；原始 `[500, 480, 520]` 输出 `[500, 501, 520]`。
   - R4：整段 `POS_MSEC` 不可用时（非有限、负数，或从下标 2 起仍持续为 0），退回现有的 `frame_index * 1000 / fps`，同样满足 R1。判定规则写进代码注释与测试。
   - R5：每帧记录时间戳来源，取值为 `container`、`repaired`、`fps_fallback` 之一。`VideoFrame` 新增带默认值的字段，现有构造方式保持兼容。
2. `gazelle/runtime/pipeline.py` 的截断检测：
   - 期望帧数：`metadata.frame_count` 可用时，未设置 `--max-frames` 取 `frame_count`，设置了取 `min(max_frames, frame_count)`；`frame_count` 不可用时不检测。
   - 若 `frames_read < expected - tolerance`，其中 `tolerance = max(2, ceil(0.005 * frame_count))`，则先写出 `run_config.json`（`decode_complete` 为 false），关闭资源，再抛出明确错误，CLI 以非零码退出。已写出的 JSONL 保留。
   - 错误信息包含已读帧数、期望帧数、输入路径，并提示“文件可能含无法解码的数据包；AVI 空包的处理见 USAGE”。
3. 视频 `run_config.json` 新增三个键：`frames_expected`（未知时为 `null`）、`decode_complete`（布尔）、`timestamp_sources`（三种来源的计数对象）。
4. 四份用户文档：说明时间戳取自容器并做最小修补；解码提前停止即失败；`run_config.json` 的三个新键（更新 USAGE 中的键表与计数）；给出 AVI 空包的无损重封装命令（作业数据分析 §3.1）。`tests/test_usage_docs.py` 锁定三个新键名与重封装命令中的 `noise=drop`。
5. 测试（默认隔离，不读真实视频）：用 fake capture 覆盖 R1 至 R5 的全部示例、整段回退、中间夹有 NaN、取整碰撞（例如 10.2 与 10.4）；截断检测的正例、反例与 `--max-frames` 情况；`run_config.json` 新键；现有 `tests/test_media.py`、`tests/test_video_pipeline.py` 全部通过。

### 非目标

- 不引入新依赖，不安装 PyAV。
- 不改输出视频帧率，`resolve_video_fps` 不变。
- 不实现跳读或起始偏移。
- 不处理 AVI 空包本身（TASK-132 负责重封装）。
- 不改 `predictions.jsonl` 与 `head_observations.jsonl` 的逐帧字段。

### 依据材料

- 分支 `feature/stage2-correctness`，基线为 STATE.md 的 `last_pushed`。
- 代码：`gazelle/runtime/media.py`、`gazelle/runtime/pipeline.py`（`_video_run_config_payload`、主循环）、`gazelle/runtime/perception/mediapipe_backend.py`（`_video_timestamp`，只读参考，不改其拒绝规则）。
- 测试：`tests/test_media.py`、`tests/test_video_pipeline.py`、`tests/test_usage_docs.py`。
- 文档：`docs/USAGE.md` 中 `run_config.json` 的键表。

### 不可变约束

- AGENTS.md 全部运行时不变量。视频保持流式处理；观测、预测与渲染帧数一致。
- MediaPipe 后端的严格递增检查保留；修补在读取器完成。
- 默认测试隔离。

### 允许动作

- 修改上述代码、测试、四份用户文档与 `tests/test_usage_docs.py`。
- 只读读取 `E:\Gazelle_Workdata\` 做下方真实检查；输出写到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-131\`。
- 按协作方案 §4 提交并推送，并在 draft PR 发英中双语评论。

### 禁止

修改其他文件；写入 `E:\Gazelle_Workdata\` 或用户独立目录；新建分支或 PR、合并、force push；修改环境；下载。

### 验收标准

1. 新增与既有单测通过；完整离线门通过，无新增 skip。
2. 真实读取检查（仅 CPU）：对 29 个 MP4 分段各解码前 600 帧，套用 `_video_timestamp` 的取整递增规则，违规为 0；报告每段三种来源的计数。检查脚本放在仓库外，实施报告给出命令。
3. 真实截断检查：对一个原始 AVI（例如 `20260911\20260911_設備カメラ.avi`）以 `--max-frames 50` 运行 CLI，退出码非零，错误信息符合“必须实现”第 2 条；报告报错前是否已构建模型。
4. 真实 smoke（GPU，先按协作方案 §5 检查空闲显存）：对此前会中止的 `20260911\20260911表情解析用カメラ1-1.mp4` 以 `--head-source mediapipe --max-heads 1 --max-frames 300` 运行，退出码 0；`frames_read` 为 300；两份 JSONL 各 300 行；`decode_complete` 为 true；报告 `no_head` 与 `ok` 帧数。不加 `--save-rendered`。
5. 四份用户文档与 `tests/test_usage_docs.py` 同步。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-131-pycache"
& $py -m unittest tests.test_media tests.test_video_pipeline tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。涉及时序语义与输出 schema。
- 需真实 smoke：是，见验收标准第 2 至 4 条。
- 文档同步：需要。
- 风险与回退：修补后的时间戳与真实采集时间可能相差毫秒级；容器估算帧数不准时截断检测可能误报，误报时在实施报告中列出文件与数字，不放宽阈值。回退方式是 `git revert` 本任务的提交。
- 依赖：无。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实检查结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
