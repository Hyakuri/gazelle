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

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：
