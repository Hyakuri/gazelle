# TASK-138：标注与区域工具的第 2 轮审查后续（正式标注前必须完成）

状态：ready
创建：2026-10-17（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：TASK-121、TASK-123、TASK-135 的第 2 轮审查结论（各任务文件 §3），以及两份独立代码审查。
授权：2026-10-14 本地修改与本地运算授权；作业数据只读。

## 1. 契约

### 目标

修复标注工具中可能静默损坏标注的问题，把区域完成标记与导出文件绑定，让抽样不受其他会话影响，并补上 TASK-135 尾部检查的起始时间偏差。完成后，用户才能开始正式标注。

### 必须实现

1. **已看范围与显式完成**（TASK-121 阻塞问题）：
   - **已看范围**：每段记录 `viewed_ranges`，即已经在页面上完整显示过的步的区间列表，按升序合并。
     - 画面加载完成并显示时，该步记为已看。逐步前进、播放、点击时间轴跳转都会记录，只记录实际显示过的步。
     - 服务端校验：区间互不重叠、在片段范围内，并且只增不减，不接受客户端删除已看记录。
   - **未看部分的显示**：时间轴上，未看过的步即使已有类别，也叠加明显的未看纹理。页面显示已看步数，例如“已看 120/300”。
   - **显式完成**：新增“本段完成”按钮。只有当全部步都已看过、且全部有类别时才能点击；点击后写入 `finished_at`。
     - 完成后再修改任何类别或他人入镜区间，`finished_at` 清空，需要重新确认。
     - 服务端不再根据“没有 null”自动写入 `finished_at`。
   - **续标**：打开页面时定位到第一个未完成的段。在该段内，定位到第一个未看过的步；全部看过时，定位到第一个 null 步；两者都没有时，定位到第 0 步。
   - **严格校验**：每段必须同时满足三条：`finished_at` 不为空、`viewed_ranges` 覆盖全部步、没有 null。
   - **schema**：标注文件 `version` 改为 2。目前没有任何正式标注，不需要迁移；读取 `version` 1 的文件时明确拒绝，并提示用新工具重新标注。
2. **单段严格校验**：`labels validate` 增加可重复的 `--segment <segment_id>` 选项。只对指定的段做严格检查，其余段只检查结构。不带该选项时，行为与现在相同：全部段都做严格检查。
3. **区域完成标记绑定导出**（TASK-123 应修）：
   - 导出时，在完成标记中记录导出目录、`roi_reference.png` 与 `classes.json` 的 SHA-256。
   - 完成标记写在区域文件旁边，导出目录由完成标记指明。`--out-root` 与默认目录的规则写进指南。
   - `sample_segments` 只从完成标记指明的导出目录复制参考图与类别，复制前核对 SHA-256，不一致时报错。
   - 显式给出 `--regions-path`、但该文件没有有效完成标记时，直接报错退出，不再静默改用默认类别。只有不给 `--regions-path` 时，才生成 `roi_r2_trial` 试用集。
4. **抽样稳定性**（TASK-121 应修）：
   - 每个会话单独派生随机种子，例如 `seed + int(session)`，互不影响。
   - manifest 记录参与抽样的会话列表。
   - 新增 `--sessions`，默认值为已批准的 7 次录制（20260821、20260828、20260903、20260911、20260925、20261002、20261009）。代理根目录中出现其他会话时忽略并打印提示，不自动加入。
   - 正式片段与 pilot 不得重叠：重叠时在同层重抽，并记录这次重抽。
5. **区域工具小项**（TASK-123）：
   - 页面显示完成状态，例如“已导出、未修改”或“导出后有修改，需要重新导出”。
   - 服务端按 schema 保存区域行，丢弃多余字段。
   - 导出时，对面积小于画面 0.5% 的区域给出提示，由用户确认后继续；不设硬性下限。
