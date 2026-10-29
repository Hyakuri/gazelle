# TASK-125：标注方案 r3——“手部/手中物体”类别与注视点

状态：ready。用户 2026-10-29 确认了验证集设计 r3 的细则（Q-017，原话“确认 r3”）与 r3.1（Q-018），本任务在第 5 轮实施，包括第 2 条与第 8 条
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
