# TASK-150：新录制（20261016、20261023）与 webcam 的接入

状态：changes-requested（Claude 2026-10-31 第 9 轮审查，见 §3）。r5 第 1 至 9 条的行为成立，`20261016` 的代理与验证通过审查。契约修订 r7 与 r6 在第 9 轮继续执行，都在 §1 末尾。此前的修订说明见“契约修订 r2”至“r5”
创建：2026-10-29（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：
- 用户 2026-10-29 的决定 D26、D27（Q-020、Q-021），原话为“Q-018至Q-021 我已经确认，请按你的推荐进行。”；
- [作业数据分析 r2](../analysis/2026-10-29-workdata-analysis-r2.md)；
- [验证集设计](../../design/VALIDATION_SET_DESIGN.md) §11；
- [系统总体设计](../../design/SYSTEM_OVERVIEW_CN.md) §2、§6；
- [阶段 3 设计](../../design/STAGE3_GAZE_ATTENTION_CN.md) §3.4。

授权：
- 2026-10-14：本地修改与本地运算；
- 2026-10-15：作业数据只读使用，派生物只留在仓库之外。

## 1. 契约

### 目标

把两次新录制接入第 2 阶段的数据层，达到与旧 7 次同等可用，同时旧 7 次的全部产物保持不变。

- **源数据**：文件夹 `20261016`（画面时钟 2026-10-14）与 `20261023`（画面时钟 2026-10-19），各有 A、B、E 与一个 webcam 文件 `WIN_*_Pro.mp4`。
- **webcam**：记为 `cam_w`，作辅助视角（D26）。它接入时间轴与代理，用作标注参考与以后的基线，不是必需输入。
- **产出**：
  - 清单；
  - E 的重封装；
  - 时间映射（含 W）与内容校准；
  - 5 Hz 代理（含 W）；
  - 同步验证；
  - 作业者片段；
  - 新分层的验证数据集 `roi_r2_2026_10`，共 8 段。

### 背景（已实测，见分析 r2）

| 项目 | `20261016`（画面时钟 2026-10-14） | `20261023`（画面时钟 2026-10-19） |
| --- | --- | --- |
| A（画面时钟） | 3 段，78.2 分钟，12:53:28–14:11:38 | 4 段，91.8 分钟，13:37:27–15:09:23 |
| B（画面时钟） | 2 段，60.4 分钟，12:59:54–14:00:20 | 3 段，62.0 分钟，13:58:00–15:00:05 |
| E（画面时钟） | 60.2 分钟，12:59:55–13:59:59 | 60.5 分钟，13:59:41–14:59:59 |
| W（文件名中的电脑时间） | `WIN_20261014_12_05_36_Pro.mp4`，180 分钟 | `WIN_20261019_12_33_53_Pro.mp4`，180 分钟 |
| 三机重叠（各自画面时钟，误差约 1 秒） | 12:59–13:59，60.1 分钟 | 13:59–14:59，60.3 分钟 |
| 其他 | 重叠段内换人：W 中 13:13:36 至 13:15:36 工位无人 | A、B 在 14:22:59 同时中断约 6 秒，E 连续 |

- **摄像机身份**：两个新文件夹的编号没有互换，カメラ1 是 A，カメラ2 是 B，由画面时钟样式确认。
- **E**：AVI 前 60 秒的 1801 个包中有 902 至 903 个空包，与旧 E 相同，需要重封装。
- **W**：
  - H.264，1280×720，14.985 fps，带 48 kHz 立体声音轨，没有画面时钟。
  - 文件名中的时间是录制开始时的电脑时间。它的日期与画面时钟日期一致，与文件夹名不同。
- **W 相对 B 的偏移**：
  - 方法：运动能量互相关，脚本在仓库外 `gazelle_runs\claude-data-r2\webcam_offset.py`。
  - 符号：正值表示同一事件 W 的电脑时钟读数比 B 的画面时钟晚。
  - 结果：`20261016` 的 13:20–13:30 为 −1.8 秒，13:45–13:55 为 −2.2 秒；`20261023` 的 14:00–14:10 为 −0.4 秒，14:30–14:40 为 −0.2 秒。
  - 精度：B 只用了各段的整数起始时钟，所以约为 ±1 秒。

### 现有代码的约束

Claude 2026-10-29 只读核对，对应 HEAD `5882791`。其中前四条由主线程抽查过原码。

- **清单**：`inventory.py` 的 `identify()` 对 `WIN_*` 抛出“Ambiguous or unknown camera filename”，整个清单中止。清单扫描整个源目录，没有按录制筛选的选项。
- **重封装**：`remux.py` 每次运行，都只用本次处理的行重写 `remux_report.json`。`media_path` 与 `extract_roi_candidates` 都依赖报告中的对应行。
- **抽样**：
  - 每次录制有自己的随机数生成器 `Random(seed + int(session))`；`DEFAULT_SESSIONS` 是旧 7 次。
  - 固定的试标时刻必须恰好落在一次所选录制中，否则报错。
  - 数据集根目录已存在时拒绝写入。
  - `labels.json` 记录 manifest 与类别文件的 SHA，不一致时拒绝加载。
- **代理与拼图**：
  - `proxies.py` 的 `ROLES` 只有三台摄像机；每次运行都重写 `session.json`。
  - 标注页面显示一张预先拼好的三视角图，1920×720，没有第 4 个视角。
- **时间映射**：`timemap.py` 对每个文件读画面时钟；`assemble_session` 固定三台摄像机，重叠取全部摄像机的交集。`osd_clock.py` 只有 A、B、E 的样式，遇到未知摄像机抛 KeyError。
- **校准与验证**：`sync_calibrate.py` 与 `sync_validate.py` 固定三台摄像机；`sync_validate.py` 对每台摄像机都做时钟抽查。
- **指纹**：代码修改后，若对旧录制重跑代理，会因实现指纹不符而报 FileExistsError。

### 必须实现

1. **摄像机角色**：
   - `camera_roles.json` 增加 webcam：文件名以 `WIN_` 开头、以 `_Pro.mp4` 结尾的文件识别为 `cam_w`，角色为 webcam，没有画面时钟。
   - 其他无法识别的文件名仍然报错，现有测试保持不变。
   - 不在 `osd_layouts.json` 中加 W，因为该文件参与实现指纹。
   - 清单记录 W 的流信息，包括有音轨这一事实；`needs_remux` 为假。
2. **共享文件不改动旧内容**：
   - 先查依赖：`inventory.json`、`remux_report.json`、区域候选 `candidates.json` 等多次录制共用的文件，被旧录制的哪些产物记录了哈希、依赖了哪些行。结果写入报告，属 A 级。
   - 旧行的内容必须不变。若某个旧产物记录了整个文件的哈希，就不改写该文件，改为写新的同级文件，并让下游按录制找到正确的文件。
   - 清单与重封装增加按录制运行的选项，例如 `--session`。合并更新时只改所选录制的行。
3. **重封装**：两个新 E 的 AVI 按 TASK-132、TASK-135 的同一方法与检查重封装。不得使用 `--force`，旧的 11 个输出不动。
4. **基础时间映射**（`timemaps_v2_base`）：
   - A、B、E 按现有方法读画面时钟，门槛不变。
   - W 走新的无时钟分支：wall = 文件名时间 + 容器 PTS，斜率 b = 1。
     - 文件名时间与画面时钟用同一种编码，即不带时区的时间按 UTC epoch 秒记录。
     - 来源记为 `filename_clock`，并写明这是电脑时钟，不是画面时钟。
   - 三机重叠只由 A、B、E 决定。W 的覆盖另行记录，不参与交集。
   - W 写在单独的 `auxiliary_cameras` 键下，`cameras` 仍只含 A、B、E。原因：抽样（`read_session`）、清单校验（`validate_manifest`）与同步验证的摄像机循环都要求 `cameras` 恰好是这三台。
5. **内容校准**（`timemaps_v3`）：
   - A、E 对 B 的校准与旧 7 次完全相同：不改 A、E 的校准、采样与拟合函数，用现有的采样指纹（AST 级）核对这些部分在改动前后一致；有差异就逐项报告。
   - W 用同一方法对 B 校准偏移、漂移与分段，`sync_uncertain` 的规则相同；W 的样本取在同一个 5 Hz 网格上。
   - W 校准失败时，只把该录制的 W 标为不可用并记录原因，不阻塞 A、B、E。W 的校准结果也放在 `auxiliary_cameras` 下，不进入代理生成“全部有效且已校准”的检查（`proxies.run`），否则 W 失败会挡住 A、B、E。
   - **数值核对（防止符号错误）**：把 W 的结果换算成背景一节的符号约定。`20261016` 的两个窗口在其中点（B 时钟 13:25:00 与 13:50:00）的校准偏移必须为负，且与 −1.8、−2.2 秒之差都不超过 1.2 秒，这个余量是分析 r2 约 ±1 秒的精度加一个分箱。`20261023` 的两个窗口只报告数值。不满足时按 B 级报告，不调整方法去迎合这个数。
6. **5 Hz 代理**：
   - A、B、E 与旧 7 次相同：1080p，逐帧记录来源与 PTS。
   - W 另设一个可选角色，不放进 `ROLES`，因为抽样与抽帧都复用 `ROLES`。代理的 `session.json` 中，W 同样写在 `auxiliary_cameras` 下。
     - 输出 `proxy_webcam.mp4` 与 `proxy_webcam.frames.json`，1280×720。
     - 网格与 A、B、E 相同，只覆盖三机重叠段。
   - 只保留视频流，不写音频。
   - `20261023` 的 A、B 同时中断，按现有缺口规则记录（`coverage_gaps` 与逐步的 `gap`），不插值。
     - 若需要 `--allow-internal-gaps`，记录在 `session.json` 中。
     - 先确认中断位于文件边界还是文件内部，写入报告。
7. **同步验证**（`sync_validation_v3`）：
   - A–B、E–B、A–E 用与旧 7 次相同的门槛。另加 W–B 的残差，门槛与 A–B 相同；W 未通过时只把 W 标为不可用。
   - 时钟抽查只做 A、B、E，按 TASK-140 第 2 轮的规则：同源帧补读，每次录制可评估比例 ≥ 90%。
     - 抽查样本的生成方法与旧 7 次相同，种子为 20261015 加录制编号。
     - 生成脚本若在仓库外，把它复制到本任务的运行目录并记录。
   - 事件条图加 W 一行，目视抽查的结果写入报告。
8. **作业者片段**，写入 `gazelle_data\workdata\workers\worker_spans.json`：
   - **格式**：每个片段为 `{session, span_id, start_wall, end_wall, worker_id}`，时间用 B 的画面时钟，同样按 UTC epoch 编码。
   - **内容**：按[作业者分析](../analysis/2026-10-29-worker-identity-analysis.md) §3 的 11 个片段写入，`worker_id` 直接填 P1 至 P4（用户 2026-10-29 判定，片段表经 Q-024 确认）。
     - 机器可读的初稿在仓库外：`gazelle_runs\claude-workers-r1\worker_spans_draft.json`。
     - 初稿中旧录制的时间在代理时间轴上，新录制的时间在各摄像机的画面时钟上。写入时统一换算到 B 的时间轴，并记录换算。
   - **核实**：在两个交接时段（0903 的 00:14:00 至 00:19:35、1016 的 13:13:39 至 13:16:29）内，A、B 上没有确认的人脸，即宽度至少 200 像素、分数至少 0.5 的人脸。不一致时按 B 级报告，不自行改动片段。
   - **切分规则**：只在换人处切分；同一人离开后回来，不切分。交接时段从前一人最后一次确认的人脸，到后一人第一次确认的人脸，不属于任何片段。规则写进文件头；阶段 3 的 TASK-302 直接使用这个文件，不另行切分。
   - **隐私**：只存时间与编号，不存外观描述、图像或姓名。
