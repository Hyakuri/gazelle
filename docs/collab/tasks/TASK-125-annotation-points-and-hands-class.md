# TASK-125：标注方案 r3——“手部/手中物体”类别与注视点

状态：第 3、4 轮 accepted（Claude 2026-10-30 第 7 轮审查、2026-10-31 第 8 轮审查，见 §3），正式标注可以开始；用户独立 checkout 验收待标注时完成
创建：2026-10-18（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：用户 2026-10-18 的目标说明（`docs/requirements/PROJECT_GOALS_CN.md` v3）与决定 D20；[验证集设计](../../design/VALIDATION_SET_DESIGN.md) §10（r3）。
授权：2026-10-14 本地修改与本地运算授权；作业数据只读；正式区域的类别重新导出以 Q-017 的确认为准，用户已于 2026-10-29 确认；第二次重新导出（只给手部类换色）以 Q-025 第 1 项为准，用户已于同日同意。

## 1. 契约

### 目标

让标注工具支持验证集设计 r3：

- 新增“手部/手中物体”类别；
- 在全局视图上点出注视位置；
- 使用标注 schema v3，并配套严格校验与完成规则。

完成后，用户按新方案开始 26 段正式标注。

### 必须实现

1. **类别规则**（设计 §10.2）：
   - 固定类别在用户画的目标区域之后，依次为 `hands_object`、`cell_other`、`away`、`absent`、`unknown`。
   - 按正式区域，键位为：1–4 目标区域，5 `hands_object`，6 `cell_other`，7 `away`，8 `absent`，0 `unknown`。
   - `default_classes.json` 与 `default_regions.json` 同步，中文名为“手部/手中物体”。颜色不与区域和其他类别冲突。
   - 区域工具导出时按新规则生成 `classes.json`。
2. **重新导出正式类别**：用户已于 2026-10-29 同意（Q-017），本轮执行。
   - 区域 JSON 不变，用区域工具的正式导出路径重新生成 `classes.json`、参考图与完成标记。
   - 旧的导出改名备份，并记录前后哈希。
   - 核对区域 JSON 的 SHA 前后相同。
3. **标注页面**：
   - **键位**：按新类别映射。
   - **加点**：在全局视图上单击，给当前步加一个注视点；同一步已有点则替换。坐标换算到全局代理帧（1920×1080）的归一化坐标，视图缩放时也要正确。
   - **显示**：全局视图上显示当前步的点，以及所在片段内其他点（淡色）；时间轴上标出点所在的步。
   - **删除**：删除当前步的点用独立的按钮与快捷键，不得与“删除变化点（Delete）”冲突。
   - **跳过**：“本片段跳过注视点”按钮与快捷键，切换当前片段的跳过标记。
   - **提示缺点**：需要点的片段缺点且未跳过时，状态栏提示“缺注视点”，时间轴上该片段加标记。
   - **限频**：同一片段内相邻两点至少相隔 5 步（1 秒），否则拒绝并提示。
   - **改类别时清理**：片段改为 `away`、`absent` 或 `unknown` 时，其中的点与跳过标记自动清除并提示，撤销时一起恢复。
   - **完成条件**：“本段完成”的启用条件增加一条，即所有需要点的片段都有点或跳过标记。TASK-138、TASK-124 的其余完成规则不变。
4. **服务端与 `labels.py`**：
   - schema version 3，每段增加 `points`（`{step, x, y}` 列表）与 `point_skips`（片段起始步列表）。
   - 保存时检查结构。严格校验按设计 §10.4；`--segment` 与命令行一行报错的行为不变。
   - 拒绝 version 2 文件，并提示用新工具重新标注。
   - 完成判断同样只认已保存的状态，与 TASK-124 一致。
5. **数据集**：
   - `sample_segments` 复制新的 `classes.json`，manifest 记录标注 schema 版本 3。
   - 若 TASK-140 第 2 轮已经生成 `roi_r2` 与 `roi_r2_trial`，按新类别文件重新生成，或只替换类别文件与 manifest，二者任选并记录。要求帧与片段选择不变。
6. **文档**：四份用户文档与两份中文指南（`ANNOTATION_GUIDE_CN.md`、`ROI_GUIDE_CN.md`）写明：
   - 新类别及其优先规则；
   - 注视点规则：必点、可跳过、额外点每秒最多一个、哪些类别不点；
   - 判断依据：眼睛优先于头部，头部优先于手部；
   - 快捷键。

   同时更新 `tests/test_usage_docs.py`。
7. **测试**（默认隔离）：
   - 类别规则与键位；
   - 点的添加、替换与删除，坐标归一化（含视图缩放）；
   - 限频；
   - 改类别时的清理与撤销；
   - 严格校验各条与完成条件；
   - 拒绝 version 2；
   - 重新导出时区域 JSON 不变、旧导出有备份；
   - Node harness 覆盖：单击加点、跳过、缺点提示、完成按钮条件。
8. **r3.1“画面外”标记**（设计 §10.8；用户 2026-10-29 已同意，Q-018）：
   - 对 `cell_other` 与 `hands_object` 片段，提供一个按键与按钮，把当前片段标为“画面外”，代替点注视点。按键不得与现有快捷键冲突，并写入文档。
   - `point_skips` 的每项改为 `{step, reason}`，`reason` 为 `unsure` 或 `out_of_view`。schema 版本仍为 3。
   - 严格校验：`out_of_view` 只能出现在上述两类片段。标为画面外的片段不再要求注视点，完成条件视为已处理。
   - 改类别时的清理与撤销规则同样适用于这一标记。
   - 测试与浏览器实测各增加一项：标一个画面外片段，并核对校验与完成条件。

### 非目标

- 不改区域多边形、5 Hz 时间轴、片段长度与抽样规则。
- 不做注意力热力图或任何模型（属于第 3 阶段）。
- 不创建正式 `labels.json`。

### 不可变约束

- AGENTS.md 的默认测试隔离；源目录只读。
- 正式区域多边形不变；正式类别只按第 2 条重新导出一次（Q-017 已确认），不做其他修改。
- TASK-138 与 TASK-124 建立的完整性规则不得削弱：只认已保存的已看范围、显式完成、降频写盘、`--segment`。

### 允许动作

- 修改 `tools/validation/**` 中与本任务相关的文件与对应测试、两个 Node harness。
- 更新四份用户文档的研究数据工具小节与 `tests/test_usage_docs.py`。
- 用旧试用集与临时 `--labels-path` 做浏览器实测；按第 2 条重新导出正式类别。
- 按协作方案 §4 提交、推送，并在 PR #6 发英中双语评论；问题处理按协作方案 §3.5。

### 禁止

- 协作方案 §3.5 的硬边界；修改环境；写入源目录；提交数据、媒体或标注。
- 修改正式区域多边形；创建正式 `labels.json`。

### 验收标准

1. 上述测试通过；完整离线门通过，无新增 skip；两个 Node harness 通过。
2. 浏览器实测（临时标签文件）：在 pilot 上标 30 秒，至少 3 个片段：
   - 1 个 `hands_object`；
   - 1 个标为跳过；
   - 1 个含额外点。

   然后检查：
   - `labels validate --segment 20260911_pilot` 在补齐前失败、补齐并确认完成后通过；
   - 把一个片段改为 `away` 后，其中的点被清除并有提示；
   - 播放与逐步时的写盘频率仍为每秒最多一次。
3. 正式类别重新导出（若已确认）：区域 JSON 的 SHA 不变，旧导出有备份，完成标记有效。
4. 四份用户文档与两份中文指南中英语义一致。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-125-pycache"
& $py -m unittest tests.test_validation_labels tests.test_validation_server tests.test_validation_roi tests.test_validation_sampling tests.test_usage_docs -v
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

- 需独立审查：是，涉及标注数据与评估协议。
- 需真实运行：浏览器实测，仅 CPU。
- 文档同步：需要。
- 依赖：Q-017（用户 2026-10-29 已确认 r3 细则）；排在 TASK-124 第 2 轮之后，因为改动同一组文件。

## 2. 实施报告（Codex 追加，不要修改上文）

### 第 5 轮实施报告（2026-10-29）

- 接手核对：STATE 授权第 5 轮依次 TASK-140、TASK-124、TASK-125；在前两项完成后沿用 `writer=codex`，主线程 Inline Execution，无子代理。采用 r3.1 的 `{step, reason}` 覆盖契约第 4 条的早期起点列表格式；不改契约正文与研究协议。
- 提交与推送：`daeebc9b7ec4777e4b9b2d8e32f3e87c8a97f44a` — `Add attention points and hands-object annotation contracts`，已正常推送到 `feature/stage2-correctness`。本报告与最终 STATE/文档基线另行提交；没有新分支、新 PR、force push 或 merge。
- 变更：新增 `hands_object`；正式四目标键位为 1–4、5 hands、6 other、7 away、8 absent、0 unknown。schema v3 的 points/skips 结构、有限归一化坐标、唯一步号、每片段 5 步间隔、原因/类别限制、完整覆盖和已保存完成门均在服务端检查。v1/v2 明确要求重新标注。页面支持缩放点选、替换、X 删除点、S 跳过、O 画面外、时间轴提示、自动清理与撤销；Delete 仍删除类别变化点。采样 manifest 新增 `annotation_schema_version=3`。
- 文件：`tools/validation/{labels.py,annotation_page.html,default_classes.json,default_regions.json,roi_regions.py,roi_page.html,render_roi_reference.py,sample_segments.py}`，相关 Python/Node 测试，四份英中用户文档与两份中文指南。按眼睛 > 头部 > 手部与手部类别优先规则同步；ROI_GUIDE 同步已实现的证据边界不确定区间说明。

