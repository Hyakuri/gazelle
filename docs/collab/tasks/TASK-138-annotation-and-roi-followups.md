# TASK-138：标注与区域工具的第 2 轮审查后续（正式标注前必须完成）

状态：accepted（2026-10-17 第 3 轮审查；应修项转入 TASK-124）
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

### 2026-10-17 实施与验证

- 接手：新仓库根与分支复核，HEAD `db5f29f`，`writer=none`、`next_actor=codex`；先接管 writer。Claude 的 14 份协调文档单独提交为 `117fbc2`（`Record coordinator updates`）并推送，PR #6 正文已同步。用户本轮直接批准 D18，收讫记录在 Q-010。仅主线程 Inline Execution，无子代理。
- 实现提交：`1b854ebfa06b9a12a070c7f34cd5e51c6f7ce91a` — `Require explicit reviewed annotation completion`，已普通推送到既有分支。
- 修改：25 个文件，范围为契约列出的标注、区域、抽样、remux、media、对应测试、两个 Node harness、四份用户文档与两份中文指南。
- 标注 version 2：实际图片加载、显示后记录合并 `viewed_ranges`，未看部分保留纹理；服务端拒绝已看范围缩减、重叠与越界。全部已看且有类别后，显式完成才写 `finished_at`；修改类别/他人区间清除完成，撤销不恢复旧完成凭据。续标优先未看步，支持可重复 `--segment`。
- 完成标记 version 2：绑定区域、导出目录、参考图与类别 SHA-256；显式未完成 `--regions-path` 失败，复制使用验证后的原始字节。会话白名单、独立 `seed + int(session)`、pilot 重叠重抽及记录已实现。区域小于 0.5% 时要求确认，服务端丢弃区域行额外字段，页面显示完成状态。固定类别中文名统一、请求体读取前检查令牌、Host/Origin 拒绝测试已补齐。

#### 命令与结果

所有 Python 使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，设置 `PYTHONPYCACHEPREFIX=%TEMP%\gazelle-task-138-pycache`、`PYTHONIOENCODING=utf-8`。完整日志在仓库外 `gazelle_runs\task-138\`。

| 命令 / 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.test_validation_labels -v`（修改前回归） | exit 1，两个预期失败，复现自动完成与旧 schema |
| 相关 ROI/抽样/尾部回归（修改前） | exit 1：无导出绑定、未完成 ROI 静默回退、尾部时间偏差；新增测试插入位置错误导致一次 NameError，修正后重跑 |
| `python -m unittest tests.test_validation_labels tests.test_validation_server tests.test_validation_sampling tests.test_validation_roi tests.test_workdata_tools tests.test_media tests.test_usage_docs -q` | exit 0，79 tests / 5.020s / 0 skip |
| `python -m compileall main.py gazelle tests tools` | exit 0 |
| `python -m unittest discover -s tests -v` | exit 0，611 tests / 9.839s / 0 skip |
| `python main.py --help`、`python main.py --list-models` | 均 exit 0 |
| `node tests/roi_page_test.cjs`、`node tests/annotation_page_test.cjs` | 均 exit 0；后者初次因测试遗留未结束的他人区间而失败，明确取消起点后通过，未放宽按钮规则 |
| `python -m unittest tests.test_validation_sampling -q`（最终补充导出篡改拒绝断言） | exit 0，5 tests / 0.155s；参考图与类别任一被修改均拒绝创建数据集 |
| `git diff --check`、准确暂存路径检查 | 通过；无未跟踪数据，无仓库内媒体、权重或字节码产物 |

非致命输出：离线套件既有坏 MP4 用例输出 `moov atom not found`；Git 提示 LF/CRLF 转换，未改全局配置。一次汇总脚本漏写 UTF-8 导致 cp932 解码失败，补上 `encoding='utf-8'` 后只读重跑通过。浏览器首次按 label 定位片段选择器未匹配，依据实际 DOM 的 `#segments` 重试成功。

#### 真实运行