6. **尾部检查起始时间**（TASK-135 应修）：
   - `tools/workdata/remux.py` 的尾部时间检查先把 OpenCV 的 `POS_MSEC` 加上 `start_time`，或从包 PTS 中减去 `start_time`，再与一个标称帧间隔比较。
   - 用现有 11 个重封装文件只读复核：差值应接近 0，而不是 33 ms。复核结果写到独立报告文件，不改写 `remux_report.json`。
   - `gazelle/runtime/media.py` 中 `p + 1` 分支统一返回浮点数。
7. **小项**：
   - 标注服务在解析请求体之前检查令牌。
   - `default_classes.json` 与 `default_regions.json` 中固定类别的中文名统一。
   - 为标注服务补 Host/Origin 拒绝路径的测试。

### 非目标

- 不改类别定义、判断规则、5 Hz 时间轴与片段长度。
- 不生成正式数据集：正式数据集要等正式区域文件与 TASK-139 的同步代理。
- 不处理同步协议：由 TASK-139 处理。

### 依据材料

- `tools/validation/`：`annotate_server.py`、`annotation_page.html`、`labels.py`、`sample_segments.py`、`extract_frames.py`、`roi_server.py`、`roi_page.html`、`roi_regions.py`、`render_roi_reference.py`、`default_classes.json`、`default_regions.json`、两份中文指南。
- `tools/workdata/remux.py`、`tools/workdata/common.py`、`gazelle/runtime/media.py`。
- 对应测试与两个 Node harness。
- TASK-121、TASK-123、TASK-135 的 §3。

### 不可变约束

- AGENTS.md 的默认测试隔离与运行时不变量。
- 源目录只读。
- 现有派生数据不得被破坏：试用集、候选帧与重封装输出只读复核，不重写。

### 允许动作

- 修改上述文件与测试，更新四份用户文档的研究数据工具小节与 `tests/test_usage_docs.py`。
- 在 `Gazelle-next` 中运行离线门、两个 Node harness，以及第 6 条的只读复核。
- 用现有试用集与临时 `--labels-path` 做浏览器实测。
- 按协作方案 §4 提交、推送，并在 PR #6 发英中双语评论；问题处理按协作方案 §3.5。

### 禁止

- 协作方案 §3.5 的硬边界。
- 修改任何 Conda 环境。
- 写入源目录；提交数据、媒体或标注。
- 创建正式 `labels.json` 或正式 `roi_regions.json`。

### 验收标准

1. 新增测试（默认离线）：
   - 一键标满整段后，没有确认就不算完成：续标仍停在该段的第一个未看步，严格校验失败。
   - 看完全部步并确认后，严格校验通过；之后修改类别，`finished_at` 被清空。
   - 已看范围只增不减；越界或重叠的区间被拒绝。
   - `--segment` 只严格检查指定段。
   - 完成标记中的哈希不一致时，抽样拒绝复制；显式 `--regions-path` 未完成时报错。
   - 每会话种子：改变一个会话的重抽次数，其他会话的抽样不变；未列入 `--sessions` 的会话被忽略。
   - 尾部检查：`start_time` 为 0.033 s 的文件，差值按 0 计算。
2. 完整离线门通过，无新增 skip；两个 Node harness 通过。
3. 浏览器实测（临时 `--labels-path`）：
   - 在 pilot 第 0 步按一次数字键：页面显示未看纹理，“本段完成”按钮不可用。
   - 播放或逐步看完全部步后，按钮可用；确认后续标跳到下一段。
   - 改一个类别后，完成状态被清除。
4. 第 6 条的只读复核：11 个文件全部通过，差值接近 0。
5. 四份用户文档与两份中文指南中英语义一致，写明显式完成、已看范围与 `--segment` 的用法。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-138-pycache"
& $py -m unittest tests.test_validation_labels tests.test_validation_server tests.test_validation_sampling tests.test_validation_roi tests.test_workdata_tools tests.test_media -v
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

- 需独立审查：是。涉及标注数据的完整性。
- 需真实运行：是，即第 6 条的只读复核与浏览器实测，仅 CPU。
- 文档同步：需要。
- 依赖：无。排在第 3 轮第一项，在 TASK-139 之前，使重新生成的试用集直接采用新的抽样规则。

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