9. **新分层的验证数据集** `gazelle_validation\roi_r2_2026_10\`（验证集设计 §11.2）：
   - **格式与记录**：与 `roi_r2` 同格式。manifest 记录 `cohort: "2026-10"`、种子 20261015、抽样规则，以及所用代理的 SHA-256。
   - **抽样**：
     - 每次录制 4 段，共 8 段。
     - 分层、缺口重抽与 `sync_uncertain` 排除，规则都与 `roi_r2` 相同。
     - 没有试标段。为此给抽样增加明确的“无试标段”选项，默认行为不变。
   - **作业者片段**：每段按时间重叠最多的作业者片段记录 `span_id`；完全落在无人时段内的片段，归入时间上最近的片段。不因归属重抽（验证集设计 §11.3）。
   - **类别**：使用与 `roi_r2` 相同的正式类别文件。
   - **不改旧数据集**：`roi_r2` 与 `roi_r2_trial` 不变，运行前后对两个目录各做一次 SHA-256 清单比较。
   - 不创建 `labels.json`。
10. **W 参考画面**：
    - **抽帧**：新数据集的每段另存 W 的逐步参考图，例如 640×360 的 JPEG，带 SHA-256。A/B/E 拼图的格式与检查不变。
    - **页面**：片段有参考图时，标注页面显示 W，可以收起；没有参考图时保持原样。标注仍只在全局视图上进行。
    - **冲突**：若与 TASK-125 的页面改动冲突，按 B 级交 Claude，其余各项照常完成。
11. **文档**：
    - 四份用户文档、`tools/workdata/README_CN.md` 与 `ANNOTATION_GUIDE_CN.md` 中写“7 次录制”的地方，改为按实际录制说明。
    - 写明 webcam 的角色、新数据集与新增的选项。
    - 同步更新 `tests/test_usage_docs.py`。
12. **测试**（默认隔离，不读真实视频）：
    - webcam 文件名的识别；未知文件名仍然报错；
    - 按录制合并更新清单与重封装报告时，旧行不变；
    - W 的无时钟基础映射：文件名时间的编码、PTS、b = 1；
    - 重叠只由 A、B、E 决定；
    - W 校准失败不阻塞 A、B、E；
    - W 代理的可选角色与输出尺寸；
    - W 不参与时钟抽查；
    - 作业者片段文件的校验：互不重叠、都在重叠段内、无人时段不属于任何片段；
    - 无试标段的抽样，以及 `cohort` 字段；
    - 回归：没有 W 的三机录制，输出与改动前一致。

### 非目标

- 不重跑、不改写旧 7 次的任何产物，也不为了代码指纹一致而重跑。
- 不做区域按录制配准（TASK-151，D27）。
- 不把 W 用于阶段 3 的计算。基线 B3w 属于 TASK-308。
- 不处理音频。
- 不创建正式 `labels.json`。
- 不改正式区域、完成标记、参考图与类别文件。TASK-125 的正式导出除外。

### 不可变约束

- **研究完整性**：遵守 AGENTS.md「Research And Data Integrity」。同步门槛、时钟抽查规则、抽样规则与旧数据集都不变；失败如实报告，不放宽。
- **数据**：源目录只读。派生数据只写到 `gazelle_data\workdata\`、`gazelle_validation\` 与 `gazelle_runs\task-150\`。
- **环境**：不修改环境，不安装，不下载。MediaPipe 在 CPU 上运行；开发阶段的遥测已经接受（GZ-23）。
- **隐私**：仓库中的报告只含汇总数字、文件名与时钟读数，不放图像，不写人名与企业名。

### 允许动作

- 读全库。
- 修改：
  - `tools/workdata/**`、`tools/validation/**`，包括标注页面；
  - 对应的测试；
  - 第 11 条列出的文档。
- 运行 L0 至 L2 的检查，并按下面“真实运行”一节做 CPU 与 FFmpeg 处理。
- 按协作方案 §4 在阶段 2 分支 `feature/stage2-correctness` 提交并推送，在 PR #6 发双语评论。
- 不新建分支或 PR，不合并，不 force push。

### 验收标准

1. **清单**：共 56 个文件，2 个 W 文件识别为 `cam_w`；旧 40 行的内容不变。
2. **重封装**：两个新 E 通过与旧 E 相同的检查；旧 11 个输出与报告中的旧行不变。
3. **基础映射**：两次新录制的 A、B、E 通过原门槛；W 的来源为 `filename_clock`。
4. **内容校准**：两次新录制的 A、E 对 B 通过原门槛；W 满足第 5 条的数值核对。若 W 不可用，原因写清。
5. **代理**：每次录制有 A、B、E 三段；W 可用时另有 W 一段，W 不可用时写明原因。各段帧数相同，逐帧的来源与 PTS 可以回溯；`20261023` 的中断按缺口记录。
6. **同步验证**：A–B、E–B 通过；A–E 通过或证据不足；W–B 的结论明确；A、B、E 的时钟抽查每次录制可评估比例 ≥ 90%。
7. **作业者片段**：9 次录制共 11 个片段，编号 P1 至 P4，与作业者分析 §3 一致；两个交接时段经检测核实。
8. **新数据集**：`roi_r2_2026_10` 共 8 段，每段的 `span_id` 按第 9 条的规则确定；manifest 记录 cohort、种子与代理哈希；`roi_r2`、`roi_r2_trial` 的 SHA-256 清单前后一致。
9. **旧产物不变**：旧 7 次在 `inventory`、`remux`、`timemaps_v2_base`、`timemaps_v3`、`keyframes_v3`、`sync_samples_v2`、`proxies`、`sync_validation_v3` 与 `roi` 下的文件，SHA-256 清单前后一致。共享文件按第 2 条处理。
10. **门与文档**：离线门全部通过，文档与测试同步。

### 验证命令（Codex 必跑，Claude 复跑）

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-150-pycache"
python -m unittest tests.test_workdata_tools tests.test_workdata_timemap tests.test_workdata_calibrate tests.test_workdata_proxies tests.test_workdata_sync_v3 tests.test_validation_sampling tests.test_validation_extract tests.test_validation_server tests.test_validation_labels tests.test_usage_docs -v
python -m compileall main.py gazelle tests tools
python -m unittest discover -s tests -v
python main.py --help
python main.py --list-models
python -m tools.docs check
git diff --check
git status --short
```

另跑标注页面的 Node 测试。所有 Python 命令使用 `Gazelle-next` 的解释器。

### 真实运行

- **内容**：CPU 与 FFmpeg 处理，包括重封装、画面时钟识别、校准、代理编码、同步验证，以及作业者片段的核实（MediaPipe，CPU）。
- **资源**：低于正常优先级，同时最多三个进程。预计需要数小时 CPU；不需要 GPU，不下载。
- **记录**：命令、解释器、版本、帧数、产物与清理情况。

### 需独立审查

是。本任务涉及时序、同步、数据集与评估协议。

### 风险与回退

- **共享文件**：改写共享文件会影响旧产物的来源核对，所以按第 2 条先查依赖。
- **W 的相关性**：W 的画面与 B 差别大，部分窗口的运动能量可能相关不足。允许 W 不可用，不阻塞其余结果。
- **代码指纹**：代码改动后，旧录制产物里的指纹不再与当前代码一致。这是预期的，不重跑。

### 依赖

- **第 5 轮**：TASK-140 第 2 轮（正式代理目录、切换与两个数据集）、TASK-124 第 2 轮、TASK-125（正式类别文件与标注页面）。
- **用户**：Q-022（匿名作业者编号）不阻塞本任务。

### 契约修订 r2（Claude，2026-10-29，第 5 轮审查后）

第 5 轮的产物与本契约原文不同的地方，以本节为准：

1. **轮次与依赖**：排在第 8 轮（第 6 轮审查后由第 7 轮顺延）。依赖 TASK-125 第 3 轮通过审查，因为新数据集复制的是那时的正式类别文件，其中手部类已换成 `#b6ff00`。
2. **正式代理目录**：两次新录制的代理直接生成到 `proxies\<录制>\`。
   - 在 `proxies\manifest.json` 中为它们追加记录，字段与旧 7 次相同：来源目录、所用映射的版本与 SHA、验证文件的位置、`sync_uncertain` 的步数与区间、视频 SHA。没有 v2 代理，v3 与 v2 的差记为 null 并写明原因。
   - 先把原 manifest 改名备份；旧 7 条记录逐字段不变，用备份核对。
3. **验证结果**：新录制的验证写入 `sync_validation_v3\`，即当前代码的输出格式，路径记入 `proxies\manifest.json`。旧 7 次的正式验证在 `sync_validation_r5\`，不改。
4. **不确定区间与时钟**：切点的不确定区间按 TASK-140 第 2 轮的规则，现已在拟合与细化中实现。时钟抽查按同源帧补读。报告每个切点的区间与步数。
5. **你在标注期间**：第 8 轮时用户可能正在标注 `roi_r2`，`labels.json` 与其备份会随时变化。
   - 本任务不读写 `roi_r2` 中的 `labels.json`、`labels.json.bak`，也不在 `roi_r2` 中运行抽帧或校验命令。
   - 第 9 条与验收第 8 条的前后核对，在 `roi_r2` 只比较 `manifest.json`、`classes.json`、`roi_reference.png` 与 `frames\**`。
6. **旧产物不变**（验收第 9 条）：另加 `sync_validation_r5`、`proxies_v1_20261029`、`timemaps_v1_20261029`，以及 `proxies\manifest.json` 的旧 7 条记录。
7. **标注页面**（第 10 条）：在 TASK-125 第 2 轮的页面上加 W 参考画面，第 2 轮的全部行为与 Node harness 保持通过。

### 契约修订 r3（Claude，2026-10-30，源目录迁移与新文件夹）

用户 2026-10-30 把各录制文件夹从上层的日文文件夹移到 `E:\Gazelle_Workdata\` 下，文件名与内容不变。Claude 只读核对（[源数据迁移核对](../evidence/2026-10-30-source-relocation-check.md)）：清单中旧 7 次的 40 个文件 SHA-256、大小与修改时间全部一致；2026-10-29 记录的 56 个文件大小与修改时间全部一致。同日出现新文件夹 `20261030`，见第 5 条。本修订优先于上文中与之冲突的条款。

1. **源根目录**：一律用 `E:\Gazelle_Workdata`。
2. **不改写带哈希的旧产物**：
   - `timemaps_*`、`sync_*`、`keyframes_v3`、`proxies*` 与两个数据集中记录的旧绝对路径，是生成时的出处记录。它们的 SHA-256 记在 `proxies\manifest.json` 与数据集 manifest 中，改写会破坏正式数据的哈希链，所以不改。
   - 打开源视频一律经清单（`root` 加 `relative_path`），不经这些记录中的绝对路径。发现某个工具直接打开记录中的绝对路径时，作为 B 级问题报告，不要改写数据。
3. **清单**：
   - `inventory.json` 的 `root` 改为新目录。改之前把旧文件改名备份；旧 40 行与备份逐字段相同。
   - 第 2 条的“旧内容不变”，以及验收第 1、9 条对清单的要求，相应改为：旧 40 行逐字段相同，`root` 为新目录，备份存在。
4. **重封装的出处检查**：
   - `remux_report.json` 旧 11 行的 `input` 记录的是旧绝对路径，不改。
   - `video_source.media_path` 等按绝对路径核对出处的地方，改为按相对清单根目录的路径加输入大小匹配，并核对清单中的 SHA-256 对应同一文件；相对路径或大小不同时仍然拒绝。
   - 测试（默认隔离）：在临时目录中把源文件整体移到另一个根目录、字节不变，出处检查通过；改动大小或相对路径时拒绝。
5. **新文件夹 `20261030`**（画面时钟 2026-10-29）：用户回答 Q-026 之前不接入，不做清单、重封装、代理或抽样。
   - 清单不得因它报错，也不得把它写入清单，例如用第 2 条的按录制选项，或明确排除并在报告中记录。
   - 留给接入它的任务：其中的 webcam 类文件名为 `20261030動作解析カメラ_<电脑时间>_Pro.mp4`，不以 `WIN_` 开头；全局摄像机的画面时钟换了格式与位置（没有星期），现有的时钟版式读不出来。
6. **根目录的非视频文件**：清单只收 `.avi` 与 `.mp4`，保持现状；不打开、不复制。
7. **文档**：`docs/usage/USAGE.md`、`docs/usage/USAGE_CN.md` 与 `tools/workdata/README_CN.md` 中的 `$raw` 改为 `E:\Gazelle_Workdata`，与本任务的其他文档改动一起提交。
8. **验收第 1 条**改为：清单共 56 个视频文件（`20261030` 不计），2 个 W 文件识别为 `cam_w`；旧 40 行逐字段不变；`root` 为 `E:\Gazelle_Workdata`。

### 契约修订 r4（Claude，2026-10-30，用户决定纳入 `20261030`）

用户 2026-10-30 决定把 `20261030` 纳入研究集（Q-026 第 1 项）；协调者安排由 [TASK-152](TASK-152-recording-20261030-intake.md) 在本任务之后接入，并让 2026-10 分层只有一个数据集。本修订优先于上文中与之冲突的条款，包括 §1 目标中“产出”所列的新数据集：

1. 第 9 条的抽样与数据集代码（`cohort` 字段、无试标段的抽样、每次录制独立的随机数生成器、`span_id` 的确定规则）与第 12 条的相应测试仍在本任务实现，用临时数据集验证。正式数据集 `roi_r2_2026_10` 的生成与验收第 8 条移到 TASK-152，在三次录制都接入后一次生成 12 段。本任务不生成这个数据集。
2. 第 10 条（W 参考画面）仍在本任务实现，用临时数据集测试，不生成正式数据集。
3. 修订 r3 第 5 条照旧：本任务不接入 `20261030`。
4. 作业者片段文件写入 9 次录制的 11 个片段；`20261030` 的片段由 TASK-152 追加。
5. 用户 2026-10-30 确定了 W 的用途（D28）；协调者安排 W 的补充、二次验证与基线 B3w 都由阶段 3 的 TASK-313 实施，本任务不做（上文非目标中的“基线 B3w 属于 TASK-308”相应改为 TASK-313）。二次验证依赖 W 的同步，所以 W–B 的门槛不变：W 未通过时仍只把该录制的 W 标为不可用，并写明原因；W 的逐步 `sync_uncertain` 标记照常写入。

### 契约修订 r5（Claude，2026-10-31，第 8 轮审查后；第 9 轮执行）

依据[第 8 轮审查记录](../evidence/2026-10-31-round8-review.md) §5 与本任务 §3 的发现。本修订优先于上文中与之冲突的条款。第 1 至 9 条现在就做，第 10 条要等用户回答 Q-032。

1. **切点规则**（Q-029，协调者决定的缺陷修复，门槛数字不变）：
   - `refine_breakpoints` 的候选切点必须落在该切点 `adjacent_window_centers` 的闭区间内。没有候选时保留粗切点，`refined=false`。
   - A、E、W 都适用。这是本轮唯一授权修改的受保护函数，其余采样、映射与拟合组件继续按 AST 核对。
   - 旧 7 次不重跑。它们的 4 个切点都在区间内，Claude 在内存中验证过，加规则后切点与尾部完全不变。
   - 这条改的是原第 5 条冻结的拟合函数，也是看过失败之后定的：内存模拟中 1016 E 恰好以 5/50 通过，1023 E 已通过的两个切点也会移动。Q-032 向用户说明了这一点，用户可以推翻。
   - 测试：区间外的候选被拒；区间端点可取；没有候选时保留粗切点；用 1016 E 的实际窗口数字写默认测试（数字夹具，不读正式数据）。
2. **重新拟合**：
   - 本修订的代码全部提交之后再运行，否则实现哈希过期，产物会记 `code_worktree_dirty=true`。第 9 条同样如此。
   - `20261016`、`20261023` 用 `--reuse-samples` 从已存样本重新拟合，不重新解码。失败的映射先改名保留为 `*.before-task150-r5`，因为这个选项要求目标文件不存在；不需要另设输出路径。采样 SHA 不变是前提，见第 3 条；`refine_breakpoints` 不在采样指纹内。
   - 预期（Claude 内存模拟）：1016 E 有效，尾部 10.0%，切点约 1135.2，不确定区间约 [1110.3, 1160.2]；1023 E 有效，尾部 3.6%，切点约 1175.4、1595.1；1023 A 仍失败，尾部 13.2%。实测不同时按 B 级报告，不调整方法去迎合。
3. **路径解析**（Q-031）：
   - 这些位置直接打开记录的路径：`sync_calibrate.run`、`proxies.full_mapped_frames`、`prepare_camera`、`proxies.run`、`keyframes.source_keyframes`、`ProxyClockReader._pair`。在调用方加一层只在内存中工作的解析：记录的路径不可用时，按清单的 `root` 加相对路径找到文件；E 的重封装文件不在源目录，记录的路径仍然有效时不解析。
   - `full_mapped_frames`、`sample_camera`、`source_keyframes` 的 AST 不变，由调用方先换好内存中的 `media_path`。前两个在采样指纹内，`source_keyframes` 在受保护组件内。采样 SHA 必须保持 `7c6c32f4…`，否则第 2 条不能复用已存样本。
   - 清单由命令行传入：`sync_calibrate`、`proxies`、`sync_validate` 增加 `--inventory`；不传时行为与现在相同。
   - 核对只比对记录，不重算整文件哈希：映射行 `fingerprint` 的 `source_sha256`、`media_size` 与清单行的 `sha256`、`size_bytes` 相同，磁盘文件大小也相同；不同时拒绝。
   - 不改写任何带哈希的旧数据，不重跑旧录制。
   - 测试：在临时目录中把源文件整体移到另一个根目录，这些入口都能打开；大小或 SHA 不同时拒绝。
4. **W 的隔离**（§3 发现 1、3、4）。W 失败不得挡住 A、B、E：
   - `export_events` 中 W 一行读帧或缩略图核对失败时，把 W 标为不可用，重新导出不含 W 的条图，A、B、E 的验证结果照常写出。
   - W 分支的异常保护覆盖 PyAV 的 `av.error.FFmpegError` 与 `KeyError`，涉及 `webcam.py`、`sync_validate.py`、`proxies.py`、`timemap.py`。
   - `read_webcam_reference` 发现证据过期或被移动时，这次录制的 W 不进入参考图，manifest 写明原因，A、B、E 的抽样照常进行。索引缺记录时同样写明原因，不静默。
   - W–B 失败时 `reason` 写出没有满足的具体条件。
5. **W 参考画面的页面**（§3 发现 2）：
   - 换步时不得折叠面板：用 `visibility` 或固定比例的容器保留占位，时间轴与主图不跳动。图片未就绪时不显示上一步的图。
   - 面板移到时间轴与类别按钮之后。1500×950 的窗口内，时间轴的位置与没有 W 时相同。
6. **作业者片段**（Q-030，协调者决定）：
   - 用户确认的边界不变。交接核实改为：除区间最后 10 秒以外，A、B 上没有确认的人脸。`20260903` 最早命中距区间末 8.3 秒，`20261016` 2.4 秒，都满足。这改动了原第 8 条的核实条件，10 秒是看到 8.3 秒之后定的，Q-030 已写明，用户可以推翻。
   - 新录制初稿的时间直接按 B 的时钟使用：这两次录制 A、E 的基础时钟与 B 只差约 0.01 至 0.40 秒，小于边界约 5 秒的精度。外端裁到最终映射的重叠段内。
   - 两次录制的最终映射都确定之后，才写入正式 `workers\worker_spans.json`，文件头写明规则与精度（验证集设计 4.5.0 §11.3）。`20261023` 等 Q-032 时，这一步也等。
   - `plan` 拒绝 `status: review-only` 的候选文件；`coverages` 由生产调用传入，片段超出重叠段时报错；隐私校验覆盖文件头与交接行，只允许规定的字段。
7. **测试补强**（§3 发现 6）。审查用的 57 个变异有 39 个存活，清单在仓库外 `gazelle_runs\claude-review-r8\reviewers\task150\mutation-results-all.json`。除判定为可接受的 5 个（`rem_unknown_session`、`s_pilot_flag_ignored`、`t_fingerprint_no_webcam`、`c_fingerprint_no_webcam`、`p_fingerprint_size`）之外，其余 34 个都要失败。主要缺口：
   - W 校准的参数顺序（符号）、关键帧掩码、失败的拟合不得写入；
   - `timemap.run`、`sync_validate._run`、`proxies.run` 层的 W 分支；
   - 参考图与片段的对应、逐步的不确定与缺口标记、尺寸与哈希、续跑；服务端夹具改回同时覆盖有 W 与无 W；
   - 页面：图片未就绪时不显示旧图、加载失败不挡标注、W 不计入已看步；
   - 作业者片段：无人时段的拒绝用例（第 12 条明列）、额外字段、按区间而不是按点归属；
   - 重跑时清单与重封装不产生重复行。
8. **小项**（§3 发现 5、7）：
   - W 的文件名规则放进 `camera_roles.json`，`inventory.py` 与 `webcam.py` 共用一处解析，TASK-152 只需加一条规则。
   - `--session` 配错 `--root` 时报错，不改写 `root`。重跑旧录制时行序不变。重封装重跑失败时保留原来的有效行。
   - 在报告中写明：不带 `--session` 的重封装从重写变为合并。
9. **继续第 8 轮没有运行的部分**：
   - `20261016`：代理（含 W）、代理残差验证、时钟抽查、事件条图、`proxies\manifest.json` 追加，方法与门槛不变。这次录制的重叠段有内部缝隙，需要 `--allow-internal-gaps`，写入 `session.json`。
   - `20261023`：A 没有校准，`proxies.run` 会拒绝，这一次录制等第 10 条。第 10 条实施后走同样的步骤，同样需要 `--allow-internal-gaps`。
   - 任一对验证失败时保留代理，停在这里报告，不写索引。预演显示 1016 的 E–B 恰好 90.0%，A–E 漂移 0.122 秒/小时，都可能失败。
10. **同步复核规则：用户在 Q-032 选择推荐项之后才实施**。只用于 `20261016`、`20261023`、`20261030` 及以后的录制。
    - **拟合**：门槛结果恰为 `residual_tail_exceeds_0_2` 时，用同样的信号计算 120 秒窗口（步长 60 秒），对同一条拟合线算残差，按 `residual_summary` 的四个条件判定：±0.2 秒内不少于 90%、中位绝对值不超过 0.1 秒、中点偏差不超过 0.1 秒、漂移不超过 0.1 秒/小时。通过时 `valid=true`、`reason='valid_second_look'`，窗口与四个数字写入 `second_look`。拟合系数不变。
    - **代理验证**：A–B 或 E–B 只因 ±0.2 秒占比不足而失败时，按同样的办法在代理信号上复核；其他条件失败时不复核。
    - **A–E**：不通过时，120 秒窗口下中位绝对值与中点偏差都不超过 0.15 秒、漂移不超过 0.15 秒/小时，就不挡住录制；超过时录制不通过。A–E 的 ±0.2 秒占比这一条不再要求。数字照常写入验证文件。
    - **记录**：每次录制记 `sync_grade`：全部按原门槛通过为 `official`，用过上面任何一条为 `second_look`，写入验证文件与 `proxies\manifest.json` 的新记录。旧 7 次的记录不动，缺这个字段时视为 `official`。
    - **预期**（离线预演，不是真实代理）：1023 A 的拟合在 120 秒窗口下 96.3%；1023 A–E 中位 0.112、偏差 −0.103、漂移 −0.089；1016 A–E 中位 0.043、偏差 −0.008、漂移 0.144。
    - 用户选择其他选项时，Claude 另写修订，这一条作废。
11. **验收调整**：
    - 第 4、6 条：1016 与 1023 的 E 按原门槛；1023 的 A 与两次录制的 A–E，用户选择 Q-032 的推荐项时按第 10 条。在那之前，这几项如实记为未通过。
    - 第 7 条：两个交接时段按第 6 条核实。
    - 其余验收不变。旧产物不变的核对范围相同，另加 `timemaps_v3` 中改名保留的失败映射。

### 契约修订 r6（Claude，2026-10-31，用户回答 Q-032 之后）

用户 2026-10-31 回复“确认 Q-032，选 1”，r5 第 10 条生效。规则的正式文本是[验证集设计](../../design/VALIDATION_SET_DESIGN.md) §11.7（5.0.0）。它与 Q-032 或 r5 第 10 条不一致时按更严的一条执行，并按 B 级报告。规则到此写定。下面只写实施方式，本修订优先于上文中与之冲突的条款。

1. **时机**：Claude 审查完第 9 轮已交回的部分、把 `next_actor` 改为 `codex` 之后才开始。审查要稳定的目标。
2. **开关**：`sync_calibrate`、`sync_validate` 增加 `--second-look`，默认关闭；不传时判定结果与现在相同。旧 7 次与 `20261016` 不重跑。
3. **W 不复核**（协调者写定时补充）：W–B 按原门槛，失败时只把这次录制的 W 标为不可用，不影响 `sync_grade`。
4. **受保护组件**：
   - 48 个受保护组件的 AST 按 `c1b8416` 核对，全部不变，本修订没有获准改动的受保护函数。`_fit_gate`、`fit_calibration`、`refine_breakpoints`、`window_lags`、`lag_peak`、`_line` 都在其中。
   - `residual_summary`、`session_passed` 不在这 48 个之内，也不改，验收时加入 AST 核对。`window_lags` 已支持 120 秒窗口。
   - 复核写成新函数，由 `sync_calibrate.run` 与 `sync_validate._run` 调用。采样 SHA 保持 `7c6c32f4…`。
   - 拟合层的新函数放在 `sync_calibrate.py`。`residual_summary` 只能在函数内导入，因为 `sync_validate` 在模块顶层导入 `sync_calibrate`。不要调用 `corrected_time`：这时 `valid` 为假，它会报错。
   - `implementation_hash` 不含 `sync_validate.py`，也不改；`fit['second_look']` 记录 `sync_validate.py` 的 SHA-256。
5. **拟合层**：
   - 在 `refine_breakpoints` 之后、写入 `row['calibration']` 之前判定，只处理 A、E，`reason` 恰为 `residual_tail_exceeds_0_2` 时才运行。
   - 窗口用 `window_lags(signals['cam_b'],signals[camera],window=120.,step=60.)`。有效窗的时间取 `t=t_mid_seconds+lag_seconds`，按 `corrected_time` 的规则归入 `segments`；有切点时，跨切点的窗口也这样归段，不剔除。残差为 `lag_seconds-c0-c1*t`。
   - 残差替换 `lag_seconds` 后交给 `residual_summary(rows,fit['duration'])`，`passed` 为真才算通过。
   - 无论是否通过，窗口与四个数字都写入 `fit['second_look']`。通过时 `valid=true`、`reason='valid_second_look'`；`segments`、`residual_mad`、`residual_tail_fraction` 保留原值。
   - Claude 用现有映射与缩略图按这个算法在内存中算过：`20261023` A 有效窗 54/59，±0.2 秒内 96.30%，中位绝对值 0.036 秒，中点偏差 0.002 秒，漂移 0.034 秒/小时，四项都过。这是预演，以实测为准；实测不同时按 B 级报告，不调整方法去迎合。脚本在 `gazelle_runs\claude-review-r9\data\fit_second_look.py`。
6. **`20261023` 重新拟合**：
   - 本修订的代码全部提交之后运行，同 r5 第 2 条。
   - 现有失败映射 `20261023.json`（SHA `255a798a…`）先改名保留为 `20261023.json.before-second-look`，不得覆盖已有的 `20261023.json.before-task150-r5`。
   - 用 `--reuse-samples --second-look --inventory …` 重新拟合，不重新解码。A 的窗口与系数、E 与 W 的窗口、系数、切点、有效状态与尾部值必须与现有映射相同。比较时排除必然变化的字段：`calibrated`，A 的 `valid`、`reason`、`second_look`，A 各行新增的 `calibration`，`cameras.cam_a`，`overlap`，以及各处的 `implementation_sha256` 与 `fingerprint`。不相同时停下，按 B 级报告，不生成代理。
7. **代理验证层**：
   - `pairs[name]` 的 `conclusion`、`passed`、`reason` 仍是 60 秒窗口、原门槛的结果，复核结果写在 `pairs[name]['second_look']`。
   - A–B、E–B 的 `reason` 恰为 `fraction_within_0_2 < 0.9` 时才复核。A–E 的 `conclusion` 为 `failed` 时复核；`insufficient_evidence` 沿用原规则，不复核。
   - 带 `--second-look` 时，`synchronization_passed` 与 `passed` 由新函数按 §11.7 计算。不带时结果等于 `session_passed`，不写 `sync_grade`；这时映射里有 `valid_second_look` 就报错退出。
   - `sync_grade` 写入验证文件顶层与索引行。同步未通过时为 null，不省略。同步通过时，`mapping['calibration']` 的 A、E 有 `reason=='valid_second_look'`，或代理验证用过任何一种复核，就是 `second_look`，否则是 `official`。
   - 读取 `sync_grade` 写成一个函数，放在 `tools/validation/sample_segments.py` 读取索引的地方：旧 7 次缺字段视为 `official`，其他录制缺字段报错。TASK-152 复用。
8. **`20261016`**：不重跑，验证文件也不改：它写于这条规则之前，SHA 记在索引行与 W 的绑定中。这是 r5 第 10 条“写入验证文件”的唯一例外。第 9 轮审查通过后，在它的索引行加 `sync_grade: official`，并更新 `acceptance_status`。做法与追加相同：先保留备份，再核对旧 7 行逐字段不变。审查不通过时按审查结论处理。r5 第 10 条“预期”中 1016 的数字是预演，实测以 §2 为准。
9. **继续 r5 第 9 条**：`20261023` 的代理（`--allow-internal-gaps`）、四对残差（`sync_validate --second-look`）、时钟抽查、事件条图。验证文件顶层 `passed` 为真之后追加索引；W–B 失败只把 W 标为不可用，不挡索引。验证文件的目录与 `20261016` 相同，以第 9 轮审查的确认为准。`append_proxy_manifest.py` 现在要求全部 `pairs` 通过，并写死了 `20261016`，要相应修改。按规则仍失败时保留代理，不写索引，按 B 级报告，不调整规则。
10. **正式作业者表**：两次录制的最终映射都确定之后写入，同 r5 第 6 条。文件头依据验证集设计 5.0.0 §11.3。
11. **文档与测试**：
    - 四份用户文档与两份中文指南写明 `--second-look`、`sync_grade` 与它们的含义。
    - 测试默认隔离，覆盖三种情况各自的通过与失败、边界值（0.9、0.1、0.15）、中点偏差与漂移为负值时按绝对值判定、有切点时的归段、不该复核时不运行、证据不足、W 不复核、默认关闭时与现有结果相同、`sync_grade` 的取值，以及缺字段时旧 7 次视为 `official`、其他录制报错。
12. **验收**：r5 第 11 条第 1 点改为：第 4、6 条按 §11.7 判定，`20261016` 不重跑。其余两点不变。另核对受保护组件与采样 SHA，核对改名保留的映射，核对旧 7 条索引行不变。需要独立审查。

### 契约修订 r7（Claude，2026-10-31，第 9 轮审查后；与 r6 一起执行）

依据[第 9 轮审查记录](../evidence/2026-10-31-round9-review.md) §3 与本任务 §3。本修订优先于上文中与之冲突的条款。先完成并提交本修订与 r6 的代码，再运行 r6 的真实步骤。

1. **路径解析闭合**（r5 第 3 条的缺口）：
   - 磁盘 `st_mtime_ns` 必须等于清单行 `mtime_ns`，映射行 `media_mtime_ns` 也必须等于它，不等时拒绝。Claude 2026-10-31 核对：56 个文件与 43 行映射全部相等。
   - 去掉内存中的 mtime 副本。比对通过后 mtime 本来就相同，`checked_source` 对解析后的路径同样比较 mtime。
   - 清单行 `needs_remux` 为真、记录路径失效时直接拒绝，不用 AVI 顶替重封装文件。
   - 测试加：搬迁后 mtime 改变的文件被拒绝；同大小不同内容、mtime 不同的文件被拒绝。
2. **W 分支的异常**：`sync_validate`、`proxies`、`sync_calibrate`、`timemap`、`sample_segments` 的纯 W 分支改用 `except Exception`，记录 `error_type`。A、B、E 的路径不改。
3. **测试**：
   - FFmpegError 用例必须用不继承 ValueError、OSError、RuntimeError 的类，例如 `av.error.ExternalError`，并覆盖条图路径；条图路径也要有 KeyError 用例。
   - 搬迁测试覆盖 W、经 `_run` 的非空 `indices`、三个 CLI 的 `--inventory` 接线、`checked_source`。
   - `gazelle_runs\claude-review-r9\reviewers\task150\results\mutation-classified.json` 中 `classification` 为 `test-gap` 的 40 个变异要失败，定义在同目录上一级的 `scripts\`，代码移动时按原义改写，第 1、2 条改写的代码按新行为对应。主要是：索引缺记录的原因、隐私校验、旧录制的覆盖来源、`timemap.run` 第一层分支、负的 `c0`。其中 `n_sp_keep_old_mtime`、`n_sp_checked_mtime_always` 的结果就是第 1 条要求的新代码，不计入；它们的反向变异（恢复内存副本、对解析路径不比 mtime）要失败。
   - 补一个用例：重跑清单时已消失文件的旧行怎样处理。
4. **文档**：
   - `tools/workdata/README_CN.md` 写明 `--inventory`、`webcam_unavailable`、`review-only`、切点的闭区间规则，并加进文档测试。
   - `docs/usage/USAGE.md`、`USAGE_CN.md` 关于修改时间的一句按第 1 条核对，已成立就不改。
5. **小项**：
   - `inventory.py` 换 `--root` 时同时比较 `mtime_ns`，补 `n_inv_wrong_root_size`、`n_rem_failed_any_status`、`n_rem_failed_invalid_kept` 三个用例。
   - 写入正式作业者文件时必须带全部文件头；`span_id` 限定为 `<录制>_worker_<n>`。
   - `timemap.run` 一次录制只有一行 W 且失败时不得报 UnboundLocalError。第 310 行把 KeyError、FFmpegError 用于 A、B、E 的做法保留，写入报告。
   - `sync_check.py` 打开记录路径、要求全部行有效。它是可选的旧诊断，不改，在报告中写明。
6. **验证文件的目录**：新录制的验证写入 `sync_validation_r5\`，这是正式目录。修订 r2 第 3 条的 `sync_validation_v3\` 作废，r6 第 9 条的“目录与 `20261016` 相同”就是这个目录。
7. **作业者表**：候选片段 `20261016_worker_2` 超出最终重叠段 0.167 秒，写入前按最终映射裁剪，同 r5 第 6 条。
8. **`20261016`**：第 9 轮审查已通过它的代理与验证，r6 第 8 条的索引更新可以执行，`acceptance_status` 写 `Claude round-9 review accepted; user acceptance pending`。

## 2. 实施报告（Codex 追加，勿改上文）

### 第 8 轮实施记录（Codex，2026-10-31；实现待审，真实数据受 B 级问题阻塞）

- 以实时 STATE 接手，沿用 `feature/stage2-correctness` 与 draft PR #6；主线程 Inline Execution，无子代理。实现提交 `397c5d168ceaa67d0424659623232f548c65fe0d` — `Support selected recordings and optional synchronized webcam references` 已推送；[实现检查点](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6527893311)。本节不是独立验收。
- 代码：清单、重封装可重复传 `--session`，保留未选录制的行；迁移后的 E 来源按相对路径、大小、清单 SHA 核对。严格识别 `WIN_YYYYMMDD_HH_MM_SS_Pro.mp4`，W 以文件名电脑时钟加原生 PTS 建图，不改 OSD 版式。W 单列于 `auxiliary_cameras`，同一 5 Hz 网格上沿用现有校准方法、720p 无音轨代理与 W–B 门槛，失败不挡 A/B/E。
- 抽样与标注：新增 `--no-pilot`、`--cohort`、`--worker-spans`，每次录制的随机数独立；按最大重叠、无人时段最近片段、相同则较早片段归属，不重抽。通过 W–B 验证并绑定映射、session、视频 SHA 后，才把 W 纳入参考图；640×360 JPEG 逐张带哈希、缺口和不确定标记。页面可收起 W，注视点仍只在 E 标注。无 W 的 payload、拼图与默认旧 7 次抽样保持原行为。
- 契约保护：`check_implementation.py` 比较 **21 个采样、映射、A/E 运动/拟合组件的 AST，全部不变**；采样 SHA 为 `7c6c32f413379ddb023dcfc07295376aec727bf12bffb13af2f6e3461ac6d77d`。旧映射、代理不因新实现指纹而重跑。正式 `roi_r2` 的 `labels.json`、`labels.json.bak` 未读写，不在该目录运行提取或校验；正式区域与导出不改。

#### 命令、检查与实际活动

- 所有 Python 使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，字节码在仓库外 TEMP；未安装、卸载或修改环境。外部证据目录 `gazelle_runs/task-150/`，数据在 `gazelle_data/workdata/`，源 `E:\Gazelle_Workdata` 只读。没有接入 `20261030`，没有生成 `roi_r2_2026_10`。
- 核对版本：Python 3.14.8、PyAV 19.0.1、NumPy 2.5.4、OpenCV 5.0.0.93、MediaPipe 1.1.1；FFmpeg/ffprobe 为预检中的 `2025-03-31-git-35c091f4b7-full_build-www.gyan.dev`。结束检查确认两个校准 PID 不存在；命令组合的最后一个 `Get-Process` 因进程已退出返回 1，不是 docs/check 或校准之外的新失败。
- `run-gate.ps1 -Tag task150`：`python -m compileall main.py gazelle tests tools`、`python -m unittest discover -s tests -v`（**744 tests / 35.344s / 0 skip**）、`python main.py --help`、`python main.py --list-models`、两个 Node harness、`python -m tools.docs build`、`python -m tools.docs check`、`git diff --check` 均 exit 0。合成坏 MP4 的 `moov atom not found` 与 Git LF/CRLF 提示为非致命消息。TDD 红/绿记录在 `*-red.log`、`*-green.log`；功能门 `task150-gate.json` 逐命令保存退出码。
- 临时浏览器数据集的 **7 项实际检查通过**：W 640×360、步 2 对应图片、不确定提示、收起、展开、无 W 隐藏、原拼图 1920×720。证据 `webcam-browser-checks.json` 与合成截图 `webcam-browser.png`；测试标签独立，8810 服务停止、标签页关闭。最初两次定位器不匹配，改用实际 DOM 定位后成功；不是页面故障。未把本次内置浏览器检查称为 Edge 真实按住重复验收。
- `audit_before.py`：预先列明 **16,836 文件 / 87,442,562,724 字节**；共享 inventory/remux report/proxy manifest/ROI candidates 的整文件 SHA 在已保护 JSON 中未发现依赖（`shared-hash-dependencies.json`），随后按契约保留旧行。inventory 原文件改名 `inventory.before-task150-20261031.json`；旧 40 行逐字段不变，root 更新为新根，清单现 **56 文件 / 2 W**。
- `run_intake.py` 调用 `create_inventory(..., sessions=['20261016','20261023'])`、`run_inventory(..., sessions=...)`，无 `--force`。两个新 E 实际 FFmpeg stream-copy 重封装通过包数、PTS、时长、头/中/尾解码与 EOF 检查；有效输出分别 **54,058 / 54,296 包**，空小包全部去除。旧 11 条报告逐字段不变，报告合计 13 条。命令与检查在 `remux-result.json`，未上传视频或派生 JSON。
- 两次 `python -m tools.workdata.timemap --inventory .../inventory/inventory.json --remux-root .../remux --out-root .../timemaps_v2_base --session <日期>` 均 exit 0：1016 的 7 文件、1023 的 9 文件全部 valid；E 分别 352、360 个锚点。W 各完整扫描原生 PTS，来源为 filename_clock、b=1，不读取画面时钟。`base_summary.py` 核对当前实现 SHA 与覆盖。1023 的 A/B 大缺口均在文件边界，**5.985482693 / 5.952110529 秒**，另有 0.124、0.093 秒边界缝；E 连续。
- 两次 `python -m tools.workdata.sync_calibrate --timemaps .../timemaps_v2_base --out-root .../timemaps_v3 --samples-root .../sync_samples_v2 --keyframes-root .../keyframes_v3 --session <日期>` 均已结束，**exit 1**，分别因 1016 E、1023 A 的尾部残差超限；详见 B 级问题。实际优先级检查为 BelowNormal（16384），本轮长 CPU 作业最多三个；所有作业和临时服务已结束。
- 0903 交接核实：`check_handover.py --session 20260903` 在 B 时钟开区间 00:14:00–00:19:35，对 A/B **各 6,700 个原生帧**用缓存 `blaze_face_full_range.tflite`、CPU、1920×1080 检测，宽度换算到 4K ≥200、分数 ≥0.5。A **81 命中帧**，B **64 命中帧（65 次检测）**；以源文件与 PTS 去重后修正了原先把检测次数当作帧数的记录；首个分别为 00:19:26.725725、00:19:31.082138，脚本 exit 1。目视六张命中帧确认实际人脸。最初按重叠起点取日期，跨午夜使错误日期无帧而误报通过；原失败证据保留为 `handover-20260903-initial-date-error.*`，改为重叠中点日期并断言区间、非零帧后重跑，以上只使用重跑结果。
- MediaPipe 模型 SHA `3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b`，复用缓存，无下载、无 Gazelle/CUDA 推理。开发阶段遥测按 GZ-23 许可，未做包级网络审计。实际活动还包括本机 HTTP/浏览器、CPU 解码、FFmpeg、GitHub；Git/GitHub 沿用获准 yun 上下文，不复制凭据。图片仅在本机证据目录，不进仓库。
- 六份用户/工具说明及文档测试已同步。当前只实现新分层能力，正式生成由 TASK-152 负责。
- 后续自查发现 W 图片的内联 `display:block` 会覆盖 `hidden`。在合成服务 8811 将步 1 图片延迟 25 秒，实际浏览器复现 `hidden=true` 但 computed display=block；改为仅在 `:not([hidden])` 时 display:block。重跑变为 display=none，加载后恢复 block、640×360。证据 `webcam-delay-check.json`、`webcam-browser-fixed.png`；临时服务和标签页已关闭。修复没有改变文档所述行为；`run-gate.ps1 -Tag task150-final` 重跑完整门 **744 tests / 38.588s / 0 skip**，其余八项同样 exit 0，结果为 `task150-final-gate.json`。
- `audit_after.py` 对预先列明的 **16,836 文件**重新计算 SHA，**338.266s、exit 0**；只有允许追加的 inventory 与 remux report 整文件 SHA 改变，旧 40 行、11 条报告及 7 条代理索引逐字段相同，inventory 改名备份 SHA 等于旧文件。其他旧产物、两个数据集的限定元数据/帧均逐字节不变。初跑已列出的变化同样只有两个共享文件，但检查器的正反斜线比较不一致导致 exit 1；修正外部脚本后完整重算，失败日志 `protection-after.log` 保留，正式结果为 `protection-after-fixed.log`、`protection-result.json`。共享代理索引的后续追加另做旧行核对。
- 1016 交接核实独立使用已通过的 A→B 校准与 B 基础映射，不依赖失败的 E。`check_handover.py --session 20261016` 实际检查 A/B **各 4,250 帧**，A **20 帧**、B **43 帧**命中；最早分别为 B 时钟 **13:16:27.007591 / 13:16:26.601678**，均位于契约交接区间内。273.977s，exit 1；首个、最高分、最后一个共六张实际帧经目视确认有人脸，证据 `handover-20261016-summary.json` 与本机 `handover-20261016-hits.jpg`。没有据此识别身份或修改 P1/P2 边界。
- 两次八组灰度样本完整扫描到 EOF并通过像素 SHA 复核，1016 每机 **18,018 步**，1023 每机 **18,099 步**。A/B/E/W 的实际解码帧数分别为 1016 **117253/90664/54058/161708**、1023 **137755/93002/54296/161707**。`final-data-audit.json` 保存映射、旁注、像素 SHA，核对全部 16,836 保护文件在完整哈希后大小和 mtime 不变；正式代理索引 SHA 与本轮前相同。
- **未运行项**：两次正式代理、代理残差验证、9 个时钟抽查/录制、事件条图与正式索引追加，均因必需校准失败而未运行，不以模型拟合通过代替代理 W–B 验收。`run_proxy_validation.py`、`make_clock_samples.py`、`append_proxy_manifest.py` 已准备但未执行；原时钟抽样脚本复制为 `check_proxy_clocks.original.py`，计划方法仍为固定种子 `20261015 + int(session)`。没有生成正式旁注，故没有正式 `sync_uncertain` 步数；`cut-diagnostics.json` 仅记录映射切点在原采样网格上的诊断投影：1016 E 区间 [1070.138509,1100.279277] → 151 步；1023 E 两区间 [1140.362641,1200.324615]、[1620.357520,1673.666389] → 301、268 步，均 localized。其余拟合无切点；这些数字不是可用于抽样的正式标记。
- 作业者只在本任务运行目录生成 **9 次 / 11 段**的 `worker_spans_candidate.json` 和 `worker-conversion-review.json`，带 review-only/阻塞说明。旧 7 次原本已在 B 代理轴，外端点裁到重叠范围；新录制保留原时钟为候选，并列出可用摄像机校准的替代换算。格式、非重叠、范围和交接排除校验通过，**正式 `workers/worker_spans.json` 未创建**，不能把候选当作已确认数据。

#### 自主决定（A 级）

- W 的接口与错误隔离按契约单列，参考图必须有绑定的通过验证；重用既有 A/E 算法而不复制改写研究门槛。临时数据覆盖新 schema，原有三机路径回归通过。
- 用原生逐帧核实交接，比先前约 5 秒抽样细；不据此自行改动匿名片段边界。无效的日期初跑、定位器失败等保留证据，不计作成功。
- 等待真实处理时，只在仓库外准备 TASK-140 测试并在隔离进程内做变异；生产代码、正式数据不受改写。13 个变异全部触发断言失败，结果待 TASK-140 正式报告归档。

#### 范围外改动

- 无。相邻 ROI 提取代码只复用本任务要求的迁移后重封装来源校验，没有运行正式候选提取。

#### 待 Claude 判断（B 级）

0. **1016 必需的 E 校准失败，依赖它的代理与验证暂停**：A 51/60 有效窗、MAD 0.055943、尾部 2/51；W 52/60、MAD 0.042401、尾部 4/52，B 时钟 13:25/13:50 处 W 电脑时钟减 B 为 **−2.384729 / −2.443956 秒**，两处数值核对通过。E 50/60、MAD 0.039280，但尾部 **6/50=12% >10%**，校准命令 exit 1，正式映射保留 `calibrated=false`（SHA `d9a60b922b5f2f0a8dc63d9367f90fd2a04dc6303ba951f7d2a45f56a560ce5b`）。对同一已存窗口的只读诊断发现，原算法细化前为 5/50=10%，细化把切点从 1140.190933 移到 1085.208893 秒后变为 6/50；没有采用粗拟合替换正式失败结果。推荐 Claude 审查切点细化目标与最终门的关系，另行决定是否制定保留有效粗拟合的规则；代价是需要新的协议与独立验证。本轮不改 A/E 的受保护函数，不剔除窗、不放宽门槛、不生成 1016 代理或把它写入正式索引。`fit-gate-diagnostic-20261016.json` 保留六个尾部窗及相关强度，`calibration-summary-20261016.json` 保留完整数值核对。
   - **1023 必需的 A 同样失败**：53/60 有效窗、MAD 0.054952、尾部 **7/53=13.2075%**，无切点，细化前后相同。E 55/60、MAD 0.051328、尾部 4/55；W 56/60、MAD 0.072269、尾部 3/56，均通过拟合；B 时钟 14:05/14:35 处 W 偏移 **−0.575497 / −0.745526 秒**（按契约仅报告）。映射 SHA `32251e2195c6dbd2a8c9dd629b1eee6a6b5c634aa0887a505a530c7c22954b2f`、`calibrated=false`。推荐 Claude 从已存七个尾部窗及空间运动选择证据复核适用性；继续保留失败，不通过丢弃窗口、改变门槛或重新选样本取得通过。此项与 1016 共同阻塞两次正式代理及 TASK-152 的后续数据生成，相关跳过项写入 `skipped-actions.json`。
1. **0903、1016 的交接区间前提均不成立**：命中数字与本机图像如上。推荐 Claude 复核最后/最早有效人脸的精确 B 时间后修订边界；Codex 不自行挪动边界，不发布会被 TASK-302 消费的正式 worker_spans。约 5 秒采样与逐原生帧检查的粒度差异可能解释较早入场，但不是改写契约的授权。
2. **历史重处理工具直接打开记录中的绝对路径**：`sync_calibrate.run`、`proxies.full_mapped_frames/prepare_camera/run`、`keyframes.source_keyframes`、`sync_validate.ProxyClockReader._pair`。新录制的映射使用新根，当前处理不受影响；旧录制在迁移后重处理会失败。推荐另以清单 root + relative_path 在外层解析到内存路径，并保留原哈希记录；本轮没有改写旧产物或受保护采样函数。
3. **新录制作业者边界的时钟来源未逐项注明**：初稿与分析说明使用各摄像机自己的画面时钟，不能无证据统一当作 B。推荐 Claude 结合原检测记录明确 1016 两个内边界的来源摄像机，再按已通过的 A→B 映射转换；本轮给出候选换算供复核，不发布未确认的正式值。

#### 待用户决定（C 级）

- 无。尚待 Claude 独立审查与用户独立 checkout 验收。
- 图片加载补修与完整报告提交 `9684f1f4e9c9acdf3b5f14ed687d1c2f28ff0c77` — `Hide pending webcam images and report recording intake blockers` 已推送；[最终英中报告](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6528779201)。交付状态为实现待审、真实数据目标未达成，后续按 §3.5 继续不受影响的 TASK-140。

### 2026-10-31 第 9 轮（Codex，契约 r5 第 1 至 9 条）

- 实现提交 `c1b8416eda76aa1dbf61d37bcfb32e133352c4f4` — `Constrain synchronization cuts and isolate optional webcam failures`，已在原分支推送；[代码检查点](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6540063021)。主线程 Inline Execution，没有子代理、额外 checkout 或新分支。Q-032 未答，第 10 条、1023 代理与正式 worker 文件没有实施。以下是 Codex 检查记录，不代替 Claude 独立审查或用户独立 checkout 验收。

#### 实现与离线检查

- `refine_breakpoints` 只在相邻长窗中心的闭区间内选细化切点，没有候选时保留粗切点；端点与 1016 E 实际数字夹具覆盖。对 48 个受保护 AST 的核对只有这个获准函数改变，另外 47 个不变；采样 SHA 仍为 `7c6c32f413379ddb023dcfc07295376aec727bf12bffb13af2f6e3461ac6d77d`，OSD 版式与 glyph 字节不变。没有修改门槛、采样或其他拟合算法，没有重跑旧七次。
- 三个 CLI 的可选 `--inventory` 只在记录路径失效时解析来源，匹配映射/清单 SHA 记录与大小并检查磁盘大小；保留有效 remux 路径。为维持受保护读取器的严格 stat 校验，核验后只在临时内存副本使用迁移文件的 mtime；不改写旧记录，不重算完整源视频 SHA。临时搬迁测试经过校准、代理和时钟读取入口。
- W 的 PyAV/KeyError 与事件读帧/缩略图错误均在可选分支隔离；事件失败重新导出 A/B/E 条图，W 原因写入报告。W 证据缺失、迁移或过期时不读 W 参考，在 manifest 记录 `webcam_unavailable`，三机抽样继续。W–B 的 reason 列出具体失败条件。面板移到时间轴与类别之后，加载和失败时保留 360px 占位并隐藏旧图。
- `plan` 拒绝 review-only 文件；生产调用传入重叠范围，正式旧代理从索引绑定的映射取得真实边界，新代理使用 session 的 overlap。文件头与交接行只接受许可字段。W 文件名规则统一放到 camera_roles；清单重跑保留行序并拒绝缺少已有源的错误 root；重封装失败保留原有效行。**不带 `--session` 的重封装也从重写改为合并报告**。
- 默认离线门：`python -m compileall main.py gazelle tests tools`；`python -m unittest discover -s tests -v`（**774 tests / 68.758s / 0 skip**）；`python main.py --help`；`python main.py --list-models`；`node tests/annotation_page_test.cjs`；`node tests/roi_page_test.cjs`；`python -m tools.docs build`；`python -m tools.docs check`；`git diff --check` 全部 exit 0。解释器为现有 `Gazelle-next`，字节码留在 TEMP。`task150-final-gate.json` 保存命令与退出码；合成坏 MP4 的 moov 消息和 Git 行尾消息非致命。
- 必需变异 **34/34 检出**。初轮 33/34，补上直接验证 W 代理旁注 role 的测试后，`p_sidecar_role` 在 105 项聚焦测试中触发断言失败。其余已检出的变异沿用仍适用的结果；最后全套正常门 774 项通过。初始矩阵保留，合并证据为 `task150-mutations-final.json`。部分变异因代码位置改变作等价替换，矩阵标 `adapted`；两项通过错误而非断言检出，记录未改称断言。变异进程为默认 Normal；完整离线门与真实长 CPU 作业为 BelowNormal，未宣称全部进程都低优先级。
- 内置浏览器以临时合成数据在 1500×950 实测：有 W、无 W、加载与失败状态的时间轴文档坐标均为 860.979187；图片占位 360px，加载/失败隐藏旧图；W 返回 404 后仍能标注并保存到临时文件。点击类别触发浏览器自动滚动时，viewport 坐标改变但文档坐标不变。`task150-browser-observed.json` 记录证据；服务停止、标签页关闭。Node 另覆盖 W 不计入已看步。Headless Edge 尝试因 GPU 子进程 exit -1073741790 而失败，日志保留；不将内置浏览器检查称为 Edge 独立验收，也未修改浏览器/安全设置去绕过。
- 四份公共用户文档与文档测试同步。实施中数个新夹具的预期/形状问题、外部日志读取一次误用默认 cp932、状态查询的一次括号错误、Edge 启动失败均保留原记录；未为取得通过放宽生产门槛。外部交接检查最初把返回的 gap 数命名为 excluded_sampling_steps，读回接口后改为分别记录 1 个 gap 与 251 个 sync_uncertain 步；生产抽样规则没有改变。

#### 真实重新拟合与数据验证

- 全部代码提交、工作区干净后才开始。先核对旧失败映射 SHA，再在同目录改名为 `20261016.json.before-task150-r5`、`20261023.json.before-task150-r5`，旧 SHA 分别为 `d9a60b922b5f2f0a8dc63d9367f90fd2a04dc6303ba951f7d2a45f56a560ce5b`、`32251e2195c6dbd2a8c9dd629b1eee6a6b5c634aa0887a505a530c7c22954b2f`。
- 两次命令：`python -m tools.workdata.sync_calibrate --timemaps ../gazelle_data/workdata/timemaps_v2_base --out-root ../gazelle_data/workdata/timemaps_v3 --samples-root ../gazelle_data/workdata/sync_samples_v2 --keyframes-root ../gazelle_data/workdata/keyframes_v3 --inventory ../gazelle_data/workdata/inventory/inventory.json --session <20261016|20261023> --reuse-samples`。分别 **exit 0 / 33.652s**、**exit 1 / 33.925s**，复用八组现有样本，不重新解码。样本像素、旁注 SHA 与 sampling SHA 全部核对，A/W 的窗口、参数、切点、有效状态与尾部值逐项不变。
- 1016：A 51/60 有效窗、MAD 0.055943、尾部 2/51；E 50/60、MAD 0.041917、尾部 **5/50=10.0%**，切点 **1135.213989**、不确定区间 **[1110.270794,1160.157184]**；W 52/60、MAD 0.042401、尾部 4/52。W 电脑时钟减 B 在 13:25/13:50 为 **−2.384729 / −2.443956s**，符号和容差核对通过。新映射 SHA `9de009d075a35ef27e677fd04f1efac23d127e5eb4e3b0c43b0d1a6ece2e7335`，calibrated=true。
- 1023：A 53/60、MAD 0.054952、尾部 **7/53=13.2075%**，仍为 `residual_tail_exceeds_0_2`；E 55/60、MAD 0.046268、尾部 **2/55=3.6364%**，切点 **1175.352834 / 1595.144727**；W 56/60、MAD 0.072269、尾部 3/56。W 两处偏移 **−0.575497 / −0.745526s** 仅报告。新映射 SHA `255a798ae93127ebb6f6904c186c191a6cc1b27879e309b42c06555a329cee47`，calibrated=false。实测均符合 r5 预演，不启用未授权 second-look。

- `python -m tools.workdata.proxies --timemaps ../gazelle_data/workdata/timemaps_v3 --out-root ../gazelle_data/workdata/proxies --session 20261016 --allow-internal-gaps --inventory ../gazelle_data/workdata/inventory/inventory.json`：**exit 0 / 5139.823s**。四路各 **18,019 帧**，5 Hz、3603.8 秒、H.264/yuv420p、无音轨；A/B/E 为 1920×1080，W 为 1280×720。源解码帧数 A/B/E/W 为 **117253/90664/54058/161708**，全部到 EOF，帧数差异不需复核。缺口数 **0/0/1/0**，同步不确定步 **0/0/251/0**；E 的两段记录范围重叠，其并集仍为 251 步。没有删除缺口或不确定步。
- 新 `session.json` 记 `allow_internal_gaps=true`、overlap、`code_commit_sha=c1b8416…`、`code_worktree_dirty=false`。原采样网格为 18,018 步，最终校准后的代理网格为 **t0=1791982796.0、N=18019、step=0.2**，不是重采样旧缓存。固定时钟抽查沿用原规则，seed **40522031**，索引 **[6172,15089,17317]**，A/B/E 共 9 项；保存的原脚本 SHA 与代理 session SHA 一并记录。
- 验证命令：`python -m tools.workdata.sync_validate --proxies ../gazelle_data/workdata/proxies --out-root ../gazelle_data/workdata/sync_validation_r5 --session 20261016 --clock-samples ../gazelle_runs/codex-round9/clock-samples-20261016.json --timemaps ../gazelle_data/workdata/timemaps_v3 --keyframes-root ../gazelle_data/workdata/keyframes_v3 --inventory ../gazelle_data/workdata/inventory/inventory.json`。

- 同步验证 **exit 0 / 516.801s**，四个同步对全部按原门槛通过，未启用第 10 条。A–B：50 有效窗、±0.2 秒占比 **96.0%**、中位绝对值 **0.042817s**、中点偏差 **0.007267s**、漂移 **0.008499s/h**；E–B：49 窗、**93.8776% / 0.048267s / −0.002444s / −0.028316s/h**；A–E：40 窗、**100% / 0.038592s / −0.000931s / 0.077786s/h**；W–B：50 窗、**92.0% / 0.034470s / −0.004904s / 0.014055s/h**。A–E 覆盖比例 0.782551，结果保留全部有效性类别。没有剔除失败窗或更改门槛。真实代理结果与 r5 的离线预演不同，不能把预演当成这次验证结果。
- 时钟 **9/9 可评估且通过**，均直接从代理读出，无需补读替代索引；源 PTS/代理缩略图比较仍实际执行。保存的 `delta_seconds` 是 source base_X(pts) 减整数 OSD 读数，不能与 `reading_minus_grid_seconds` 混用。
- 事件条图共 **4 张**（3 运动 + 1 切点附近），k=2545/15100/16459/5715；缩略图像素与文件 SHA 通过检查。已逐张目视 B/A/E/W 四行，转身、伸手、抬手、俯身动作大致对应，未见缺行或黑行；不据此声称亚帧精度。切点附近图按既有“±10 秒最大运动”规则选择，中心比切点晚 **7.685295s**，不是精确切点画面。图像只在本地查看，未上传 GitHub。验证文件 SHA `f02956527a597f853d1ca6ca7adebb8fdc57c292b92df06f136ddfef37093710`。
- `append_proxy_manifest.py --session 20261016` 在四对、时钟、EOF、帧数、媒体/映射/session/验证 SHA 与 W 符号全部通过后追加唯一新行；先以独占新文件保存原索引，再原子替换索引并读回。旧 **7 条逐字段相同**，新索引共 **8 条**，新记录明确写 `Codex checks passed; Claude independent acceptance pending`。备份 `proxies/manifest.before-task150-r5.json` 的 SHA 为 `b516f63d86d2fe6bb55003f4288d5d2e1ce6821638ba1a1a322b6f6d3871e210`，新索引 SHA `3d2ac38ea1017dbde9d899e2e1c6a6fa7dd01e906204d7e0cd34c9e58d22a6f6`。没有写入待 Q-032 的 sync_grade/second_look 字段。

- 追加索引之前，`task150-audit-after.py` 对预先登记的 **16,891 文件 / 90,097,391,320 bytes** 重算 SHA，**433.399s、exit 0**，全部相同；两份新录制旧失败映射核对改名后备份。当时共享 inventory 56 行、remux 13 行、代理索引 7 行均逐字段及整文件相同。两份正式数据集限定元数据与帧不变；`roi_r2/labels.json` 与 `.bak` 从清单构造起排除，未枚举或读写。原始源只作读取，旧录制无重处理。
- 追加之后，`task150-handoff-check.py` 核对其余 **16,890** 个登记文件的大小/mtime 没有再变化，原索引备份 SHA 与前测相同，原 **7 条** 索引内容不变，仅新增 1016。`read_session` 实际读取新代理，W 参考通过绑定校验；返回 1 个 gap，另有 251 个同步不确定步。没有提取正式数据集，也没有写正式 worker 表；1023 代理目录不存在。两份失败映射与原索引的旧内容均可从备份核对。
- 实际活动：现有 `Gazelle-next`、Python 3.14.8；真实 CPU 数值拟合、PyAV 原生解码、FFmpeg 编码/ffprobe 文件检查、OpenCV 时钟/代理检查、四张本地图片查看、临时浏览器与 GitHub。复用现有采样与来源 packet/keyframe 缓存，新代理生成自己的 keyframe 验证缓存；没有 Gazelle/MediaPipe 模型推理、CUDA、模型下载、训练或环境修改（TASK-101 的真实模型活动另记于该任务）。普通文件权限预检与获准 yun Git/GitHub 例外分开记录。全部真实处理链、前测/后测和临时服务已结束；失败浏览器的诊断配置留在仓库外。详细日志、完整命令和 JSON 均在 `gazelle_runs/codex-round9/`，媒体与派生数据没有上传。

#### 自主决定（A 级）

- 采用共享 source_paths 解析与 transient mtime 副本，保持三个受保护读取函数的 AST；证据哈希与源 SHA 记录不改。作业者文件头用固定匿名字符串、5 秒精度、10 秒末端例外与 SHA allowlist；具体字段在四份文档说明，不增加身份信息。正式文件仍等待两个最终映射。
- 真实新验证放在现有 `sync_validation_r5` 的新 1016 路径；旧七次不改。时钟抽样沿用保存的原脚本规则 `Random(20261015 + int(session)).sample(range(N),3)`，只生成新录制的固定三个索引。新代理保留 `allow_internal_gaps=true` 与 overlap；不让 W 参与 A/B/E 同步判定。
- r5 改过的交接条件直接依据第 8 轮已有逐帧证据复核：0903、1016 最早人脸均在区间最后 8.3 / 2.4 秒内，满足“除最后 10 秒”的新条件。没有重跑检测、识别人脸身份或挪动用户确认边界；明确该 10 秒是看到 8.3 秒后由协调者决定。

#### 范围外改动

- 无。未做 TASK-152/151/153、第 10 条、20261030 接入或正式数据集生成；未修改 Multi-Pose、Actions、Conda、全局配置、研究阈值、区域、参考图或正式标签。所有媒体与派生结果留在仓库外。

#### 待 Claude 判断（B 级）

- **1023 仍未通过原拟合门**：A 尾部 7/53，代理、验证、索引和正式 worker 表继续等待 Q-032。不是执行崩溃，也没有以 W/E 通过替代 A 的要求。1016 已完成原门槛下的代理与验证；请独立复算真实 E–B 93.8776%、A–E 漂移 0.077786s/h 与预演 E–B 90.0%、A–E 0.122s/h 的差别，当前不把差别归因于未经验证的原因。

- 文档差异：VALSET 4.5.0 的 front matter/版本记录称已补 §11.3 精度，但当前 §11.3 正文仍按最后/最早人脸定义交接，未写 5 秒精度或最后 10 秒例外。本轮按更新的 TASK-150 r5 明文实现，不擅自修改受控研究文档；请 Claude 同步正文。
- 浏览器独立验收仍待 Claude；内置浏览器与 Node 证据不替代独立 Edge 复测。

#### 待用户决定（C 级）

- Q-032 仍待回答，1023 代理、正式 worker 表和第 10 条继续等待。没有重复请求已有授权，没有将等待解释为同意。Q-033 的后续轮次调整仍由 STATE 协调，本轮不做后续任务。

### 第 9 轮继续实施记录（Codex，2026-10-31 至 2026-11-01；契约 r7/r6）

- 实现 `2530c08df2c5bd0289cbb242e6abb1903ffe18fc`（Add opt-in synchronization rechecks and close source provenance）已推送；以下为 Codex 检查，独立审查与用户独立 checkout 验收仍待进行。主线程 Inline Execution，无子代理、新分支或额外 checkout。
- 路径解析同时核对磁盘/清单/映射的修改时间，保留原 fingerprint；失效重封装路径不回退到 AVI。`checked_source` 对解析后路径照常核对大小/mtime。W 的纯异常边界使用 `Exception` 并记录类型；A/B/E 仍按既有行为失败。一次录制只有 W 且前置失败也会写出并返回结果。
- 按 VALSET 5.0.0 §11.7 实现默认关闭的 `--second-look`：拟合复核仅在指定尾部失败之后，120 秒窗口按 base 时间归入原分段，不删跨切点窗；代理三类复核保留原判定，W 不复核；同步失败等级为 null，新录制抽样拒绝缺失/失败等级。拟合复核另记 `sync_validate.py` SHA，不改实现哈希的文件集合。正式作业者 ID 限定为 `<录制>_worker_<n>`，approved 文件要求完整头。

#### 命令与离线证据

- Gazelle-next Python 3.14.8，字节码均在仓库外。最终 `python -m compileall main.py gazelle tests tools`；`python -m unittest discover -s tests -v`：**806 tests / 34.494s / 0 skip / 0 failure**；`python main.py --help`、`python main.py --list-models`、`node tests/annotation_page_test.cjs`、`node tests/roi_page_test.cjs`、`python -m tools.docs build`、`python -m tools.docs check`、`git diff --check` 均 exit 0。日志/命令数组在仓库外 `gazelle_runs/codex-round9-continued/task150-final2-*`。
- RED：second-look 新接口未实现，10 tests 中 40 个错误子情况；r7 的 6 tests 为 3 failures / 6 errors。首轮集成夹具补充 mtime、符合新规则的 span_id；补测时修正了测试替身的参数重名、关键帧表缺键与空分段。首轮全量 806 项中一个旧夹具的两个子情况缺少新等级，补齐夹具后完整重跑通过。未放宽生产规则。OpenCV 的既有坏媒体夹具 `moov atom not found` 为非致命提示。Git 的 LF/CRLF 提示非差异检查失败。
- Claude 列出的 40 个 test-gap 变异全部捕获；r7 指定的两个 mtime 变异换为反向变异。每个子进程只在内存中修改模块后跑测试，控制组 74 项通过；未创建代码副本或改动正式源。页面占位变异通过本地 HTML 副本与原 Node harness 检测。证据 `task150-mutations.py/json` 与逐项日志。外部驱动首次读取/输出编码不匹配，改为明确 UTF-8 后执行；与生产逻辑无关。
- 50 个受保护 AST 与 `c1b8416` 全部一致（48 个原组件加 `residual_summary`、`session_passed`）；采样 SHA 保持 `7c6c32f413379ddb023dcfc07295376aec727bf12bffb13af2f6e3461ac6d77d`；OSD 两份 JSON 字节不变。`implementation_hash` 函数不改。证据 `task150-ast-check.json`。默认测试均为合成/mocked，无真实模型、CUDA、网络、下载、FFmpeg 或环境改动。
- 四份用户文档、workdata 中文指南与标注中文指南同步；文档门增加规则、等级与路径闭合条款。页面本身未改，仅补占位比例回归；未重复真实浏览器验收。

#### 已执行真实步骤

- 全部代码提交且工作树干净后，先保留 `proxies/manifest.before-second-look.json`，仅在 1016 索引行补 `sync_grade=official`，`acceptance_status=Claude round-9 review accepted; user acceptance pending`。旧七行逐字段不变；验证文件 SHA `f0295652…`、映射与代理均不改，不重跑 1016。
- 1023 原失败映射 SHA `255a798a…` 改名保留为 `20261023.json.before-second-look`，原 `before-task150-r5` 备份保留。运行 `python -m tools.workdata.sync_calibrate --timemaps <data>/timemaps_v2_base --out-root <data>/timemaps_v3 --samples-root <data>/sync_samples_v2 --session 20261023 --reuse-samples --second-look --keyframes-root <data>/keyframes_v3 --inventory <data>/inventory/inventory.json`，**exit 0 / 21.894s**，新映射 SHA `eb999190…`。
- A 的原尾部仍为 7/53，复核 54/59 有效窗，占比 **0.9629629629629629**、中位绝对残差 **0.036028483432652s**、中点偏差 **0.001962617731381339s**、漂移 **0.03367916791642427s/h**，通过。数值与预演一致。剔除契约明确允许变化的字段后，新旧映射深比较 **0 差异**；A 原窗口/系数与 E/W 窗口、系数、切点、有效性、尾部均保留，缓存像素与旁注 SHA 不变。证据 `task150-refit-result.json`。
- `<data>` 为仓库外 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata`，`<run>` 为 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\codex-round9-continued`。运行 `python -m tools.workdata.proxies --timemaps <data>/timemaps_v3 --out-root <data>/proxies --session 20261023 --allow-internal-gaps --inventory <data>/inventory/inventory.json`：**exit 0 / 4308.715s**；`python -m tools.workdata.sync_validate --proxies <data>/proxies --out-root <data>/sync_validation_r5 --session 20261023 --clock-samples <run>/clock-samples-20261023.json --timemaps <data>/timemaps_v3 --keyframes-root <data>/keyframes_v3 --inventory <data>/inventory/inventory.json --second-look`：**exit 0 / 516.416s**。完整命令数组、日志与 BelowNormal 优先级记录在 `task150-pipeline.json`；两步共 4825.172s。
- 四路均 **18,100 帧 / 5 Hz / 3620s / H.264 yuv420p / 无音轨**，A/B/E 为 1920×1080，W 为 1280×720。来源全部读到 EOF，容器帧数与解码帧数完全一致，无 review-required；A/B/E/W 源解码总数为 **137755/93002/54296/161707**。实际缺口步数 **29/28/1/0**，联合读取为 30 步；E 两个切点的不确定范围各 **151/253 步**，联合 **404 步**，其余摄像机为 0。视频、旁注、映射、session、验证与条图 SHA 全部读回闭合。
- 原 60 秒窗 A–B、E–B、W–B 通过；有效窗分别 **51/60、56/60、56/60**，±0.2 秒内占比 **92.1569%、96.4286%、94.6429%**，中位绝对残差 **0.048493/0.042012/0.071641s**。A–E 原判定仍为 failed：53/60 有效窗、占比 88.6792%、中位 0.112496s、中点偏差 −0.095476s、漂移 −0.098812s/h；未覆盖原失败字段。
- A–E 的 120 秒复核为 **52/59** 有效窗、覆盖 96.1379%、占比 92.3077%、中位 **0.125374s**、偏差 **−0.114061s**、漂移 **−0.067624s/h**，按已批准的 0.15 门槛通过。录制最终 `passed=true`、`sync_grade=second_look`，拟合 A 与代理 A–E 均用到复核；W 保持原门槛且可用。验证 SHA **`ecbe704436931f885bbf3ac84ae8b0cb3cf40d370e1726fa64d60c84e66cdd40`**。
- 固定种子 `20261015 + 20261023` 抽取索引 **10887/15708/16501**，A/B/E 共 **9/9** 时钟检查通过，全部直接读代理，无替换索引或补读来源；保留并核对原抽样脚本 SHA。三个运动事件 k=4564/5660/16825 与两个 E 切点事件 k=5911/7959 的 5 张条图逐张查看，四路动作顺序无明显错配；其中 k=5660 动作较小，目视不提供细粒度时差测量。条图原尺寸 3520×756，查看尺寸 2048×440；这不代替独立同步验收。证据 `task150-data-check.json`、`task150-visual-check.json`。
- A/B 中断来自文件边界：A 的 14:22:59.329311→14:23:05.314992 为 **5.985681s**，B 的 14:22:59.305980→14:23:05.258091 为 **5.952111s**，联合覆盖间隙 6.009012s。保留 gap，不插值。W 电脑时钟减 B 时钟在 14:05/14:35 为 **−0.575497/−0.745525s**，按契约仅报告。
- `task150-data-check.py append` 在上述条件通过后保留 `proxies/manifest.before-20261023.json`（SHA `18676e18…`），追加唯一 1023 行；先前八行逐字段不变，最终索引 **9 行**、SHA **`1bca0bc519c8f6ff860e087ce93d9764d0ae320697c700b1af3660af0a7eccef`**。新增行明确写明 Codex 检查通过、Claude 与用户验收待进行。真实 `read_session` 读回 second_look、W 参考可用、30 gaps、404 uncertain steps；没有生成新数据集。

#### 正式作业者表与数据保护

- `task150-workers.py publish` 写入 `<data>/workers/worker_spans.json`：**9 次录制、11 段、2 个交接区间**，P1–P4，全部文件头齐全、5 秒精度、10 秒末端例外；源初稿 SHA `34ba423c…`，正式文件 SHA **`20075521557f2bc44e50190374fcda051d7e205d79d94cc4efb3bdbb1b30a3bb`**。格式、非重叠、重叠范围与交接排除校验通过；旧七次与原候选逐字段一致。
- 按最终映射裁剪外端点，未改原始人工时钟或内部交接边界。相对旧候选：1016 worker_1 start 为 **1791982795.8367264**（−0.393234s），worker_2 end 为 **1791986399.73127**（−0.166656s）；1023 start/end 为 **1792418380.1240337/1792422000.0974**（+0.001312/+0.004084s）。转换逐项记录在 `task150-workers.json`。
- 交接核实复用 `gazelle_runs/task-150/handover-20260903.json` 与 `handover-20261016.json`，本轮没有重跑人脸检测；已核对原记录 SHA、检测宽度 200/score 0.5、交接边界及 A/B 时间几何未变。0903 A/B 各测试 6700 帧、命中 81/65；1016 各 4250 帧、命中 20/43。所有命中均在交接末端 10 秒内，最早距结束 **8.2743/3.9179s** 与 **1.9924/2.3983s**，满足修订后的例外。
- `task150-audit-after.py` 对 **16,916 文件 / 96,329,027,951 bytes** 重算 SHA，**310.863s、exit 0**，受保护内容全不变；1023 原映射与原索引在获准备份位置核对。inventory 56 行、remux 13 行及旧七次索引不变。最后 `task150-final-check.py` exit 0：这 16,916 文件大小/mtime 没有后续变化，无须再次哈希；56 个原始文件的大小/mtime 与清单相同；1016 映射、验证 SHA 不变；正式表与九行索引再次读回。未读写正式标签及 .bak，两个既有数据集的限定元数据/帧保持不变。
- TASK-150 真实活动为 CPU/PyAV/OpenCV/FFmpeg/ffprobe、现有采样与来源 keyframe 缓存复用、新代理和验证缓存写入；没有模型/CUDA 推理、下载、环境修改或主动网络请求。没有做网络抓包，不把未请求网络当成全部原生组件无网络的实测证明。所有处理进程已正常退出；媒体、缓存、派生 JSON、工人表都在仓库外。旧七次与 1016 未重跑，真实浏览器未重测，20261030 与后续任务未执行。

#### 自主决定（A 级）

- 在入口限制 `--second-look` 只用于 20261016 起的录制，符合适用范围；抽样读取器拒绝 null/非法等级，避免失败同步进入数据集。沿用旧七次缺字段为 official。
- W 事件错误保留底层异常类型；抽样的原 `webcam_unavailable` 原因字符串不变，新增并行 `webcam_error_type`。正式 approved 头完整性与匿名 span_id 校验均有覆盖。
- 本轮仅必要 Git/GitHub 命令使用既有 yun 授权；普通会话 gh 认证与 Git 索引写入未通过，不把提权成功说成普通权限通过。其余编辑、测试、数据写入在普通会话执行。

#### 范围外改动

- 无。没有处理 20261030、TASK-152/151/153、阶段 3 或新数据集，没有读写 `roi_r2/labels.json` 及其备份；正式区域/类别/原始媒体只读，派生物、缓存与凭据未上传。

#### 待 Claude 判断（B 级）

- 实测 A–E 复核中位/偏差/漂移为 **0.125374/−0.114061/−0.067624**，与契约中的缩略图预演 **0.112/−0.103/−0.089** 不同，但全部满足已批准规则；没有调整方法迎合预演。请 Claude 独立复算真实代理及窗口，确认差异，当前不臆测原因。独立复算、实现/变异审查与真实结果验收待进行。`sync_check.py` 仍是打开旧记录路径、要求全部行有效的可选旧诊断，本轮不改。`timemap.run` 第二层对 A/B/E 的 KeyError、FFmpegError 行级失败处理按 r7 保留。

#### 待用户决定（C 级）

- 无新增决定；独立 checkout 验收待进行。

## 3. 审查结论（Claude 追加）

### 2026-10-31 第 8 轮审查（Claude）

- **审查目标**：`397c5d1`（实现）、`9684f1f`（图片隐藏修正与报告）、`319c542`（补充报告），在 HEAD `299bf0f` 上审查。完整记录见[第 8 轮审查记录](../evidence/2026-10-31-round8-review.md) §5。
- **结论**：**changes-requested**。主体实现正确，旧录制的路径不受影响；W 的隔离有漏洞，页面有一处影响标注的问题，测试偏弱；真实数据目标未达成。
- **发现**（独立审查用合成数据运行确认，发现 1、2 Claude 另读代码确认）：
  1. **中：W 的条图失败会挡住 A、B、E。** `export_events` 不在 W 的异常保护内。W 读帧或缩略图核对失败时 `sync_validate.run` 抛 ValueError，A、B、E 的验证文件不写。
  2. **中：有 W 的片段每换一步页面都跳。** `annotation_page.html:85` 的 `image.hidden=true` 让面板每步折叠约 360 像素，时间轴与主图随之移动；展开时时间轴也在常见窗口之外。`roi_r2` 没有 W，不受影响；新分层的 12 段会受影响。
  3. **中低：W 的异常保护太窄。** 只捕 OSError、ValueError、RuntimeError。PyAV 的 `ExternalError`、`UnknownError` 等与 `KeyError` 会让 `sync_calibrate.run` 中止，A、E 的结果不写。
  4. **中低：W 证据过期时挡住抽样。** `read_webcam_reference` 直接报错，而 W 不是必需输入；索引缺记录时又静默不带 W。
  5. **低：作业者片段的校验。** `coverages` 没有生产调用，超出重叠段的片段被接受；`plan` 接受 `status: review-only` 的候选文件；文件头与交接行不查。
  6. **测试偏弱**：57 个变异存活 39 个，其中两个是 W 校准的参数顺序（符号）。TASK-152 没有参考偏移，别无保护。这些存活项对应的现行行为大多已由实验确认正确，缺的是回归保护。
  7. **低**：`--session` 配错 `--root` 时不校验保留行；重跑旧录制时行序改变；重封装重跑失败会替换有效行；W–B 失败的 `reason` 只有 `failed`。
- **未报告的决定**：W 的文件名规则写在代码里而不在 `camera_roles.json`；不带 `--session` 的重封装从重写变为合并；服务端夹具改成全部带 W。前两项按修订 r5 第 8 条处理，第三项按第 7 条。
- **A 级决定**：同意 W 接口单列、复用 A/E 算法；同意参考图必须绑定通过的验证，但失败时的行为按修订 r5 第 4 条改；同意逐原生帧核实交接并保留失败证据。
- **B 级问题**：Q-029、Q-030、Q-031 已处理，见审查记录 §5.4 至 §5.6；需要用户决定的部分是 Q-032。

### 2026-10-31 第 9 轮审查（Claude）

- **审查目标**：`c1b8416`（实现）、`27d5301`（报告）、`5690745`（交接），r5 第 1 至 9 条。完整记录见[第 9 轮审查记录](../evidence/2026-10-31-round9-review.md) §3。第 10 条与 r6 没有实施，不在范围内。
- **结论**：**changes-requested**。行为成立，没有 must-fix，修正写入契约修订 r7。`20261016` 的代理与验证通过审查。
- **Claude 实际运行的检查**：
  - 16,891 个受保护文件重算，只有 3 个获准的文件变化，旧 7 行索引逐字段相同；
  - 新代码重放 9 次录制的 18 组拟合，0 处不同，旧 4 个切点不变；
  - 从保存的代理缩略图复算 `20261016` 的四对，240 个窗口全部一致；
  - 实测与预演逐窗比较，差别的典型大小约 0.02 秒（P90 约 0.045，E–B 最大 0.192），没有系统偏移；
  - 重读 9 个时钟读数，全部与验证文件相同；
  - 真实 Edge 实测 W 面板 19/19，旧页面回归 23/23、28/28、37/37、3/3、3/3。
- **注意**：`20261016` 的通过是合规的，但余量在噪声范围内：E–B 占比的自助法区间 [85.7%, 100%]、W–B 占比的区间 [84.0%, 98.0%]、A–E 漂移的区间 [−0.007, 0.197] 秒/小时都包含门槛。W–B 只影响 W 是否可用。
- **发现**（只读子代理报告，发现 1 Claude 读代码确认）：
  1. **应修：路径解析少一环。** 只比大小，并用磁盘 mtime 覆盖内存副本，同大小的错文件能通过。这是 r5 第 3 条的缺口，不是实现错误。
  2. **应修：FFmpegError 的测试是假的。** 用例用的 `InvalidDataError` 继承 ValueError。代码本身正确。
  3. **应修：契约点名或新增的行为没有测试**。66 个变异存活，其中 40 个是测试缺口。
  4. **应修：搬迁测试只覆盖一部分入口。**
  5. **应修：`tools/workdata/README_CN.md` 没有更新。**
  6. **小项**：W 分支只列了具体异常类；AVI 可能顶替丢失的重封装文件；错 `--root` 只比大小；作业者文件的校验偏松；`timemap.run` 两处；`sync_check.py` 没有上报。
- **A 级决定**：内存中的 mtime 副本不同意，其余同意，见审查记录 §3.5。
- **没有检查**：没有重新生成代理，4 张事件条图没有看，W 面板只测了合成夹具。