1. `python gazelle_runs\task-138\revalidate.py`：BelowNormal CPU，真实 ffprobe/OpenCV，只读复核 **11/11** 重封装文件，exit 0，用时 **128.205s**；头/中各 30 帧、尾部 59 或 60 帧到 EOF。先扣除 0.033s 起点后尾部差接近 0（浮点舍入量级）。源文件和输出 size/mtime 未变，`remux_report.json` SHA 前后相同；独立结果为 `gazelle_data\workdata\remux\task138_validation.json`。
2. 本地浏览器服务：`python -m tools.validation.annotate_server --dataset-root ...\gazelle_validation\roi_r2_trial --labels-path ...\gazelle_runs\task-138\browser_labels.json --annotator codex-task138 --port 8781`。只用旧试用集，不改其 manifest、帧或正式 labels。
   - 第 0 步按一次 `1`：已标 300/300，已看 1/300，299 步有未看纹理，完成按钮禁用。
   - 重载定位步 1（0.2s），播放至 300/300 后按钮可用；确认后跳至 `20260821_s01`。
   - `python -m tools.validation.labels validate --dataset-root ...\roi_r2_trial --labels-path ...\task-138\browser_labels.json --segment 20260911_pilot`：未确认 exit 1；确认后 exit 0；改为 unknown 后完成清空、exit 1；再次确认后 exit 0。其他 26 段未完成不妨碍 pilot 单段严格检查。
   - 控制台 warnings/errors 为空；页面与服务已关闭，8781 无监听。试用集正式 `labels.json` 仍不存在。此为交互机制验证，所选类别不代表研究判断。
3. 用户区域：只读检查发现五个多边形均为 target，缺 cell，故无完成标记。用户明确批准“保留全部顶点、名称和颜色，仅将 work_area.kind 改为 cell，并在 TASK-138 完成后导出校验”。完成上述验证后执行该限定例外。
   - 原始 JSON 完整备份：`gazelle_runs\task-138\roi_regions_before_cell_fix.json`，SHA `747bfee95b8723e8230c1cff61e739b923b92e201c2df0b8cf853d37ee7fa760`。
   - 修正后 SHA `6511ff108c397e4d7dc474bddf6531810f505443f80cf8aca4967c8d4cddf0bb`；深比较证明唯一语义变化是该 kind，四个目标、全部顶点、名称、颜色及元数据保留。参考候选 1920×1080，哈希匹配；五块面积分别约 9.323%、7.672%、13.360%、6.169%、65.539%。
   - 使用修复后的 `render()` 实际导出 1 张参考图、7 张跨日期叠图、8 类 classes.json 与 v2 完成标记；`completed_document()` 与各 SHA 全通过。参考图及全部七日期叠图已目视检查，边线与文字完整；人员遮挡与容器高度变化不构成精确几何标定证明。
   - 记录在 `gazelle_runs\task-138\formal_roi_check.json`。未生成正式数据集、正式逐帧 labels；须等待 TASK-139 同步验收。

#### 反证式复核

一键填满不等于看完；完整播放仍不等于显式确认；确认后修改仍使严格校验失败。篡改导出任一文件不能复制；改变一个会话的随机消耗不影响另一会话，20261016 被忽略；0.25s 起点的合成尾部用例也按 0 差计算。旧试用集和全部真实媒体保留。

#### 自主决定（A 级）

- 标签 HTTP 的 `finish=true` 要求类别/他人区间先保存，不能在同一请求修改后直接确认；UI 保存完成后才启用确认，避免混合操作。
- 图片显示用两次 animation frame 且页面可见时记已看；未加载、失败或被跳过的图片不记。已看保存会创建临时/正式指定的标签文件，六份说明同步此行为。
- ROI 完成标记升为 v2，旧标记需重新导出；区域 JSON 本身仍为 v1。复制前读取并验证导出字节，避免校验后再读到另一版内容。
- `--sessions` 仍要求包含固定 pilot 的会话，保留“恰好一个 pilot”既有约束；缺少指定会话明确报错。

#### 范围外改动

仅用户直接批准的正式 ROI 单字段修正、备份与导出；未更改研究类别含义、顶点或协议。D18 批准只记授权，不在本任务实施同步。

#### 待 Claude 判断（B 级）

请独立复跑、审查 A 级决定和真实浏览器完成流程。正式 ROI 的领域边界与后续标注协议由用户/Claude 验收；本次数据一致性与叠图检查不能代替研究验收。

#### 待用户决定（C 级）

无待决授权。D18 与 ROI 单字段例外均由用户本轮直接批准，未扩大到任意编辑正式区域。

#### 外部活动、限制与状态

真实活动仅 CPU、磁盘、ffprobe/OpenCV/Pillow、loopback 浏览器和已授权 GitHub 发布；无模型、CUDA 推理、MediaPipe、下载、模型缓存修改或 Conda 改动。普通沙盒权限沿用本会话已验证结果；Git/GitHub 在已批准 yun 上下文，非普通沙盒认证通过。标签与媒体不上传。

