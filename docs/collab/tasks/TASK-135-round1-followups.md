# TASK-135：第 1 轮审查的后续加固（时间戳回退无漂移、重封装尾部检查、文档与测试）

状态：ready
创建：2026-10-16（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：TASK-131、TASK-132 的第 1 轮审查结论（各任务文件 §3）；两份独立代码审查的发现；问题登记表 GZ-07、GZ-21。
授权：2026-10-14 本地修改与本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

修正 TASK-131 r3 时间戳回退算法的累积漂移，加强 TASK-132 的尾部解码检查，并补齐两项任务在文档与测试上的缺口。TASK-131、TASK-132 已验收，本任务只做改进，不改变它们已验收的其他行为。

### 必须实现

1. **时间戳回退无漂移（TASK-131 契约 r4）**：按 TASK-131 §1 第 1 条 r4 的第 4 步实现，即 `max(prev_out + 1000 / fps, p + 1)`，其中 `prev_out` 为上一帧未取整的输出值，`p` 为其取整值。更新 TASK-131 表格第 4、5 行对应的测试期望。新增漂移回归：从 0 开始连续 10 分钟没有时间戳时，29.97、30、60 fps 下最后一帧与 `(n - 1) * 1000 / fps` 的差小于 1e-6 毫秒。
2. **TASK-131 的文档精确化**（四份用户文档，中英一致）：
   - 回退规则写成“取上一帧加一个标称帧间隔与上一帧取整后加 1 毫秒两者中的较大值”，不再写“至少 1 毫秒或一个帧间隔”这类有歧义的表述。
   - “缺失的时间戳”定义写全：非有限值、负数，以及从下标 2 起为 0 的值。
   - `run_config.json` 新键在键表中按其他行的写法标注可为 `null`。
   - 截断时：avc1 只保留 JSONL 与 `run_config.json`；mp4v 会留下不完整的 `rendered.mp4`。照实写明。
   - AVI 重封装示例改用仓库外的占位路径，避免在仓库根目录生成媒体文件。
   - 说明行为变化：下标 1 的 `POS_MSEC` 为 0 时，该帧现在记为 1 毫秒，不再按帧号推算。
3. **TASK-131 的测试补强**：
   - 截断测试中的假 writer 实际创建文件，验证 avc1 的临时源文件不会残留。
   - 错误信息断言要逐项检查已读帧数、要求帧数、容器帧数带标签的文字，以及“undecodable packets”提示。
   - 新增一条 CLI 级测试：截断时 `main()` 以非零码退出。
4. **TASK-132 的尾部解码检查加强**：
   - 尾部从 `count - 60` 处定位后一直读到读取失败，最多读 120 帧。
   - 要求读取以失败结束，且结尾连续成功读取不少于 30 帧。
   - 最后一帧的 `POS_MSEC` 与输出最后一个包的 PTS 相差不超过一个标称帧间隔，`probe_packets` 需要返回最后的 PTS。
   - 新增失败用例：末尾 30 帧不可解码时校验不通过。
   - 用加强后的检查重新校验现有 11 个重封装文件；校验通过的跳过、不重写，报告每个文件的结果。
5. **TASK-132 的测试补强**：首 60 秒含小包的 AVI 得到 `needs_remux` 为 true；只改修改时间、不改大小时，SHA-256 缓存失效并重算。
6. **文档结构**：四份用户文档各设一个独立的「研究数据工具 / Research data tools」小节，不再放在“视频推理”或“常见错误”小节之内。现有内容整体迁入，`tests/test_usage_docs.py` 的锁定 token 随之调整。

### 非目标

不改区域标记工具（TASK-123 自行修复）；不改逐帧 JSONL 字段；不改 MediaPipe 后端的严格递增检查；不处理 MediaPipe 遥测（GZ-23）与 Torch Hub 联网探测（GZ-24）。

### 依据材料

- `gazelle/runtime/media.py`、`gazelle/runtime/pipeline.py`、`tools/workdata/remux.py`、`tools/workdata/common.py`、`tools/workdata/inventory.py` 及对应测试。
- 四份用户文档中 TASK-131、TASK-132 加入的内容。

### 不可变约束

AGENTS.md 全部运行时不变量与默认测试隔离；源目录只读；现有有效的重封装输出不得被破坏。

### 允许动作

修改上述代码、测试、四份用户文档与 `tests/test_usage_docs.py`；读取源目录与数据根，按第 4 条重新校验重封装输出；按协作方案 §4 提交并推送，并在 PR #6 发英中双语评论。问题处理按协作方案 §3.5。

### 禁止

协作方案 §3.5 的硬边界；写入源目录或用户独立目录；提交数据或媒体。

### 验收标准

1. 新增与既有测试通过；完整离线门通过，无新增 skip。
2. TASK-131 r4 表格全部用例与漂移回归通过；TASK-131 其余已验收行为不变。
3. 11 个重封装文件在加强后的检查下全部通过，或对未通过的文件给出数据，按 §3.5 的 B 级交 Claude 判断。
4. 四份用户文档各有独立的研究数据工具小节，中英语义一致，第 2 条六项都已体现。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-135-pycache"
& $py -m unittest tests.test_media tests.test_video_pipeline tests.test_runtime_cli tests.test_workdata_tools tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（时序语义）。
- 需真实运行：重封装输出的重新校验，仅 CPU。
- 文档同步：需要。
- 依赖：无；排在 TASK-123 修复之后、TASK-133 之前，让后续任务直接写入新的文档小节。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实运行结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 自主决定（A 级）：
- 范围外改动：
- 待 Claude 判断（B 级）：
- 待用户决定（C 级）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

### 2026-10-17 实施报告