#### 命令、结果与失败记录

所有 Python 使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`（3.14.8），`PYTHONPYCACHEPREFIX=$env:TEMP\gazelle-r5-pycache`，`PYTHONIOENCODING=utf-8`。日志位于仓库外 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\codex-round5`。

| 检查 | 命令/证据 | 结果 |
| --- | --- | --- |
| 针对性检查 | `python -m unittest tests.test_validation_labels tests.test_validation_points tests.test_validation_roi tests.test_validation_sampling tests.test_validation_server -v` | 36 tests / 2.843s / 0 skip，exit 0 |
| 最终完整离线门 | `python -m unittest discover -s tests -v`，`125-offline.log` | **708 tests / 30.244s / 0 skip**，exit 0 |
| 静态/入口 | `python -m compileall main.py gazelle tests tools`；`python main.py --help`；`python main.py --list-models` | 全部 exit 0 |
| 页面逻辑 | `node tests/roi_page_test.cjs`；`node tests/annotation_page_test.cjs` | 两项 exit 0；包含缩放/留白坐标、加点/替换/删除、跳过/画面外、缺点门、清理/撤销、合并片段限频、保存节流 |
| 数据集 | `python -m tools.validation.extract_frames --dataset-root ..\gazelle_validation\roi_r2_trial --validate-only`；同命令改为 `roi_r2` | 各 27 segments / 8100 frames / valid true，exit 0；完整代理/帧哈希复查，顺序执行 |
| 临时 pilot | `python -m tools.validation.labels validate --dataset-root ..\gazelle_validation\roi_r2_trial --labels-path ..\gazelle_runs\codex-round5\125-browser-labels.json --segment 20260911_pilot` | 完成前 exit 1 单行“Segment has not been completed”；实际观看并确认后 exit 0 |
| 正式结构 | `python -m tools.validation.labels validate --dataset-root ..\gazelle_validation\roi_r2 --labels-path ..\gazelle_runs\codex-round5\125-formal-empty-labels.json --allow-incomplete` | exit 0；新建的仓库外空 v3 测试文档，不是正式 labels，也不表示标注完成 |
| 文档/补丁 | `python -m tools.docs build`、`python -m tools.docs check`、`git diff --check`、`git diff --cached --check` | 最终均 exit 0；本轮结束另建立文档基线 |

- 反证式复核：先在旧实现观察 v3/coverage/UI/export/相邻同类拆段限频回归失败，再实现对应约束；日志 `125-red.log`、`125-ui-red.log`、`125-export-red.log`、`125-spacing-red.log` 保留。首次整组旧样例仍假定 v2、六目标与无点完成，出现 4 fail / 2 error；修正样例而未放宽新规则，第二次 36 项通过。首次暂存检查发现新测试末尾多余空行，删除后再次检查通过，未改测试逻辑。
- 非致命输出：合成坏 MP4 回归保留 OpenCV/libav 的 `moov atom not found`；Git 有 LF/CRLF 提示。没有新增 skip。
- 一次性外部更新脚本 `reexport_points.py` 已完成正式导出，随后因默认试用集原本没有参考图而 FileNotFoundError 中止；在任何数据集写入前停止。未重复正式导出，改由 `update_point_datasets.py` 续做元数据更新，并保留试用集 `default-trial` 来源与无参考图状态。首次浏览器审计脚本漏写 UTF-8 编码导致 cp932 解码失败；补显式编码后审计通过，原日志保留。浏览器能力查询的未绑定句柄失败未改变页面或配置；直接使用已有页面完成验证。

#### 正式导出与数据集

- 只调用一次正式 `render(..., backup_existing=True)` 路径；对应 CLI 为 `python -m tools.validation.render_roi_reference --regions-path <roi>/roi_regions.json --candidates <roi>/candidates.json --backup-existing`。旧类别、参考图、七张叠加图、完成标记全部改名保存在 `gazelle_data/workdata/roi/export-backup-20261029T105703379479Z`，逐文件核对备份哈希。`completed_exports()` 通过。
- 区域 JSON 前后 SHA 均为 `6511ff108c397e4d7dc474bddf6531810f505443f80cf8aca4967c8d4cddf0bb`。正式 classes 从 `ef5f351a94d5ee8aab365c68ce7fd318c03aa19a846e49c288899b812bf81c5f` 变为 `2871cdb85817a4c77f00c7640a95dd451afdc551504b540473e8c0d6b72ad2d8`；完成标记从 `7c88e9f1b5e667241bcf1580910e811f6fcd5822535cc675bccb67f16fdf96b2` 变为 `8ef3f24cc54e59000bca3e69bcb999e09fff1d39f18f757009e1e0b3d92ed70d`。参考图仍为 `bb88e34bb6bcd653aba27b21da5e32498a4e7383823d5cb38fde1fb9b1db59f6`，七张叠加图均逐字节相同。
- 数据集仅更新类别与 manifest（正式集同步复制相同参考图），旧文件改名为 `*.before-task125-20261029`。试用集保留三个默认目标，手部键 4，classes SHA `0767bad7b01ed1b73eb167b12a4d7857384c87b366562f62820225ce4f0a72d9`；正式集四目标九类别，手部键 5。两份 manifest 的 `segments` 全结构完全相同，未重新抽样、抽帧或改变来源。
- 最终 manifest SHA：trial `45dc96fd8093d72b34c12510979245bde9541f494e833fb00ca842814353958f`；formal `7cb207798dc284e0c11f0f6e1c36000ec5273c7b38d7987b55cc706efd8634ae`。完整前后哈希记录 `125-export-and-datasets.json`。两个根目录均没有 `labels.json`；此前 TASK-140 空 v2 检查文件仅保留历史证据，未冒充当前 v3 校验。

#### 真实浏览器与外部活动

- `points_browser_server.py` 运行现有 AnnotationApplication/HTTP handler，仅在测试包装层记录每次成功写入，绑定 `127.0.0.1:8785`。临时 `125-browser-labels.json`：pilot 0–10 s hands_object（step 0、5 两点），10–20 s target + unsure，20–30 s cell_other + out_of_view，30–60 s unknown。实际点选坐标约 (0.25, 0.5)，和缩放后的画面换算一致。
- 改第一片段为 away，页面提示自动清除 2 点；撤销恢复。连续播放实际显示全部 300 步，按钮随后启用；确认完成、换段、返回后保持“已确认完成”。严格 CLI 完成前失败、完成后通过。截图 `125-browser-proof.jpg`，结构与时序证据 `125-browser-audit.json`、`125-browser-writes.json`。
- 播放常规写盘间隔 **1.053244–1.093406 秒**；终点暂停强制 flush 的末次间隔 **0.799097 秒**单列。另一段未播放时 5.024 秒内发送 41 次方向键，常规间隔 **1.059217–1.074587 秒**；切段保留实际显示的 0–41 共 42 步。没有把尚未显示的步算作已看。
- 真实活动仅 CPU、现有 Pillow/OpenCV、读候选图/JPEG/代理哈希、本地 loopback HTTP 与仓库外导出/临时标签写入。无真实模型、Hub、下载、新模型缓存、CUDA 推理、FFmpeg 可执行程序、依赖安装或环境修改。两次只读完整性复查顺序运行，普通进程优先级；前面的代理/抽帧长任务按既有低优先级方案执行。服务与本轮校验进程均已退出；临时测试标签是功能验证样例，不是科学标注。

#### 决定、范围与待验收