**已实施、已静态检查、已实际运行；待 Claude 独立验收。** 当前四份用户文档与两份指南同步。本任务没有生成同步代理或正式数据集，按队列继续 TASK-136，再执行已获 D18 批准的 TASK-139。

## 3. 审查结论（Claude 追加）

### 2026-10-17 第 3 轮审查（Claude）

- **审查目标**：`1b854eb`（实现）与 `d767dba`（报告），在 HEAD `f0c4311` 上审查。这些文件此后没有改动。
- **独立复跑结果**：
  - 完整离线门 643 tests，0 skip。
  - 一份只读代码审查（子代理）：相关单测 39 项、文档测试 20 项、两个 Node harness 全部通过，另用不写文件的 Node 与 Python 探针核对了页面与服务端逻辑。
  - **浏览器实测（Claude）**：用旧试用集 `roi_r2_trial` 和临时标签文件 `gazelle_runs\claude-review-r3\browser\labels_claude_r3.json`，端口 8791，测完已关闭。

    | 步骤 | 结果 |
    | --- | --- |
    | pilot 第 0 步按一次数字键 | 已标 300/300、已看 1/300；时间轴有未看斜纹；“本段完成”不可用 ✓ |
    | 重新加载 | 定位到第一个未看步 ✓ |
    | 浏览器面板被隐藏时播放 | 画面只刷新约 2 次/秒，随后停止重绘；只记下真正显示过的步（88/300），不会把没显示的步算作已看 ✓ |
    | 看完 300/300 步 | 按钮可用；确认后跳到 `20260821_s01` ✓ |
    | `labels validate --segment 20260911_pilot` | 确认前 exit 1，确认后 exit 0，修改类别后 exit 1 且 `finished_at` 清空 ✓ |

  - 尾部检查：读取了 Codex 的只读复核结果 `task138_validation.json`，11/11 文件的差值都是 0.0；没有重新运行。
- **已核实**：
  - GZ-27 已关闭：`finished_at` 只在显式完成时写入，只有按钮会发出完成请求，按钮的启用条件完整。
  - 已看范围只增不减，越界与重叠都被拒绝；严格校验要求三项条件同时满足；version 1 文件被明确拒绝；`--segment` 的行为正确。
  - 完成标记 v2 记录了导出目录与两个 SHA-256；抽样时复制的就是校验过的那份字节；显式给出未完成的 `--regions-path` 会报错。
  - 每会话独立种子、`--sessions` 默认 7 次录制、与 pilot 重叠时重抽并记录；区域行按 schema 保存、面积小于 0.5% 时提示、页面显示完成状态；令牌在读取请求体前检查；Host/Origin 拒绝有测试。
- **应修**（不阻塞，转入 TASK-124，排在正式标注之前）：
  1. 服务端判断能否完成时，用的是同一请求里携带的 `viewed_ranges`。持有令牌的客户端可以一次请求同时写入全部已看并完成。页面本身不会这样做。应改为与类别相同的规则：只认已保存的已看范围。
  2. `labels validate` 失败时打印 Python traceback，应改为一行错误信息，退出码不变。`viewed_ranges` 的错误信息误用了 other_people 的措辞。
  3. 播放时每看一步就整文件原子保存一次并写 `.bak`，约 5 次/秒。建议只看过但没有改动的保存最多每秒一次，暂停、换段、完成时立即写入，以减少 Windows 替换文件失败的机会。
  4. 指南补一句：修改了一段较长的类别后，确认完成前请回放检查该段。这是因为“已看”只表示显示过，不表示修改后重新看过。这一点不改变本任务的规则。
  5. 小项：
     - `remux.py` 中 `start_time` 为 None 时尾部检查失败。这是安全方向，但应明确按 0 处理并记录。
     - `media.py` 的浮点返回值没有类型断言；`--segment` 只测了函数，没测命令行。
     - 区域页面导出与并发编辑之间可能显示过时状态；抽样会重新校验，所以结果安全。
- **范围外改动**：Codex 按用户直接批准，把正式区域的 `work_area.kind` 改为 `cell` 并重新导出。只读核对显示，唯一语义变化是该字段，其余顶点、名称、颜色均保留，备份完整。这一批准由 Codex 转述，用户已于 2026-10-17 直接向 Claude 确认（Q-013）。
- **结论**：**accepted**。连同 TASK-121 的阻塞问题（GZ-27）一并关闭。应修项见 TASK-124。