- **接手/提交**：在 TASK-123 修复报告提交 `870f5dd` 后按 STATE 接手。实现 `40c10d7de56e6112471100786f5f55db9c9df3c3` — `Remove timestamp drift and verify remux decoding reaches the tail` 已推送。
- **实现**：读取器保留上一帧未取整输出，严格按 r4 `max(prev_out + 1000 / fps, p + 1)` 回退，其他容器/修补分支不变。重封装尾部从 count−60 读到 EOF（上限 120），要求连续成功至少 30；probe_packets 新增最后实际包的 last_pts，尾部解码时间按 `r_frame_rate` 的一个标称间隔检查。报告保留 decoded 数组并新增 decode_details/tail_pts，现为真实窗口帧数。CLI 实际子进程确认截断异常使进程退出非零，未改 CLI 异常语义。
- **文档**：四份用户文档独立研究工具小节，USAGE 编号增至 16；r4、完整缺失值定义、下标 1 的零值行为、nullable、avc1/mp4v 截断产物差异、仓库外重封装路径均同步。中文工具指南同步尾部校验，并补正之前遗留的 Gazelle 环境名称。
- **命令/结果**：`$py=C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，`PYTHONPYCACHEPREFIX=%TEMP%\gazelle-task135-pycache`。`& $py -m unittest tests.test_media tests.test_video_pipeline tests.test_runtime_cli tests.test_workdata_tools -v`：141 项、exit 0；`& $py -m unittest tests.test_usage_docs -v`：19 项、exit 0。`& $py -m compileall main.py gazelle tests tools`、`& $py -m unittest discover -s tests -v`（最终代码 **572 项 / 6.672 s / no skips**）、`& $py main.py --help`、`& $py main.py --list-models`、`git diff --check` 均 exit 0。最终文档微调后重跑 19 项文档检查通过。
- **红绿/失败**：旧实现下新测试 141 项，8 failures/3 errors，包含 10 分钟漂移（29.97/30/60 FPS 均失败）、r4 表格与尾部检查；其中两个 errors 是新测试自身问题（fake writer 未接受 kwargs；CLI 本来以未捕获 ValueError 退出而非直接抛 SystemExit），修正测试为真正子进程后通过。另一次只读探索使用了不存在的 tests/fakes.py，改读现有 FakeCapture。既有 OpenCV malformed-media warning 与 Git LF/CRLF 提示不影响 exit status，无新增 skip。
- **真实执行**：`& $py C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-135\revalidate.py`，父 PowerShell/子进程 BelowNormal；只调用 ffprobe 与 OpenCV，完全不调用重封装函数或 FFmpeg 编码，以免校验失败时重写已有输出。最终 **11/11 skipped-valid，exit 0，103.767 秒**。源/输出文件大小和 mtime 前后相同；现有 remux_report.json 保留，新增结果在数据根 `remux/task135_validation.json`。全部头/中各 30 帧、尾部到 EOF，最后解码时间与包 PTS 相差 **33.000 ms**，均小于标称间隔 **33.333 ms**。

| 会话/摄像机（原 AVI，对应 MP4） | 尾部连续帧 | 结果 |
| --- | --- | --- |
| 20260821 / cam_a | 60 | skipped-valid |
| 20260821 / cam_b | 60 | skipped-valid |
| 20260821 / cam_e | 60 | skipped-valid |
| 20260828 / cam_a | 60 | skipped-valid |
| 20260828 / cam_b | 60 | skipped-valid |
| 20260828 / cam_e | 59 | skipped-valid |
| 20260903 / cam_e | 60 | skipped-valid |
| 20260911 / cam_e | 60 | skipped-valid |
| 20260925 / cam_e | 60 | skipped-valid |
| 20261002 / cam_e | 60 | skipped-valid |
| 20261009 / cam_e | 60 | skipped-valid |

- **外部活动**：真实 CPU/磁盘、ffprobe/OpenCV；没有模型/GPU/MediaPipe、下载、网络数据访问、缓存或环境修改；GitHub 只发布代码、文档及汇总报告。首次真实复核以 OpenCV 平均 FPS 为容差，103.697 秒全部通过；自查收紧为 `r_frame_rate` 后再次完整复核，以上数字为最终规则结果。日志与重跑脚本在 `gazelle_runs/task-135/`，单测日志在 `%TEMP%/gazelle-task135-*.log`。
- **反证式复核**：r4 全表、高帧率/非有限边界与连续 10 分钟无时间戳均通过；29.97、30、60 FPS 最后帧误差均 <1e-6 ms。假 writer 实际创建临时 MP4，截断后不存在；错误文本逐项核对 read/required/container reports/undecodable packets。模拟末尾 30 帧不可解码、120 帧上限未 EOF、最后 PTS 偏离标称间隔、包数/时长/PTS 非递增均拒绝。mtime 单独改变会重算 SHA，首分钟含小包的 AVI 标记 needs_remux。

#### 自主决定（A）

标称帧间隔采用 ffprobe `r_frame_rate`，避免 VFR 的 OpenCV 平均 FPS 放宽阈值。真实复核用只读驱动脚本，把结果写独立报告；无效时报告失败而不自动重封装。CLI 测试通过子进程测试现有未捕获异常的非零退出，无运行时接口变更。

#### 范围外改动

额外同步 `tools/workdata/README_CN.md` 的尾部校验与环境名称，属于本次用户可见行为的直接说明；无相邻功能。

#### 待 Claude 判断（B）

无阻塞问题。请独立审查时序语义、尾部规则与真实数据报告；所有文件固定 33 ms 差值与输出 start_time=0.033 s 一致，此处只作解释，检查仍使用未经补偿的实际差值。

#### 待用户决定（C）

无。状态：已实现、已实际运行、ready-for-review；尚未独立验收，不更新 last_accepted。

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：
