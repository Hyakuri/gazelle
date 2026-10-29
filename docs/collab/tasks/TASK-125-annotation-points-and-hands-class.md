# TASK-125：标注方案 r3——“手部/手中物体”类别与注视点

状态：ready-for-review。Codex 于 2026-10-29 完成第 5 轮实施与验证，待 Claude 独立审查。用户确认的 r3（Q-017）与 r3.1（Q-018）均已实施，包括第 2 条与第 8 条
创建：2026-10-18（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：用户 2026-10-18 的目标说明（`docs/requirements/PROJECT_GOALS_CN.md` v3）与决定 D20；[验证集设计](../../design/VALIDATION_SET_DESIGN.md) §10（r3）。
授权：2026-10-14 本地修改与本地运算授权；作业数据只读；正式区域的类别重新导出以 Q-017 的确认为准，用户已于 2026-10-29 确认。

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

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：
