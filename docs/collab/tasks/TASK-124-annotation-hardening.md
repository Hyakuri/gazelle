# TASK-124：标注工具加固（TASK-138 的应修项，正式标注前完成）

状态：ready
创建：2026-10-17（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：TASK-138 §3 第 3 轮审查结论与一份独立代码审查。
授权：2026-10-14 本地修改与本地运算授权；作业数据只读。

## 1. 契约

### 目标

把“确认完成”的条件完全落在服务端已保存的状态上，降低播放时的写盘频率，并改进错误提示。标注规则与 schema 不变。

### 必须实现

1. **完成条件只认已保存的已看范围**：
   - 带 `finish=true` 的请求，按服务端已保存的 `viewed_ranges` 判断是否看完，与类别、他人入镜区间已有的规则一致。
   - 同一请求里新增的已看范围照常合并保存，但不用于本次完成判断。
   - 页面行为不变：页面在所有保存完成后才启用按钮。
2. **只含已看变化的保存降频**：
   - 只新增已看范围、没有其他改动的保存，最多每秒写盘一次。
   - 暂停、换段、点击“本段完成”、页面隐藏或关闭前立即写入。
   - 类别、他人入镜区间、备注的保存不降频。
   - 写盘失败的处理与现在相同：页面停止并提示。
3. **错误信息**：
   - `labels validate` 失败时输出一行可读的错误，包含段编号与原因，不打印 Python traceback。退出码仍为 1。
   - `viewed_ranges` 的结构错误使用自己的措辞，不再沿用 other_people 的错误文本。
4. **尾部检查的 `start_time`**：
   - `tools/workdata/remux.py` 中 `start_time` 缺失或为 None 时按 0 处理，并在复核结果中记录 `start_time_assumed_zero: true`。
5. **区域页面状态**：导出完成后、每次保存后，页面以服务端返回的完成状态为准刷新显示。没有实际改动的保存不显示“需要重新导出”。
6. **指南**：两份中文指南与四份用户文档的相应位置补充一句：修改了一段较长的类别后，确认完成前请回放检查该段，因为“已看”只表示显示过。
7. **测试**（默认隔离）：
   - 一次请求同时携带全部已看范围与 `finish=true`，在此前没有保存过已看的段上，完成被拒绝；已看范围本身被保存。
   - 只含已看变化的连续保存在 1 秒内最多写盘一次；暂停与换段时立即写入。用伪时钟测试，不依赖真实等待。
   - `labels validate` 的命令行入口：`--segment` 参数、失败时一行错误、退出码。
   - `media.py` 的 `p + 1` 分支返回 `float` 类型。
   - `start_time` 为 None 时按 0 计算并记录。

### 非目标

- 不改类别、判断规则、已看与完成的定义、标注 schema 版本。
- 不改区域文件或完成标记的格式。
- 不生成数据集。

### 依据材料

- TASK-138 §3。
- `tools/validation/labels.py`、`annotate_server.py`、`annotation_page.html`、`roi_page.html`、`roi_server.py`，两份中文指南。
- `tools/workdata/remux.py`、`gazelle/runtime/media.py`。
- 对应测试与两个 Node harness。

### 不可变约束

AGENTS.md 的默认测试隔离与运行时不变量；源目录只读；不创建或修改正式 `labels.json`、正式区域文件与完成标记。

### 允许动作

- 修改上述文件与测试，更新四份用户文档的研究数据工具小节与 `tests/test_usage_docs.py`。
- 在 `Gazelle-next` 中运行离线门与两个 Node harness。
- 浏览器实测用旧试用集与临时 `--labels-path`。
- 按协作方案 §4 提交、推送，并在 PR #6 发英中双语评论；问题处理按协作方案 §3.5。

### 禁止

协作方案 §3.5 的硬边界；修改任何 Conda 环境；写入源目录；提交数据、媒体或标注。

### 验收标准

