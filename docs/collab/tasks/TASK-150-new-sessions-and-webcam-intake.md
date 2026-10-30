# TASK-150：新录制（20261016、20261023）与 webcam 的接入

状态：ready（第 8 轮；TASK-125 第 3 轮已于 2026-10-30 通过审查）。Claude 已在第 5 轮审查时复核，修订见 §1 末尾的“契约修订 r2”；第 6 轮审查后轮次顺延一轮；2026-10-30 源目录迁移与新文件夹见“契约修订 r3”，分层数据集移到 TASK-152 见“契约修订 r4”
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

## 3. 审查结论（Claude 追加）
