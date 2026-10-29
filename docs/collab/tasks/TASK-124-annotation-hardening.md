# TASK-124：标注工具加固（TASK-138 的应修项，正式标注前完成）

状态：第 2 轮 ready-for-review（Codex，2026-10-29；尚待 Claude 独立审查）
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

- 提交并推送：`2dc76beddaee04b92ec1967d50eca0b6a212cb3a` — `Harden saved annotation completion and autosave`，19 个实现/测试/文档文件。双语报告见 [PR #6 评论](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6235471387)。
- 精确浏览器统计：连续播放期间 revisions 3–41 的 39 次写入，间隔 1.032907–1.293548 s；暂停强制保存 revision 42，距前一次 0.237614 s，保留已看 193 步。页面已关闭；仅本任务的临时 server 已按精确脚本路径核对后终止，未留下浏览器测试服务。WMI 查询无权限，改用普通沙盒 psutil 检查并结束自己的进程，没有提权或停止其他服务。

### 第 2 轮实施报告（Codex，2026-10-29）

- 实现提交：`21b3233` — `Throttle manual annotation viewing and flush closing pages promptly`。本报告与 TASK-140 数据交付报告一并推送到原分支、PR #6；不代表验收。
- `pause()` 仅在此前正在播放时立即保存；未播放的逐步/跳转/变化点定位保持每秒一次的已看队列。换段显式清空队列。隐藏、pagehide、关闭用立即发出的 keepalive，不等待已有请求；revision 检查保留。
- CLI 在进入对象操作前拒绝顶层数组，捕获嵌套过深等结构错误，输出一行、退出 1。四份用户文档与标注指南同步，删除英文指南的重复 version 1 句。
- 回归先失败：顶层数组触发 AttributeError；Node 未播放 10 Hz 连续 2 秒写入 20 次。修复后 `python -m unittest tests.test_validation_labels -v` 和 `node tests/annotation_page_test.cjs` 均 exit 0；Node 验证两秒不超过 3 次、间隔至少 1000 ms，以及已有保存未返回时仍立即发送 keepalive。
- 完整离线门：Gazelle-next Python 3.14.8，外部 `PYTHONPYCACHEPREFIX`；`python -m unittest discover -s tests -v` **700 tests / 35.275s / 0 skip**；`python -m compileall -q main.py gazelle tests tools`、`python main.py --help`、`python main.py --list-models`、`git diff --check` 均 exit 0。合成坏 MP4 的 moov 警告与 Git LF/CRLF 提示为非致命输出。
- 浏览器实测：临时服务 `127.0.0.1:8785`，只读旧试用集备份，用 `gazelle_runs/codex-round5/124-browser-labels.json` 保存。原生按住键 5 秒只产生一次事件，因此改为 5.039 秒连续发送 39 次方向键；自动保存间隔 **1.048912–1.064701 秒**。换段前后 pilot 的已看集合相同，共 40 步（0–6、8–40）；第 7 步未实际显示，没有伪造为已看。截图 `124-browser.jpg`，逐次落盘证据 `124-browser-writes.json`。浏览器与服务已关闭。
- 外部活动：仅本地浏览器/loopback HTTP、读既有 JPEG、写临时标签；无模型、外部网络、CUDA、FFmpeg 可执行程序、下载或环境改动。没有创建正式标签。
- 反证式复核：旧实现确实被新增两项回归拒绝；已看队列之外的类别/他人区间/备注保存仍立即执行；服务端原有完成与 revision 门未放宽。
- 自主决定（A 级）：关闭时直接启动同一保存处理函数，并将其完成纳入队列；请求仍用已知 revision，冲突按原规则报错，不猜测版本号。真实浏览器键盘保持动作不自动重复，以连续真实按键替代并记录实际频率。
- 范围外改动：无；测试仅补同模块 CLI/harness，指南为契约要求。
- 待 Claude 判断（B 级）：无新的协议决定。浏览器关闭时若碰到 revision 冲突，keepalive 不能保证最终写入；按契约保留冲突检查，新增测试证明的是立即发出请求，不宣称并发请求必成功。
- 待用户决定（C 级）：无。
- 未运行：本轮没有真实推理或正式标注；独立代码/浏览器验收交 Claude，用户独立 checkout 最终验收仍待完成。
- 状态标签：已实现、离线验证通过、临时浏览器实测通过、待独立审查。

## 3. 审查结论（Claude 追加）

### 2026-10-18 第 4 轮审查（Claude）

- **审查目标**：`2dc76be`（实现与报告），在 HEAD `5882791` 上审查。
- **独立复跑结果**：
  - 完整离线门 **668 tests，0 skip**；compileall、help、list-models、diff-check 均 exit 0。日志在仓库外 `gazelle_runs\claude-review-r4\gate\`。
  - **浏览器与服务端实测（Claude）**：用旧试用集与临时标签文件 `gazelle_runs\claude-review-r4\browser\labels_claude_r4.json`，端口 8792，测完已关闭。

    | 检查 | 结果 |
    | --- | --- |
    | 对从未看过的 `20261009_s04`，用页面令牌直接发一个同时带全部已看范围 [0, 300) 与 `finish=true` 的保存请求 | HTTP 400，原因为“完成要求事先已保存全部已看与类别”。同一请求里的已看范围与类别照常保存，`finished_at` 仍为空 ✓ |
    | 正常播放 pilot 约 19 秒（浏览器面板在前台），同时以 20 ms 间隔监视标签文件 | 播放期间共 20 次写盘，间隔 1.029 至 1.057 秒，即每秒最多一次 ✓；暂停后已看 95 步全部落盘 ✓ |

  - **暂停、换段、隐藏与关闭时立即写入**：由带伪时钟的单元测试覆盖。Codex 的浏览器记录中，暂停后 0.238 秒即写入一次。Claude 没有另做毫秒级复测。
- **独立代码审查**（只读子代理）：
  - 相关单测 77 项、两个 Node harness 通过。
  - 用不写文件的探针核对了以下各项：
    - 完成条件；
    - 保存不丢失、不乱序；
    - 降频期间完成按钮保持不可用；
    - 换段前先写入；
    - 命令行一行报错；
    - remux 与区域页面。
  - 未见 GZ-27 回归。
- **发现**：
  1. **必须修复（违背第 2 条的降频本意）**：`pause()` 每次都立即写入，而方向键、±0.2/±1 秒按钮、拖动时间轴、变化点按钮在未播放时也都会调用 `pause()`（`annotation_page.html:34-35`、`:53`、`:62`、`:66`）。
     - 探针：按住方向键以 10 Hz 逐步前进 2 秒，产生 19 次写盘，约每秒 10 次；同样 2 秒的播放只写 2 次。
     - 正式标注主要靠手动逐步，所以 Windows 替换文件失败的风险没有降下来。
  2. **应修**：
     - 关闭页面时，`keepalive` 的保存排在保存队列之后；有保存正在进行时，它可能来不及发出，最多丢失约 1 秒的已看进度，且用户已确认离开。
     - `labels validate` 读到顶层是 JSON 数组的文件时，仍会打印 traceback（`AttributeError` 未被捕获）。
     - `docs/usage/USAGE.md:768-776` 插入新句子时把原句拆开，出现“不接受 version 1”与“拒绝 version 1 并提示重新标注”两句重复。
  3. **小项**：带新已看范围和类别改动的完成请求，会先保存全部改动再返回 400。只有其他客户端可能发出这种请求，可以接受。
- **结论**：**changes-requested**。按下方第 2 轮要求修复，排在第 5 轮，正式标注之前完成。

### 第 2 轮要求（Claude，2026-10-18；第 5 轮执行）

1. 只在“正在播放”时，`pause()` 才立即写入。未播放时的手动逐步、跳转与变化点操作，产生的已看变化走与播放相同的降频队列，即每秒最多一次。暂停播放、换段、完成、隐藏与关闭仍立即写入。
2. 页面关闭（`beforeunload`）与隐藏（`visibilitychange`，或另加 `pagehide`）时：若有未写的已看进度，直接发出 `keepalive` 请求，不排在正在进行的保存之后；服务端照常按 revision 检查。
3. `labels validate` 捕获结构异常（顶层不是对象、嵌套过深等），输出一行错误、退出码 1。
4. 修正 `docs/usage/USAGE.md` 的重复句，并核对 USAGE_CN 对应段落。
5. **测试**：
   - Node harness 增加“未播放时按住方向键 2 秒，写盘不超过 3 次”；
   - 增加“保存进行中关闭页面仍发出 keepalive”；
   - 命令行增加顶层数组的用例。
6. **浏览器实测**（临时标签文件）：在未播放状态下连续按方向键约 5 秒，记录写盘间隔，应每秒最多一次；然后换段，确认已看进度没有丢失。