- 自主决定（A 级）：采用 X/S/O 独立快捷键；新增固定类后目标上限从六个减为五个以保留 1–9 键位；保留试用集默认来源、正式集区域来源；不重抽帧，仅更新元数据。相邻同类区间必须合并以防拆段绕过 5 步限制；类别合并后按时间保留较早点、清理失效起点标记并提示，可整体撤销。契约未规定点与 skip 互斥，未额外禁止二者共存。增加显式 `--backup-existing`，保持原导出默认行为。
- 范围外改动：无。没有 TASK-101、TASK-150 或阶段 3 实施；没有修改原始视频、正式多边形或正式标签。仓库既有忽略目录 models/、字节码等保留，不暂存。
- 待 Claude 判断（B 级）：独立复核上述 A 级决定、r3/r3.1 语义、真实试用与导出/数据集哈希；TASK-140 同步与 TASK-124 关闭期间 revision 冲突边界仍按各自报告审查。没有新增阻塞性契约问题。
- 待用户决定（C 级）：无新增。Q-023 等既有问题不由本任务解决。
- 未运行的检查、限制：没有正式科学标注、一致性复标、真实模型精度评估或用户独立 checkout 验收。原子备份保护已完成文件；中断导出需检查备份和完成标记后恢复。浏览器关闭网络中断不保证未送达请求必然落盘，不能把 Node keepalive 检查当作无条件可靠交付。
- 状态标签：**已实施、已静态检查、已离线验证、已实际运行；ready-for-review；未独立验收。**
- 双语发布报告：[PR #6 / TASK-125](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6495066389)。

### 第 6 轮实施报告：第 2 轮修订（2026-10-29）

- **实施提交**：`ac89a66f726bc3a2efcfa777d0c8910010d7834b` — `Enforce exclusive annotation points and safe input handling`，已正常推送现有分支与 draft PR #6。接手基线 `f14b36b`；先提交并推送 Claude 协调文档 `60464e2a335df4cca3d41d8ad79b4958204c77bc` — `Record coordinator updates`，按 STATE 用 `gh pr edit 6 --repo Hyakuri/gazelle --body-file docs/collab/STAGE2_PR_BODY.md` 同步正文。主线程 Inline Execution，无子代理、新分支或新 PR。
- **状态**：实现、静态检查、离线验证及下述可见浏览器检查完成，提交供独立审查。第 9 条中的真实 `visibilitychange` 和真实按住重复事件未验证，不能算全部浏览器验收通过；具体障碍与建议见 B 级。正式标注继续暂停，未开始第 7 轮。
- **修复**：保存与严格校验均拒绝同一类别片段的 points/skips 并存；已有标记时加点被拒并说明取消键；S/O 清除整段点、显示数量，撤销恢复；合并保留点并清理冲突标记。Ctrl/Meta/Alt 组合键保留浏览器行为（Ctrl/Cmd+Z 除外），非方向快捷键忽略重复事件。隐藏按正常保存队列，pagehide/beforeunload 仍直接 keepalive；版本冲突保护保留。共享 LabelStore 在读取标签前要求整数 schema 3。慢帧就绪后等满一个步长；左侧视图点选给出提示；旧标签启动服务时单行报错。
- **文档**：四份英中用户文档与两份中文指南同步默认点位、互斥、整段画面外/部分可见/拿不准规则、区域内桌面或物体的分类、快捷键、版本门与保存边界；USAGE 两语重复的重新标注说明已去掉。未修改受控设计与审查正文。

#### 环境、命令与证据

所有 Python 使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`（3.14.8），`PYTHONPYCACHEPREFIX=$env:TEMP\gazelle-r6-pycache`、`PYTHONIOENCODING=utf-8`。日志与临时标签在仓库外 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\codex-round6`。

- 预检：默认 cwd/Git 根目录均为 Claude_Code 新仓库。普通 `codexsandboxonline` 上下文的仓库、三个派生目录与 TEMP 创建/读写/删除探针通过；只读列出原始目录的九次录制，不运行 inventory。项目 TOML 可解析，三个 writable roots 与 network_access=true；以实际读写和 `git ls-remote` 结果单独确认生效能力。普通 gh 认证仍无效，按既有限定批准在 yun 上下文验证 Hyakuri 认证和 draft PR，并仅在那里运行 Git 写入/GitHub 命令；没有将该例外记作普通 gh 通过。
- FFmpeg/ffprobe 仅运行版本查询（2025-03-31-git-35c091f4b7）；GPU 仅查询：RTX 4080 SUPER，driver 617.14，2500/16376 MiB。未修改环境、配置或凭据。

| 检查 | 命令或日志 | 结果 |
| --- | --- | --- |
| 修复前反证 | `python -m unittest tests.test_validation_points -v`；`points-red.log` | 14 tests，7 failures / 1 error：互斥、版本门及旧标签启动错误路径被捕获；未放宽断言 |
| 页面反证 | `node tests/annotation_page_test.cjs`；`ui-red.log` | exit 1：已有标记仍可加点 |
| 针对性检查 | `python -m unittest tests.test_validation_points tests.test_validation_labels tests.test_validation_server -v`；`points-green.log` | 24 tests / 0.899s / 0 skip，exit 0 |
| 完整离线门 | `python -m unittest discover -s tests -v`；`offline.log` | **715 tests / 19.108s / 0 skip，exit 0** |
| 静态与入口 | `python -m compileall main.py gazelle tests tools`；`python main.py --help`；`python main.py --list-models` | 全部 exit 0，日志 `compileall.log`、`help.log`、`models.log` |
| 两个页面 harness | `node tests/annotation_page_test.cjs`；`node tests/roi_page_test.cjs` | 全部 exit 0；`annotation-node.log`、`roi-node.log` |
| pilot 严格校验 | `python -m tools.validation.labels validate --dataset-root ..\gazelle_validation\roi_r2 --labels-path ..\gazelle_runs\codex-round6\browser-labels.json --segment 20260911_pilot` | 完成前 exit 1 / 一行未完成错误；确认后 exit 0。`pilot-before.log`、`pilot-after.log` |
| 文档与补丁 | `python -m tools.docs build`；`python -m tools.docs check`；`git diff --check`；`git diff --cached --check` | exit 0；结束按协作流程另建基线 |
| 外部结果只读审计 | `python ..\gazelle_runs\codex-round6\audit.py` | exit 0；`browser-audit.json`，94 次成功保存连续 revision，无冲突 |

- 服务端新增单规则测试：区域类 out_of_view；away/absent/unknown 中的点；非起点 skip；points+unsure、points+out_of_view；其余条件先验证合法。另检验 schema 门不创建文件、不改已有标签、CLI 单行错误与启动失败不监听端口。旧 3000 层 JSON 用例更名为顶层数组检查，**不再声称它触发 RecursionError**。
- Node 使用真实键盘处理入口测 Delete、片段中间 S、Ctrl/Meta/Alt、repeat、S/O 清点与撤销、标记后拒点、合并清理和仅画面外可完成。fake fetch 独立维护服务端 revision，检查 points/skips 字段；隐藏遇到在途保存按序完成、不失败；pagehide/beforeunload 不等待队列，故意制造的关闭竞争仍因 revision 被拒。慢帧加载后 25/199 ms 不前进，满 200 ms 才前进。
- 非致命输出：坏 MP4 隔离用例的 `moov atom not found` 和 Git LF/CRLF 提示。起初使用短任务文件名读取失败，随后使用 STATE 完整路径；浏览器变量/只读 DOM 能力查询失败均未改页面状态。无新增 skip，无依赖安装。

#### 真实浏览器与数据保护

- 测试服务 `browser_server.py` 绑定 `127.0.0.1:8786`，复用现有 AnnotationApplication/HTTP handler，使用正式 `roi_r2` 只读数据与外部临时 `browser-labels.json`。包装仅记录保存、按测试标记延迟一次响应、增加键盘/可见性日志监听；没有合成 UI 事件、注入标注状态、替换 requestAnimationFrame 或修改生产 HTML 文件以通过浏览器验收。
- 可见 IAB 中：pilot 0–10 s 为 hands_object，step 0/5 两点；10–20 s 为 item_box + unsure；20–30 s 为 cell_other + out_of_view；30–60 s 为 unknown。S 清除两点并提示，标记后单击被拒，Ctrl+Z 恢复两点与无标记；Ctrl+S、Alt+O 不改变标签。改为 away 清除两点并提示，撤销恢复。
- 保持真实绘制，实际显示 **300/300 步** 后按钮才启用，确认完成后切段、返回仍显示已确认完成；严格 CLI 前失败后通过。`browser-proof.png` 为返回后的截图。播放 60 次常规保存间隔 **1.039743–1.068478 s**；非播放连续逐步的 6 次常规保存间隔 **1.044421–1.061257 s**，实际显示 41 步。终点、编辑、切段等强制保存另计，不混入常规间隔。
- 两次故意延迟约 6 秒的请求均成功，后续 revision 连续，页面没有失败。但 IAB 隐藏面板及切换临时空白标签页都没有产生 visibilitychange，因此这**不能证明实际隐藏路径通过**。按住 S 1200 ms 只产生一次 repeat=false，不能证明真实键盘重复通过。事件见 `browser-events.json`。尝试访问现有 Chrome 项目窗口以补测时，Computer Use 应用访问审批超时；没有对 Chrome 执行输入。未绕过这些限制。
- `readonly-before.json` 与 `browser-audit.json` 对照八项只读 SHA 全相同：正式区域、类别、参考图、完成标记，以及两个数据集的 manifest/classes。区域仍为 `6511ff108c397e4d7dc474bddf6531810f505443f80cf8aca4967c8d4cddf0bb`；正式类别仍为 `2871cdb85817a4c77f00c7640a95dd451afdc551504b540473e8c0d6b72ad2d8`。两个数据集均没有正式 labels.json。未重抽样、重抽帧或重新导出；本轮没有复算全部图像哈希，上一轮独立检查属于历史证据。
- 真实活动限 CPU 单元测试/JSON/哈希/JPEG 读取、本机 loopback HTTP、临时标签与已授权 GitHub 交付。无模型、CUDA 推理、Hub/权重下载、模型缓存更新、FFmpeg 转码或 Conda 变更，服务仅监听本机地址。临时浏览器页已关闭，服务已终止且 8786 无监听。测试输出保留仓库外供审查；既有忽略目录未删除或暂存。

#### 自主决定（A 级）

- 将版本门放在 LabelStore，供编辑器和 CLI 共用，在标签读写前拒绝；整数 3 才合法，缺失、2、字符串和浮点数均拒绝。两入口都有回归覆盖。
- 采用契约第 7 条三个小项；不扩展到跨磁盘导出修复。删除原测试名对 RecursionError 覆盖的误称，保留顶层非对象回归。
- Q-025 第 1 项仍待用户，按第 8 条明确分支跳过换色、正式重导出和数据集更新；不是把未批准的动作当成通过。

#### 范围外改动

无。没有 TASK-101、TASK-150、TASK-140 第 3 轮、阶段 3、Multi-Pose、GitHub Actions 或研究协议变更。

#### 待 Claude 判断（B 级）

- 复核实现提交、715 项离线门、两个 harness 和 A 级决定。**第 9 条验收尚有两项缺口**：真实隐藏事件发生于在途保存时的行为、真实键盘按住产生 repeat=true 的行为。IAB 未产生相应事件，桌面浏览器访问审批超时；没有修改验收标准或用 Node 证据替代实测。推荐 Claude 在可产生真实事件的可见浏览器、临时标签中补测后再接受 TASK-125，并继续保持正式标注暂停。未暂定接受，也未开始后续任务。
- 浏览器关闭/网络中断的未送达请求仍不保证落盘；直接 keepalive 竞争可能被服务端版本门拒绝。该边界保留并同步文档。

#### 待用户决定（C 级）

无新增。Q-025 的颜色偏好仍按现有表等待，未重复请求授权。用户独立 checkout 验收、正式科学标注和模型精度评估均未执行。

### 第 7 轮实施报告：第 3 轮修订（2026-10-30，Asia/Tokyo）

- **提交**：协调文档 `36aa643b641a45e7544f1e7e81371d86d4639509`（`Record coordinator updates`）；实现 `806068cc4f255ccc6673c8c0350ae26aa9e2eb8b`（`Fix annotation shortcut repeats and apply approved hands color`），均已推送 `feature/stage2-correctness`。PR #6 正文已按来源文件同步，draft、标题、base 保持原状。
- **范围与状态**：只实施本节下方第 3 轮要求 1–7；主线程 Inline Execution，无子代理。已实施、已静态检查、已离线验证、已实际运行下述数据与浏览器检查；**ready-for-review，未独立验收**。真实按住重复的浏览器验证仍待 Claude，不能宣布全部浏览器验收通过。正式标注继续暂停；未做第 8 轮或阶段 3。
- **证据根目录**：`C:\Users\yun\Documents\Claude_Code\gazelle_runs\codex-round7\`，以下日志和脚本均相对此目录；没有上传媒体、标签、原始/派生数据或缓存。UTC 自动备份名仍为 20261029，报告日期采用 JST 2026-10-30。

#### 改动与预检

- 重复的页面快捷键先阻止浏览器默认动作再返回，方向键保留重复。Ctrl/Cmd+Z 必须不带 Shift、Alt；重复撤销阻止默认动作且不再次撤销。未采用按钮失焦，不改变原有焦点导航。
- Node 补充 S/O 取消及撤销恢复、重复事件 default prevention、首次生效后保持不变、Ctrl/Meta 的 Shift/Alt/repeat 组合、INPUT/TEXTAREA/SELECT 焦点隔离。文档测试防止两份 USAGE 重复说明旧版本重新标注；默认类别测试核对新颜色。
- 四份英中用户文档及两份中文指南同步撤销范围、没有重做、按住只算一次及 `#b6ff00`；标注指南 §5 补互斥检查。删除两份 USAGE 中未覆盖的极深 JSON 一行报错保证，不修改解析器或既有结构校验。
- 新目录 cwd/Git root 均为 `C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle`，接手 HEAD `e605687ba9965bcf63f0825ce73689398978ce3e`，`writer=none/next_actor=codex`。普通 `codexsandboxonline` 上仓库、三个外部输出目录及 TEMP 的隔离目录/文件创建、读取、删除全部通过；原始数据只读列出九个录制目录，没有重跑 inventory。
- `Gazelle-next` Python 3.14.8；FFmpeg/ffprobe 仅版本查询（`2025-03-31-git-35c091f4b7-full_build-www.gyan.dev`）；RTX 4080 SUPER 驱动 617.14，3051/16376 MiB，仅记录。项目 TOML 解析确认三个可写目录和网络设置，普通实际访问探针另行验证，未用提权成功冒充普通权限通过。
- 普通 Git 远端读取成功；普通 `gh` 认证仍失败，按 2026-10-16 常设批准仅 Git/GitHub 命令使用 `yun` 上下文，认证 Hyakuri 有效，PR #6 为本分支的 open draft。未改配置、凭证、Conda 或依赖。

#### 命令、结果、失败与跳过

Python 均为 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`；`PYTHONPYCACHEPREFIX=%TEMP%\gazelle-r7-pycache`、`PYTHONIOENCODING=utf-8`。Node 为现有 v24.19.0。长 CPU/文件校验命令以 BelowNormal 优先级运行。

| 命令 | 结果与证据 |
| --- | --- |
| `node tests/annotation_page_test.cjs`（先测试后修复） | 原实现 exit 1：重复事件未 preventDefault；`offline-red.log`。修复后通过；`annotation-final.log` |
| `python -m unittest tests.test_validation_points tests.test_usage_docs -v` | 聚焦 36 tests 通过；新增颜色/文档断言在修改前失败；`focused.log`、`docs-color-red.log` |
| `python -m unittest tests.test_validation_points.PointLabelsTest.test_export_cli_parses_backup_flag_before_rendering -v` | 导出 CLI 的 `%` 帮助文本在 Python 3.14 报错，修复前 exit 1，修复后 exit 0；`export-cli-red.log`、`export-cli-green.log` |
| `python -m compileall main.py gazelle tests tools/validation` | exit 0；`compileall-final.log` |
| `python -m unittest discover -s tests -v` | **717 tests / 32.143s / 0 skip / exit 0**；`unittest-final.log`。此前 716 项为加入导出 CLI 回归测试前的证据，不冒充最终门 |
| `python main.py --help`、`python main.py --list-models` | exit 0；`help.log`、`list-models.log`；未构造模型 |
| `node tests/roi_page_test.cjs` | exit 0；`roi-page-final.log` |
| `node undo-negative.cjs shift`、`node undo-negative.cjs repeat` | 两项仅在内存中恢复旧撤销缺陷，均被新增断言捕获（预期 exit 1）；仓库文件不变 |
| `python color_exports.py prepare` | 校验两集全部 16,200 帧哈希，记录旧元数据、导出与备份列表；计算 13 色 CIE76；exit 0 |
| `python -m tools.validation.render_roi_reference --regions-path ..\gazelle_data\workdata\roi\roi_regions.json --candidates ..\gazelle_data\workdata\roi\candidates.json --backup-existing` | 第一次在 argparse 构造阶段失败，**没有导出或改写**；核对全部哈希与备份列表不变后修复 CLI。随后唯一一次实际导出成功，8 张 PNG 与旧文件逐字节一致；`export.log`、`export-completed.log` |
| `python color_exports.py update-datasets` | 先核对区域、候选清单、8 张 PNG、旧导出备份及颜色唯一差异，再改两个数据集的类别和 manifest；exit 0 |
| `python -m tools.validation.extract_frames --dataset-root ..\gazelle_validation\roi_r2 --validate-only` | 27 segments / 8100 frames / valid true / exit 0；`validate-roi_r2.log` |
| 同上，`--dataset-root ..\gazelle_validation\roi_r2_trial` | 27 segments / 8100 frames / valid true / exit 0；`validate-roi_r2_trial.log` |
| `python -m tools.validation.labels validate --dataset-root ..\gazelle_validation\roi_r2 --labels-path ..\gazelle_runs\codex-round7\browser\green.json --allow-incomplete` | 27 段草稿结构通过，exit 0；仅临时标签，**不是正式完成验收** |
| `python audit.py` | 正式元数据与本轮导出后哈希一致、两集无 labels.json、7 项内置浏览器检查通过、8797/8798 无监听、Edge 临时配置清理；exit 0 |
| `python -m tools.docs build`、`python -m tools.docs check`、`git diff --check` | 通过；报告/STATE 变动后再次生成，交接执行本轮 snapshot |

- 测试辅助脚本的首次生效断言最初在第 5 步测试 Delete，但那里没有类别变化点；改为第 0 步后通过，没有放宽生产逻辑。一次写错 Node 文件名 `roi_editor_test.cjs` 导致 MODULE_NOT_FOUND；改用仓库实际 `roi_page_test.cjs` 后通过，原日志保留。
- `rg` 对 PowerShell 未展开的文件通配路径报错后改用明确路径。非致命输出为坏 MP4 隔离用例的 `moov atom not found` 和 Git LF/CRLF 提示。无新增 skip，无未授权安装。
- 未运行真实模型/CUDA/MediaPipe 推理、FFmpeg 转码、下载、训练或正式实验；未重复第 6 轮已经由 Claude 完成的完整 pilot/隐藏页面/慢帧验收。真实按住重复的浏览器检查受下述 B 级问题影响。

#### 一次正式导出与两个数据集

- 旧导出完整改名至 `gazelle_data\workdata\roi\export-backup-20261029T152657019554Z`，备份各文件哈希与导出前一致。导出目录及移动目标均先 resolve 并确认在指定 ROI 根目录内。
- 两个数据集分别保留 `classes.json.before-task125-r3-20261030` 与 `manifest.json.before-task125-r3-20261030`，备份哈希与旧文件一致。只改手部类颜色和 manifest 的 `classes_sha256`；27 段定义、所有帧、采样、版本、来源字段不变。试用集继续使用 default-trial，无新增参考图。
- 原区域多边形与颜色完全不改；参考图及 7 张叠加图字节不变。完整前后及备份哈希在 `before-export.json`、`after-export.json`、`final-audit.json`，这些外部证据没有上传 Git。

| 文件 | 导出前 SHA-256 | 导出后 SHA-256 |
| --- | --- | --- |
| `roi/roi_regions.json` | `6511ff108c397e4d7dc474bddf6531810f505443f80cf8aca4967c8d4cddf0bb` | 不变 |
| `roi/roi_reference.png`（数据集内副本亦不变） | `bb88e34bb6bcd653aba27b21da5e32498a4e7383823d5cb38fde1fb9b1db59f6` | 不变 |
| `roi/classes.json` 与 `roi_r2/classes.json` | `2871cdb85817a4c77f00c7640a95dd451afdc551504b540473e8c0d6b72ad2d8` | `79a85dabac2f170be4d92be2d1cc44cf28b99c9cdbb7942cddb1d9d6cf616aa7` |
| `roi/roi_regions.complete.json` | `8ef3f24cc54e59000bca3e69bcb999e09fff1d39f18f757009e1e0b3d92ed70d` | `153f4b254729f3f058294e167ea14479b9c88546769f758bd648c4a5dbc9a9cd` |
| `roi_r2/manifest.json` | `7cb207798dc284e0c11f0f6e1c36000ec5273c7b38d7987b55cc706efd8634ae` | `cce3365003c4b0e758348280e484364bd4f9fee83a3808d6ac64ca6838d207af` |
| `roi_r2_trial/classes.json` | `0767bad7b01ed1b73eb167b12a4d7857384c87b366562f62820225ce4f0a72d9` | `3d1056b1d2167c28a22b8301dc9ab4f1deb9f406ace1eda5e89a24a96b2d9113` |
| `roi_r2_trial/manifest.json` | `45dc96fd8093d72b34c12510979245bde9541f494e833fb00ca842814353958f` | `916bcb6f025c62d8626b8210dd459345b75667c2f5c62f4f2d5bf3d6a0ee5b1e` |

CIE76 由 sRGB 线性化、D65 XYZ/CIELAB 和 Lab 欧氏距离独立计算；结果保留两位，完整数值在 `color-differences.json`。以下覆盖全部正式类别、默认类别及调色板的 13 个其他不同颜色。

| 颜色 | 对应类别/用途 | 与 `#b6ff00` 的 CIE76 |
| --- | --- | --- |
| `#d4ac0d` | 正式 item_box；调色板 | 58.02 |
| `#16a085` | 正式 work_area_1；调色板 | 91.19 |
| `#e84393` | 正式 item_area_2；调色板 | 157.19 |
| `#34495e` | 正式 finish_area；调色板 | 130.18 |
| `#9b59b6` | 正式/默认 cell_other；默认 work_cell | 163.62 |
| `#c0392b` | 正式/默认 away | 123.90 |
| `#7f8c8d` | 正式/默认 absent | 107.62 |
| `#bdc3c7` | 正式/默认 unknown | 104.64 |
| `#e67e22` | 默认 pick_right | 93.21 |
| `#2980b9` | 默认 work_front | 139.77 |
| `#27ae60` | 默认 place_left | 65.59 |
| `#6c5ce7` | 调色板 | 188.29 |
| `#00b8d9` | 调色板 | 120.80 |

新色最小 **58.0235**（对 `#d4ac0d`），其余颜色两两最小 **21.4303**（`#7f8c8d` 对 `#bdc3c7`），满足契约的 58.0/21.4 预期与下限。

#### 浏览器、活动与清理

- 复制 Claude 的临时 Edge 辅助脚本到 `browser/`，改用端口 8797/8798、临时 labels、一次性配置目录。独立 Edge 155.0.4283.62 的 `Browser.getVersion` 可读，但页面控制连接关闭（CDP 1006，诊断最终停在 `Page.enable`）。测试未达到注入真实输入阶段，**没有有效的 Edge 红/绿结果**。换用已有 WebSocket 客户端、禁止测试浏览器 GPU 呈现、使用初始空白目标，仍未解决。中间的辅助脚本导出名称错误已修正，无生产改动或依赖安装。日志 `browser/red*.log`、`probe*.log` 保留。
- 用内置浏览器访问同一真实服务（`127.0.0.1:8798`），正式数据只读、外部 `browser/green.json` 临时标签。未替换 requestAnimationFrame，未注入标注状态或合成 keydown；通过支持的点击/按键 API 操作。
- `browser/iab-results.json` 的 **7 项通过**：Ctrl+Shift/Alt+Z 无改动；Cmd+Shift/Alt+Z 无改动；普通 Ctrl+Z 只撤销最后类别；S 与 O 各自创建/取消标记；撤销按钮有焦点时内置浏览器长按空格不改类别/标记；新手部色同时显示于类别按钮与时间轴。按钮内联色为 `#b6ff00`，时间轴为 `rgb(182, 255, 0)`；`browser/color-proof.png` 只截取类别控件，不含视频。
- **长按一项只证明该次界面结果，不证明真实 repeat=true**。Node 覆盖重复处理与默认阻止，不能替代真实浏览器验收。临时 pilot 未完成，只做草稿校验；保存 13 次，无正式标签。
- 实际活动：CPU JSON/哈希、Pillow PNG 导出、OpenCV JPEG 校验、本机 HTTP/浏览器呈现、GitHub 读取与发布；GPU/FFmpeg/ffprobe 仅预检查询，无模型推理、Hub/模型下载或模型缓存更新。浏览器临时配置/缓存确实创建，随后清理；不将“无模型 GPU 推理”扩展成浏览器绝无 GPU 呈现。
- 页面已关闭，两个服务已停止（停止进程 exit 1 为主动中断），8797/8798 无监听；临时 Edge profile 全清理。保留外部日志和临时标签供复核，保留仓库原有忽略目录，不清理未知本地文件。

#### 自主决定（A 级）

- 修复默认动作顺序即可保留焦点，不采用可选 blur；输入框与组合键仍优先隔离。
- 按契约允许的两选一删除极深 JSON 文档保证，保留已有结构测试，不扩展解析协议。
- 正式命令暴露 Python 3.14 argparse 对 `%` 的检查；最小修复为帮助字符串 `0.5%%`，显示仍为 `0.5%`。先以 mocked render 重现，再修复；核实零正式改动后才进行唯一一次实际导出。区域阈值与导出语义不变。
- Edge 能力失败不扩大权限、不修改配置，继续其余工作，以内置浏览器完成可验证的部分并如实提交 B 级待复测。

#### 范围外改动

- `tools/validation/render_roi_reference.py` 的一处 argparse 帮助转义：第 3 轮未单列此代码修复，但它直接阻塞授权的正式 CLI 导出。相邻回归测试在本轮已涉及的 `tests/test_validation_points.py`；没有扩展其他任务或公共协议。

#### 待 Claude 判断（B 级）

- **真实按住重复验收未完成**：证据与尝试见上；没有确认 Edge 连接关闭的根因，不把它推断为业务代码故障。推荐 Claude 按 STATE 原计划，在自己的已验证环境、新端口/临时标签上复跑焦点空格、连续 S/O/X/Delete/数字及 Ctrl/Cmd+Z，确认 repeat=true 时默认动作被阻止、只生效一次；并复核 Shift/Alt、箭头与新颜色。利益是沿用已成功的真实事件路径；代价是本轮不能给出全部浏览器验收通过的结论。未临时扩大执行权限或恢复正式标注。
- 请独立复核本轮唯一实际导出、所有备份与哈希，以及 argparse 的 A 级兼容性修复；用户独立 checkout 最终验收尚未进行。

#### 待用户决定（C 级）

- 无。Q-025 已授权并完成换色；本轮不要求新的环境或权限变更。

### 第 8 轮 / 第 4 轮要求实施报告（Codex，2026-10-31）

- 接手：实时 STATE 为 `writer=none / next_actor=codex`，确认后取得写者；协调文档先独立提交 `acae8a12bba50c5df57ffd6e8c8480f264d082cd` 并推送，PR #6 正文同步。实现提交 `980d8ee0005abb6154da31846463669e3baaa551` — `Release annotation control focus after mouse interaction` 已推送当前分支。
- 实现：主鼠标指针操作后的 range/select 在 change 时释放焦点；range 在 pointerup 时也释放，覆盖未改变值及拖出边界。按钮在鼠标 click 后释放。keydown 清除鼠标来源记录，Tab、键盘操作与备注文本框保留焦点。原快捷键输入隔离、重复处理、schema 和标签语义不变。
- 改动：`annotation_page.html`、Node harness、文档测试，以及四份用户文档和两份中文指南，共 9 文件。未改任何正式类别、区域、manifest、帧或标签；未读取用户 `roi_r2/labels.json` 或其备份。
- 验证（`Gazelle-next` Python 3.14.8；字节码在 TEMP）：先加回归测试，原代码 Node 失败于“鼠标改变控件后释放焦点”，修复后通过。最终 `python -m compileall main.py gazelle tests tools`、`python -m unittest discover -s tests -v`（**717 tests / 31.052s / 0 skip**）、`python main.py --help`、`python main.py --list-models`、`node tests/annotation_page_test.cjs`、`node tests/roi_page_test.cjs`、`python -m tools.docs build`、`python -m tools.docs check`、`git diff --check` 全部 exit 0。非致命输出：无效临时 MP4 测试的 `moov atom not found`；Git LF/CRLF 提示。逐命令日志和时间见仓库外 `gazelle_runs/codex-round8/task125-gate.json`。
- 浏览器：未替换的 `annotate_server`，端口 8808；`--dataset-root gazelle_validation/roi_r2 --labels-path gazelle_runs/codex-round8/task125-browser.json --annotator codex-round8-test-only`。内置浏览器实测：鼠标选 0.5× 后焦点为 BODY、空格播放；换片段后方向键单步且片段不变；拖滑块后数字键标注；点击撤销后 Enter 不再撤销；Tab/Shift+Tab 到速度控件并用方向键改变值后保留焦点；备注框输入保留焦点。换段尚在异步加载时第一次方向键未移动，加载完成后通过，原帧就绪保护保持。证据 `task125-browser-checks.json`、`task125-controls.png` 留在上述仓库外目录；页面关闭，服务主动 Ctrl+C 停止（exit 1）。
- 实际活动：CPU 离线测试、本机 HTTP、临时标签读写、GitHub 提交推送与报告；无模型构造/推理、下载、CUDA 推理、FFmpeg 转码、Conda/全局配置修改。FFmpeg/ffprobe、GPU 只在预检查询。普通权限的仓库/三个外部目录/TEMP 创建删除探针通过；普通 gh 认证仍无效，Git/GitHub 按已有批准在 yun 上下文执行，二者分开记录。
- 反证式复核：鼠标来源与键盘来源分开；新增测试覆盖静态/动态按钮、鼠标转键盘、取消指针、未改变值的滑块及边界外释放。未触碰正式数据，也没有以 mock 代替真实浏览器结果。
- 自主决定（A 级）：使用委托 pointer/change/click 事件覆盖动态生成的按钮，避免逐项绑定；range 补 pointerup，键盘任何 keydown 撤销鼠标来源；只改变焦点管理。
- 范围外改动：无。
- 待 Claude 判断（B 级）：无设计阻塞。独立验收仍待 Claude 按契约在 Edge 运行 E1–E3，并可用任务开始页面作负对照；内置浏览器结果不等同独立验收。
- 待用户决定（C 级）：无。状态：**ready-for-review / Codex verified**；继续本轮 TASK-101，不结束第 8 轮。

## 3. 审查结论（Claude 追加）

### 2026-10-29 第 5 轮审查（Claude）

- **审查目标**：`daeebc9`（实现）与 `f14b36b`（报告与交接），在 HEAD `f14b36b` 上审查。
- **独立复跑**：完整离线门 708 tests、0 skip；两个 Node harness 通过。
- **浏览器实测（Claude）**：设置同 TASK-124 §3（正式 `roi_r2` 只读、临时标签、计时器代替 `requestAnimationFrame`）。在 pilot 上：

  | 检查 | 结果 |
  | --- | --- |
  | 正式类别 | 9 类：1–4 为你画的 4 个区域，5 手部/手中物体，6 工作区内其他，7 工作区外，8 不在岗，0 无法判断；区域参考图可以展开 ✓ |
  | 加点 | 全局视图缩放为 0.507 倍时，在 (0.25, 0.5) 处单击，保存为 (0.2495, 0.4990) ✓；同一步再点为替换 ✓；X 只删当前步的点，Ctrl+Z 恢复 ✓ |
  | 5 步间隔 | 第 3 步加点被拒并提示；第 5 步加点成功 ✓ |
  | 跳过与画面外 | 区域片段按 S 标为跳过 ✓，按 O 无效（按钮禁用）✓；工作区内其他片段按 O 标为画面外 ✓；在无法判断片段上单击被拒并提示 ✓ |
  | 改类别时清理 | 把手部片段改为工作区外：2 个点被清除并提示，Ctrl+Z 一并恢复 ✓；删除变化点使片段合并：失效的跳过标记被清除并提示，可以撤销 ✓ |
  | 完成条件 | 缺点时按钮不可用 ✓；看完 300 步、点与标记齐全后可用，确认后显示“已确认完成”，换段与重新加载后保持 ✓；直接发送“改标记并完成”的请求，服务端返回 400，没有保存任何内容 ✓ |
  | 命令行 | `labels validate --segment 20260911_pilot` 完成前 exit 1，输出一行错误；完成后 exit 0 ✓ |
  | 正式数据集 | 测试前后 manifest 与类别文件的 SHA 不变，没有生成 `labels.json` ✓ |
  | **画面外片段内单击** | **加点被接受，严格校验也通过**（见发现 1） |

- **正式导出与数据集**（Claude 独立核对）：区域 JSON 的 SHA 不变；类别文件与完成标记的前后哈希与报告一致，`completed_document` 通过，类别等于由区域生成的结果；参考图与 7 张叠加图不变，旧导出备份完整；两个数据集的 manifest 只改了 `annotation_schema_version` 与 `classes_sha256`。
- **独立代码审查**（只读子代理）：52 个变异中 30 个被测试捕获；坐标换算、相邻同类片段合并、只认已保存状态的完成判断、拒绝 v1/v2 与一行报错都已核实。
- **发现**：
  1. **必须修复：同一片段可以同时有注视点与“跳过”或“画面外”标记。**
     - 位置：`labels.py` 的 `validate_points` 没有互斥检查；页面的加点、S、O 与合并清理都不处理并存。
     - 后果：设计 §10.8 写明画面外“代替点注视点”，§10.3 的点与“跳过”也是二选一。两者并存时，阶段 3 会把同一片段既当作画面内的位置目标，又当作画面外的正例；“跳过”加点时，拿不准的点会进入点误差与人工基线。
     - 子代理的例子：[0,10) 为工作区内其他并标画面外，[10,50) 为区域片段且有 2 个点；在第 10 步按 6，两段合并成一段，同时保留画面外标记与 2 个点，没有提示，完成按钮可用。
  2. **必须修复：组合键与按住重复会改动标注。**
     - 位置：`annotation_page.html` 的 keydown 处理只对 Ctrl/Cmd+Z 检查修饰键。
     - 后果：Ctrl+S 切换“跳过”，Ctrl+O 切换“画面外”，Ctrl+X 删除当前点，并且屏蔽了浏览器本身的快捷键。按住 S 会反复切换，每次都保存。习惯性的 Ctrl+S 可能悄悄把一个需要点的片段标为“已处理”。
  3. **应修**：页面隐藏时的保存冲突，见 TASK-124 §3 第 5 轮发现 1。
  4. **应修（测试）**：
     - 服务端有三条规则没有被单独测试，对应的变异都能通过：画面外只用于手部与工作区内其他、离开/不在岗/无法判断片段中不能有点、跳过的步必须是片段起点。
     - Node harness 没有真正按下 Delete 键；S 只在片段起点按过；fake fetch 不检查 revision，也不检查保存内容中有没有 points 与 point_skips；没有检查隐藏与 `pagehide` 的 keepalive；没有断言“只有画面外标记的片段可以完成”。
     - `test_validation_labels.py` 中 3000 层的 JSON 在 Python 3.14 上可以正常解析，没有触发 RecursionError 分支。
  5. **应修（文档）**：六份文档都没有写默认点位（片段的第一步，否则目标最清楚的一步，§10.3），也没有写画面外“代替点注视点”。
  6. **应修**：manifest 中的 `annotation_schema_version` 没有被读取。旧方案的数据集（例如 `roi_r2_trial` 的旧备份与几个试用集）仍能用新工具打开，并写出 v3 标签。
  7. **小项**：
     - 在前方或右侧视图上单击没有任何提示；
     - 用 v2 标签文件启动 `annotate_server` 会打印 traceback，信息本身正确；
     - USAGE.md 与 USAGE_CN.md 中“重新标注”的说明重复出现两次；
     - 文档没有写区域的补充规则：注视落在某区域内的桌面或物体上时用该区域（§10.2）；
     - 手部/手中物体的颜色 `#f1c40f` 与你画的“物品存储盒” `#d4ac0d` 都是黄色，CIE76 色差约 12，时间轴上不易区分。改颜色需要再重新导出一次类别文件，须经你同意（Q-025 第 1 项）；
     - `render_roi_reference.py` 在 `--out-root` 位于另一磁盘时，完成标记的改名会失败，正式布局不受影响。
  8. **设计层面的限制（不阻塞）**：因为相邻同类片段必须合并，同一个类别片段内目标由画面内转到画面外（例如先看屏幕，再看左侧设备）时，无法分别表示。按第 2 轮的规则，部分可见时只点可见部分；如果试标中这类片段较多，再请你决定是否扩展方案。
- **A 级决定**：X、S、O 三个键位认可；目标上限由 6 改为 5 认可（现有区域最多 4 个）；保留试用集的默认来源认可；相邻同类片段必须合并认可（与 §7 的片段定义一致，清理有提示、可撤销）；`--backup-existing` 认可。“点与跳过标记可以并存”不认可，见发现 1。
- **结论**：**changes-requested**。按下面的第 2 轮要求修复，排在第 6 轮，是该轮唯一一项，完成后立即交回 Claude。正式标注在第 2 轮通过审查后开始。

### 第 2 轮要求（Claude，2026-10-29；第 6 轮执行）

1. **注视点与标记互斥**（设计 §10.8“代替点注视点”；验证集设计 4.2.0 已写明，Q-025 第 2 项）：
   - 服务端 `validate_points`：任何片段同时有点与跳过标记（任一原因）都拒绝。保存时与严格校验都检查。
   - 页面：
     - 在已有标记的片段内单击：拒绝，提示“本片段已标为跳过（或画面外），如需点注视点，先按 S（或 O）取消标记”。
     - 在已有点的片段上按 S 或 O：删除本片段的全部点并设置标记，提示删除的个数，Ctrl+Z 一并恢复。
     - 合并造成并存时：保留点、清除标记，写进清理提示，可以撤销。
   - 文档：画面外只用于整个片段的目标都在全局画面外；部分可见时只点可见部分，不标画面外；拿不准时整段用“跳过”。
2. **快捷键**：
   - 除 Ctrl/Cmd+Z 外，按着 Ctrl、Meta 或 Alt 时不处理任何快捷键，也不阻止浏览器的默认行为。
   - S、O、X、Delete、数字键与空格忽略按住产生的重复事件（`e.repeat`）；方向键可以重复，已有写盘降频。
3. **页面隐藏与关闭**：`visibilitychange` 变为隐藏时，按正常队列写入；只有 `pagehide` 与 `beforeunload` 直接发 keepalive。
4. **数据集版本门**：`AnnotationApplication` 与 `labels validate` 拒绝 manifest 中 `annotation_schema_version` 不等于 3 的数据集，提示重新生成数据集或按 TASK-125 第 5 条更新类别。
5. **测试**（默认隔离）：
   - 服务端：每条规则单独测试，其余条件都满足、只违反这一条。包括画面外用于区域片段、点落在离开/不在岗/无法判断片段、跳过的步不是片段起点、点与“跳过”并存、点与“画面外”并存。
   - Node harness：
     - 真正按下 Delete 键：删除变化点，不删注视点；
     - 在片段中间按 S：标记记在片段起点；
     - fake fetch 检查 revision，并检查保存内容含 points 与 point_skips；
     - 隐藏时有保存进行中，页面不进入失败状态；`pagehide` 仍直接发出 keepalive；
     - 只有画面外标记的片段可以完成；
     - 组合键与重复事件被忽略；
     - 在有标记的片段内单击被拒；S/O 清除已有的点，可以撤销。
   - 命令行的 RecursionError 分支用确实能触发的深度，或删去这一用例的说法。
6. **文档**（四份用户文档与两份中文指南）：
   - 默认点位：片段的第一步，否则目标最清楚的一步；
   - 第 1 条的互斥与画面外的用法；
   - 区域的补充规则：注视落在某区域内的桌面或物体上时用该区域；
   - 组合键不作快捷键；
   - 删去 USAGE.md 与 USAGE_CN.md 中重复的“重新标注”说明。
7. **小项**（可以一并做）：
   - 在前方或右侧视图上单击时提示“请在全局画面上点”；
   - 用 v2 标签文件启动 `annotate_server` 时只输出一行错误；
   - 播放中帧就绪后，等满一个步长再前进，使慢帧也能记为已看（TASK-124 §3 第 5 轮小项）。
8. **类别颜色（只在你同意 Q-025 第 1 项后做）**：
   - 按正式导出流程再重新导出一次类别文件，把 `hands_object` 换成与全部类别、调色板颜色都明显不同的颜色。报告与每一类的 CIE76 色差，最小值不低于其他类别两两之间的最小色差。
   - 区域不变，旧导出改名备份，并记录前后哈希。
   - 按第 5 条的方式更新两个数据集的类别文件与 manifest，旧文件改名保留，片段与帧不变。
   - 默认类别（`default_classes.json`、`default_regions.json`）同步换色。
   - 用户没有同意时不做，类别文件保持现状。
9. **浏览器实测**（临时标签文件，浏览器面板可见）：第 1 至 3 条各一项，并在 pilot 上重复第 5 轮的验收步骤。
10. **交回**：完成后立即把 `next_actor` 设为 `claude`，不接着做 TASK-101、TASK-150。

### 2026-10-29 第 6 轮审查（Claude）

- **审查目标**：`60464e2`（协调文档）、`ac89a66`（实现）、`a9f0738`（报告）与 `e605687`（交接与基线 B009），在 HEAD `e605687` 上审查。
  - `60464e2` 的文件清单与 Claude 第 5 轮留下的改动一致，另有 Codex 取写锁；
  - `e605687` 只改了 Codex 负责的字段与交接记录；
  - PR #6 的正文与 `STAGE2_PR_BODY.md` 一致，第 6 轮的双语评论已发。
- **独立复跑**：完整离线门 715 tests、0 skip；两个 Node harness 通过。
- **真实浏览器实测（Claude）**：
  - 环境：Edge 155 无界面模式，每次用新建的临时配置，测完删除。键盘与鼠标事件经 DevTools 协议发出，页面收到的是可信事件，按住按键时带真实的重复标志。`requestAnimationFrame` 约每秒 61 次，没有替换。页面隐藏用切换标签与最小化窗口两种方式，产生真实的 `visibilitychange`。
  - 数据：正式 `roi_r2` 只读，标签写在仓库外的临时文件。测试服务只记录保存与帧请求，可按测试标记延迟一次保存或某些帧，不向页面注入任何内容。
  - 结果：37 项中 36 项通过；未通过的 1 项是脚本的预期写错，见下表“写盘频率”。

  | 检查 | 结果 |
  | --- | --- |
  | 加点与片段 | 缩放视图中单击坐标正确；相隔 3 步加点被拒；在左侧视图上单击提示“请在全局画面上点” ✓ |
  | 互斥 | 片段中间按 S，标记记在片段起点 ✓；在已标跳过或画面外的片段内单击被拒，提示取消键，不保存 ✓；有点的片段按 O，删除 1 个点并设标记，提示个数，Ctrl+Z 一并恢复 ✓ |
  | 合并 | 用数字键或 Delete 使片段合并：保留点，清除冲突的标记并提示；Ctrl+Z 恢复两段、标记与点 ✓。改为工作区外时清除 2 个点并提示，可以撤销 ✓ |
  | 组合键 | Ctrl、Alt、Meta 与 AltGr 的 13 种组合不改标注、不保存，也不阻止浏览器的默认行为 ✓；Ctrl+Alt+Z 不撤销 ✓ |
  | 按住重复 | 浏览器确实发出重复事件（`repeat=true`）；按住 S、O 只切换一次、只保存一次，按住空格只切换一次播放，按住方向键照常连续移动 ✓ |
  | 保存中隐藏页面 | 一次保存被延迟 6 秒时切换标签或最小化窗口：页面收到真实的隐藏事件，下一次保存排在其后，使用新的 revision，全部成功，页面没有进入失败状态 ✓ |
  | 慢帧 | 播放中 11 个帧各延迟 0.5 秒：每帧加载后至少停留 0.204 秒才前进，300 步全部记为已看 ✓ |
  | 写盘频率 | 在未看过的片段上：手动 10 Hz 逐步时间隔 1.132–1.238 秒，播放时 50 个常规间隔为 1.068–1.177 秒 ✓。pilot 上只得到 14 个常规间隔、最短 1.09 秒，因为多数步之前已经看过，只有新看的步才写盘；脚本要求多于 30 个，是我的预期写错 |
  | 完成与命令行 | 看完 300 步后按钮可用，确认后保存完成时间；`labels validate --segment 20260911_pilot` 完成前 exit 1、一行错误，完成后 exit 0 ✓ |
  | 关闭页面 | 刚看过新步就关闭页面，最后的已看进度仍由 keepalive 送达 ✓ |
  | 快速逐步 | 10 Hz 逐步时有 1 步显示过短，没有记为已看，需要回看；这是有意的保守行为 ✓ |

- **对照实验**：同一套测试改用第 5 轮的页面（`f14b36b`），4 个旧缺陷全部复现：
  - Ctrl+S 改动标记，并阻止浏览器默认行为；
  - 按住 S 写盘 8 次；
  - 慢帧加载后 14–39 毫秒就前进；
  - 保存中隐藏页面，页面进入失败状态（`Stale annotation revision`）。

  这说明上面的测试确实能发现这些缺陷。
- **命令行**：
  - 旧数据集（manifest 没有 `annotation_schema_version`），以及该字段为 `true`、`3.0`、`"3"`、`2` 的数据集：`labels validate` 与 `annotate_server` 都拒绝，只输出一行错误，不写任何文件 ✓；
  - 用 v2 标签文件启动服务：只输出一行错误，exit 1，不监听端口 ✓。
- **数据保护**：
  - 正式区域、类别、参考图、完成标记，以及两个数据集的 manifest 与类别文件，共 8 项哈希，与测试前一致，也与 Codex 第 6 轮的记录一致；
  - 两个数据集都没有 `labels.json`；
  - 测试服务、浏览器进程与临时配置都已清理。
- **独立代码审查**（只读子代理，在仓库副本上）：42 个变异中 36 个被测试捕获；页面随机操作 80,000 次（4 个种子），服务端校验没有拒绝任何结果，页面与服务端的完成判断始终一致。
- **发现**：
  1. **必须修复：按住空格会点击获得焦点的按钮**（本轮改动引入的回归）。
     - 位置：`annotation_page.html` 的 keydown 处理。被忽略的重复事件在 `preventDefault()` 之前就返回。
     - 机制：鼠标点击后，按钮保留焦点。没有被阻止的空格按下让这个按钮进入按下状态，松开时浏览器点击它。第 5 轮的页面对每次空格按下都调用 `preventDefault()`，所以没有这个问题。
     - 真实浏览器复现：
       - 点过“撤销”后按住空格：松开时多撤销一次，而工具没有重做；
       - 点过“本片段跳过注视点（S）”后按住空格：松开时该片段的注视点被删除，并设上“跳过”标记（有提示，可以撤销）。
  2. **应修：撤销键的范围。** Ctrl/Cmd+Shift+Z（常见的重做习惯）也会撤销；按住 Ctrl+Z 会连续撤销，最多 100 步。
  3. **应修（测试）**：
     - Node harness 没有测 S、O 取消已有标记，而拒点的提示正是让用户这样做；
     - 没有测 Ctrl+Alt+Z 与 Ctrl+Shift+Z；
     - 没有测焦点在输入框、文本框或下拉框中时快捷键不生效；
     - 没有测被忽略的重复事件是否阻止了浏览器的默认行为；
     - 文档测试没有防止 USAGE 中重复的“重新标注”说明再次出现。
  4. **小项（文档与测试）**：USAGE.md 与 USAGE_CN.md 仍写“嵌套过深的 JSON 也输出一行错误”。在 Python 3.14.8 上深度 100000 时确实如此，但没有测试覆盖这一分支，现有的 3000 层用例能正常解析。
  5. **小项（文档）**：`ANNOTATION_GUIDE_CN.md` §5 的严格校验列表没有写注视点与标记互斥（§4 已写）。
- **Codex 的 B 级问题**：真实的隐藏事件与按住重复，已由上面的实测补全，均符合要求。关闭页面时 keepalive 可能被 revision 检查拒绝，这一边界已写入文档，认可。
- **A 级决定**：
  - 版本门放在 `LabelStore`，编辑器与命令行共用，并要求整数 3：认可。
  - 第 7 条的三个小项：认可。
  - Q-025 第 1 项当时未获批准，因此没有换色：做法正确。
- **结论**：**changes-requested**。第 2 轮要求的第 1、3 至 7、10 条已达到，第 9 条的浏览器实测由 Claude 补全；第 2 条引入了上面的回归。用户已同意 Q-025，换色并入第 3 轮。第 3 轮排在第 7 轮，是该轮唯一一项，完成后立即交回 Claude；正式标注在第 3 轮通过审查后开始。

### 第 3 轮要求（Claude，2026-10-29；第 7 轮执行）

1. **按住按键**：被忽略的重复事件，凡属页面自己的快捷键（空格、S、O、X、Delete 与数字键），先 `preventDefault()` 再返回；方向键照常重复。可选：鼠标点击按钮后让它失去焦点。
2. **撤销键**：只有按 Ctrl/Cmd+Z、且没有同时按 Shift 或 Alt 时才撤销。按住产生的重复事件不撤销：阻止默认行为后忽略。
3. **测试**（默认隔离）：
   - Node harness：
     - 按住空格、S、O、X、Delete 与数字键时，重复事件被阻止默认行为，而且只生效一次；
     - S、O 取消已有标记；
     - Ctrl+Shift+Z、Ctrl+Alt+Z 与按住重复的 Ctrl+Z 不撤销；
     - 焦点在输入框、文本框或下拉框中时，快捷键不生效。
   - 文档测试：USAGE.md 与 USAGE_CN.md 中拒绝 version 1、2 的说明各只出现一次。
   - “嵌套过深的 JSON 输出一行错误”：用确实能触发的深度写测试（例如 100000 层），或者从 USAGE 的两种语言中删去这句。
4. **文档**：
   - 四份用户文档与两份中文指南写明：撤销只用 Ctrl/Cmd+Z，工具没有重做；按住按键只算一次，方向键除外。
   - `ANNOTATION_GUIDE_CN.md` §5 的严格校验列表补上注视点与标记互斥。
5. **类别颜色**（Q-025 第 1 项，用户 2026-10-29 已同意）：
   - 把 `hands_object` 的颜色由 `#f1c40f` 改为 `#b6ff00`（亮黄绿色）。`default_classes.json` 与 `default_regions.json` 同步修改，相关测试随之更新。
   - 按正式导出流程（`render_roi_reference.py --backup-existing`）再重新导出一次正式类别文件，只做这一次：
     - 区域 JSON 的 SHA 不变（`6511ff108c397e4d7dc474bddf6531810f505443f80cf8aca4967c8d4cddf0bb`）；
     - 旧导出改名备份，并记录前后哈希；
     - 参考图与 7 张叠加图应当逐字节不变，如有变化就停下来报告。
   - 按 TASK-125 第 5 条的方式更新 `roi_r2` 与 `roi_r2_trial` 的类别文件与 manifest：旧文件改名保留，片段与帧不变，`--validate-only` 通过，不创建 `labels.json`。
   - 报告 `#b6ff00` 与每个类别、默认类别和调色板颜色的 CIE76 色差。预期最小值为 58.0（对物品存储盒 `#d4ac0d`），必须不低于其余颜色两两之间的最小值 21.4（`#7f8c8d` 对 `#bdc3c7`）。逐项数值见 `evidence/2026-10-29-round6-review.md` §9。
6. **浏览器**：在临时标签上确认新颜色显示正确，并复测第 1、2 条。内置浏览器发不出重复事件；Claude 审查时会用 Edge 的真实事件复测。脚本在 `gazelle_runs\claude-review-r6\browser\`（`probe_server.py`、`run_new.mjs`、`run_space_focus.mjs`、`run_rate.mjs`），Codex 也可以复用，端口与临时标签文件换新。
7. **交回**：完成后立即把 `next_actor` 设为 `claude`，不接着做 TASK-101、TASK-150 与 TASK-140 第 3 轮（第 8 轮）。

### 2026-10-30 第 7 轮审查（Claude）

- **结论**：**accepted**（`806068c`）。`36aa643` 是协调文档，核对无误；`342f5ed`、`24baf57` 只含报告与交接。完整记录见[第 7 轮审查记录](../evidence/2026-10-30-round7-review.md)。
- **第 3 轮要求逐条**：
  1. 按住按键：通过。Edge 真实 `repeat=true`：数字、X、S、O、Delete 与空格都只生效一次，7 个重复事件全部阻止默认动作；方向键照常重复。焦点在撤销、跳过、类别按钮上时按住空格，不多点一次。
  2. 撤销键：通过。Ctrl/Cmd+Shift+Z、Ctrl/Cmd+Alt+Z 不撤销，也不阻止浏览器默认动作；按住 Ctrl/Cmd+Z 只撤销一次。
  3. 测试：通过。Node harness 覆盖全部要求，21 个键盘处理变异全部捕获；文档测试通过。
  4. 文档：通过。四份用户文档与两份中文指南已同步，指南 §5 已补互斥。
  5. 类别颜色：通过。独立核对哈希、备份、差异与 CIE76，只有手部类颜色变化，8 张图逐字节相同，两个数据集各 27 段、8100 帧，没有 `labels.json`。
  6. 浏览器：通过。Claude 在 Edge 中补测，见审查记录 §2。
  7. 交回：符合要求。
- **验证**：完整离线门 717 tests、0 skip；两个 Node harness；Edge 实测 `run_keys.mjs` 28/28、`run_new.mjs` 37/37、`run_rate.mjs` 3/3、`run_space_focus.mjs` 3/3；同一 `run_keys.mjs` 用于第 6 轮页面，17 项失败，说明测试有效。
- **A 级决定**：三项都同意（不让按钮失去焦点、删去极深 JSON 的保证、argparse 帮助文本转义）。15 个命令行工具的 `--help` 都正常，没有同类问题。
- **B 级问题**：真实按住重复已由本次实测解决。Codex 环境中的 CDP 1006 断开没有在这里复现。
- **新发现**：用鼠标操作滑块或下拉框后，焦点留在控件上，快捷键不响应；片段下拉框上的方向键会切换片段。这不是本轮引入的，也不会写错标签，所以不阻塞本任务通过，由第 4 轮修复。开始标注前已告诉用户临时做法。

### 第 4 轮要求（Claude，2026-10-30；第 8 轮执行）

这一轮只修一个易用性小项。它不改标注格式，不改数据集，用户可以同时标注。

1. **鼠标用过的控件释放焦点**：
   - 用鼠标操作滑块（点击或拖动）、播放速度下拉框、片段下拉框之后，焦点回到页面，快捷键立刻可用：
     - 拖动滑块后按数字键能标注，按空格能播放；
     - 改成 0.5× 后按空格能播放，方向键移动一步，不改变速度；
     - 用片段下拉框换段后，方向键移动一步，不切换片段。
   - 用鼠标点击按钮后同样释放焦点，这样 Enter 不会再次触发按钮。
   - 键盘操作不变：用 Tab 移到控件上、用键盘操作时，焦点留在控件上，否则键盘用户无法连续操作。
   - 备注文本框保留焦点。第 3 轮的隔离规则不变：`INPUT`、`TEXTAREA`、`SELECT` 有焦点时快捷键不生效。
2. **测试**（默认隔离）：Node harness 覆盖上面各条：鼠标用过后焦点已释放，键盘操作时不释放，备注框不受影响。
3. **文档**：四份用户文档与两份中文指南各加一句：用鼠标操作过滑块或下拉框后，可以直接按快捷键。`tests/test_usage_docs.py` 相应增加检查。
4. **不做**：不改标注格式与 schema，不改 `classes.json`、manifest 或帧，不碰 `roi_r2\labels.json`。
5. **浏览器**：内置浏览器能测到的部分用临时标签测。Claude 审查时用 `gazelle_runs\claude-review-r7\browser\run_keys.mjs` 的 E1 至 E3 项在 Edge 中复测。

### 2026-10-31 第 8 轮审查（Claude）

- **结论**：**accepted**（`980d8ee`）。`476ebdf` 只含报告。完整记录见[第 8 轮审查记录](../evidence/2026-10-31-round8-review.md) §2。
- **第 4 轮要求逐条**：
  1. 鼠标用过的控件释放焦点：通过。Edge 真实鼠标实测：点击与拖动滑块、用弹出列表改速度与换片段之后，数字键、空格与一次方向键都正常，方向键不再改速度或换段；点击按钮后 Enter 不再触发。键盘路径与备注框不变。
  2. 测试：通过。Node harness 覆盖鼠标、键盘与备注框三条路径。
  3. 文档：通过。四份用户文档与两份中文指南都加了说明，文档测试锁定。
  4. 没有改标注格式、类别、manifest 或帧，也没有碰 `labels.json`。
  5. 浏览器：`run_focus.mjs` 23/23，旧页面 8/23；`run_keys.mjs` 把 E1 至 E3 改成真实预期后 28/28，旧页面 24/28；`run_new.mjs` 37/37，`run_rate.mjs` 3/3，`run_space_focus.mjs` 3/3。
- **A 级决定**：同意用委托的 pointer、change、click 事件，并在 keydown 时清除鼠标来源。
- **两处小缺口，不再开一轮**：用鼠标打开下拉框、没有改选就关闭时没有 `change` 事件，焦点留在下拉框上；点击“片段”两个字时焦点也会到下拉框。都不写错数据，点一下空白处即可，已写入给用户的说明。