1. 上述测试通过；完整离线门通过，无新增 skip；两个 Node harness 通过。
2. 浏览器实测（临时标签文件）：
   - 正常播放看完后能确认完成；
   - 播放过程中标签文件的写盘次数约每秒一次以内，可从文件修改时间或计数日志核对；
   - 中途暂停、换段后重新打开，已看范围没有丢失。
3. 四份用户文档与两份中文指南中英语义一致。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-124-pycache"
& $py -m unittest tests.test_validation_labels tests.test_validation_server tests.test_validation_roi tests.test_workdata_tools tests.test_media tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
node tests/roi_page_test.cjs
node tests/annotation_page_test.cjs
git diff --check
git status --short
```

### 其他

- 需独立审查：是，涉及标注数据的完整性。
- 需真实运行：只有浏览器实测，仅 CPU。
- 文档同步：需要。
- 依赖：无。排在第 4 轮，正式标注开始前完成。

## 2. 实施报告（Codex 追加，不要修改上文）

### 2026-10-18 实施与验证

- 在 TASK-140 两组低优先级代理生成与一组验证期间，主线程 Inline Execution 完成本任务；没有子代理。
- 完成条件检查请求前已保存的 viewed_ranges；携带新已看范围与 finish 的请求会先保存范围、拒绝本次完成，重读后可确认。没有新增完成捷径或更改 schema。
- 页面聚合仅已看变化，每秒至多一次；暂停、换段、完成、隐藏和关闭立即 flush，关闭使用 keepalive 并保留未保存提示。类别、他人区间、备注立即保存。错误时停止编辑。
- labels CLI 错误单行、含段号/原因、exit 1；viewed_ranges 使用自己的错误文本。remux 缺失/None start_time 记为 0 并记录 start_time_assumed_zero。media.py 已有 float 修复，无需改实现，新增类型断言覆盖 p+1 分支。
- ROI 保存与导出响应返回服务端 complete/has_export，页面据此显示；无变化保存保持已导出。四份用户文档与两份中文指南同步“较长类别修改后回放；已看只表示显示过”。
- 先红后绿：未保存已看仍被错误完成、viewed 错误措辞、None start_time 均实际复现。聚焦 77 tests / 3.396s 通过；完整离线门 **664 tests / 17.718s / 0 skip**，compileall main.py gazelle tests tools、help、list-models、diff-check 均通过。两个 Node harness 通过；伪时钟覆盖 1 秒聚合与暂停/换段/隐藏/关闭即时保存、备注不降频。坏 MP4 回归保留非致命 moov atom 提示。
- 实际浏览器：旧 roi_r2_trial、独立 `gazelle_runs/task-124/browser-trial.json`，没有写正式 labels。正常播放至 193/300，暂停并换段、重新加载，续标从 194 步开始，原 193 步全部保留；继续播放到 300/300 后按钮启用，确认后回到该段显示“已确认完成”。页面只使用测试类别 unknown，不作为科学标注。
- 每次实际保存的时间/段号/已看计数记录在 browser-save-audit.jsonl；播放周期约每秒一次，暂停末尾约 0.238 s 的间隔属于要求的强制 flush，单列而不冒充限频失败或删除记录。浏览器证据与精确区间统计在 browser-summary.json；所有日志留在仓库外。
- 外部活动：本机 loopback 浏览器、CPU/OpenCV 读取既有试用帧；本任务无 FFmpeg、GPU、模型、网络下载、环境改动。同期 TASK-140 的真实 CPU/FFmpeg 另记。正式 ROI/完成标记不变。
- A 级：聚合在客户端保存队列中执行，服务端仍同步原子写入并按已持久化状态判断完成，避免引入后台易丢失的待写状态。完成请求中新增加的观看进度在拒绝完成时仍原子保存。范围外：无。
- B 级：待 Claude 独立浏览器审查数据完整性与保存频率。C 级：无。**已实施、已静态检查、已实际运行；未独立验收。**

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
