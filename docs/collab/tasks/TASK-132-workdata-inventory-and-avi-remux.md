# TASK-132：作业数据清单与 AVI 无损重封装

状态：accepted（2026-10-16）；尾部检查加强等改进由 TASK-135 实施
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude（工具与数据报告）
依据：[作业数据分析](../analysis/2026-10-15-workdata-analysis.md) §1 至 §3.1；GZ-22。
授权：2026-10-14 本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

为作业数据生成可复现的只读清单，并把全部 11 个 AVI 无损转成 OpenCV 能完整解码的 MP4，存放在仓库外的数据缓存中。

### 必须实现

代码放在新包 `tools/workdata/`（含 `tools/__init__.py` 与 `tools/workdata/__init__.py`），只用标准库与 `Gazelle` 环境已有的包；FFmpeg 与 ffprobe 通过子进程调用，路径默认取 PATH，可用 `--ffmpeg`、`--ffprobe` 覆盖。

1. **摄像机身份配置** `tools/workdata/camera_roles.json`（提交到仓库）：
   - 物理编号 `cam_a`、`cam_b`、`cam_e`，以及每台的识别特征：文件名规则、时钟样式（A 紧贴左边缘，B 向右缩进，E 带星期与 `CAM3`）、MP4 容器帧率（A 为 30，B 为 50）。
   - 按会话的覆盖规则：`20260903` 中 `カメラ1` 对应 `cam_b`，`カメラ2` 对应 `cam_a`。
   - 文件名中的日文模式只写在这个 JSON 配置里，Python 代码保持 ASCII（AGENTS.md）。
   - 角色映射（用户 2026-10-15 确认：カメラ2 是前方，カメラ1 是右侧，設備カメラ是两张工作台之间的全局摄像机）：`front` 为 `cam_b`，`right` 为 `cam_a`，`overview` 为 `cam_e`。映射以物理编号为准；`20260903` 的文件名互换由上一条覆盖规则纠正，所以该文件夹中名为カメラ1 的文件才是前方摄像机。
2. **清单** `python -m tools.workdata.inventory --root <源目录> --out <数据根>\inventory\inventory.json`：
   - 每个文件记录：会话文件夹、相对路径、大小、修改时间、SHA-256（按大小与修改时间缓存，未变化时不重算）、ffprobe 视频流信息（编码、宽高、`r_frame_rate`、`avg_frame_rate`、`nb_frames`、`duration`、视频流 `start_time`）、是否有音轨、前 60 秒小于 64 字节的包所占比例、分段序号（文件名中的 `-1`、`-2`、`-3`）、物理摄像机编号与判定来源（`filename` 或 `override`）、`needs_remux`。
   - 只读源目录，输出写到数据根；目标文件存在时原子替换。
3. **重封装** `python -m tools.workdata.remux --inventory <inventory.json> --out-root <数据根>\remux`：
   - 对每个 `needs_remux` 的 AVI 执行 `ffmpeg -fflags +genpts -i <in> -map 0:v:0 -c:v copy -bsf:v "noise=drop=lt(size\,64)" <tmp.mp4>`，校验通过后原子改名为 `<out-root>\<会话>\<文件名主干>.mp4`。
   - 校验：输出包数等于输入中不小于 64 字节的包数；时长与输入相差不超过 0.5%；包的 PTS 严格递增；OpenCV 在开头、中间、结尾各连续读出 30 帧。
   - 已有且校验通过的输出跳过；`--force` 才重做。失败时删除临时文件，保留已有的有效输出。
   - 写 `remux_report.json`：每个文件的输入与输出大小、包数、小包数、时长、校验结果、用时。
4. **测试**（默认隔离：不调用真实 FFmpeg，不读真实视频）：文件名规则与会话覆盖；小包比例计算；FFmpeg 命令参数逐项断言；用伪造的 ffprobe 结果覆盖校验通过与失败；原子发布（失败不留下目标文件，已有有效输出不被破坏）；SHA-256 缓存命中与失效；命令行参数解析。
5. **真实运行**（CPU 与磁盘 I/O）：对整个源目录生成清单；重封装全部 11 个 AVI；在实施报告中记录文件数、各会话摄像机编号、重封装结果、总输出大小与用时。数据根为 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`。

### 非目标

- 不改 `gazelle/` 下的运行时代码与 CLI。
- 不做时钟识别、时间映射与同步（TASK-133）。
- 不重新编码，不改变分辨率。

### 依据材料

- 作业数据分析 §1 至 §3.1；本任务的命令即分析中已验证的命令。
- `docs/collab/COLLABORATION_PLAN_CN.md` §5 的数据规则。

### 不可变约束

- 源目录只读。派生数据只写到数据根，不进 Git，不上传。
- AGENTS.md 的默认测试隔离与“下载与发布使用临时文件和原子替换”的原则。

### 允许动作

新建 `tools/__init__.py`、`tools/workdata/**`、`tests/test_workdata_*.py`；更新四份用户文档的「研究数据工具」小节与 `tests/test_usage_docs.py`；读取源目录；写数据根；按协作方案 §4 提交并推送，并在 draft PR 发英中双语评论。

### 禁止

写入 `E:\Gazelle_Workdata\` 或用户独立目录；提交任何视频、帧、清单或报告数据；修改 `gazelle/` 下的代码；新建分支或 PR、合并、force push；修改环境；下载。

### 验收标准

1. 新增测试通过；完整离线门通过（`compileall` 包含 `tools`），无新增 skip。
2. 清单含 40 个文件，会话与摄像机编号与作业数据分析 §1、§2 一致，`20260903` 的覆盖规则生效。
3. 11 个 AVI 全部重封装并通过校验；报告中每个文件的输出包数等于输入的非空包数。
4. 用仓库的 `VideoFrameReader` 读取任一重封装文件的前 600 帧，帧数为 600，时间戳严格递增（TASK-131 合入前后都应成立）。
5. `git status` 与提交中没有数据文件。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-132-pycache"
& $py -m unittest discover -s tests -p "test_workdata_*.py" -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（数据完整性）。
- 需真实运行：是，仅 CPU 与磁盘。
- 文档同步：需要。在四份用户文档中新建「研究数据工具」小节：写明用途、在仓库根目录运行的入口命令、读取什么、写到哪里、是否调用 FFmpeg、是否使用 GPU 或网络，并链接 `tools/workdata/README_CN.md`。`README.md` 与 `README_CN.md` 只放简介与指向 USAGE 的链接；`docs/USAGE.md` 与 `docs/USAGE_CN.md` 放工具表。中英文语义一致；`tests/test_usage_docs.py` 在两份 USAGE 中锁定本任务的入口模块名。原因：这些工具由用户或 Codex 直接运行，属于用户可见的用法，适用 AGENTS.md 的文档同步规则（2026-10-15 按 Codex 接手核对修正）。
- 风险与回退：重封装只复制视频流，源文件不变；问题只影响缓存，删除缓存即可重建。
- 依赖：无。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实运行结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

### 2026-10-16 实施与真实数据验证（Codex）

- **提交与范围**：`1936ef2b4cd842b7c87857d0e85643c38c154d4a` — `Add workdata inventory and validated lossless AVI remux` 已推送。新包 `tools/workdata`、摄像机配置、中文指南、10 项工具测试；四份用户文档及文档测试同步。没有修改 Gazelle 运行时、研究指标或源视频。报告与 STATE 随后提交。
- **契约与接口**：清单版本 1 的 `files` 记录源根下相对路径、size_bytes、mtime_ns、SHA-256、video 流信息、前 60 秒包统计、physical_camera、role、camera_source、part_index、needs_remux。只在根、路径、size/mtime 一致时复用 SHA；ffprobe 元数据重新读取。清单原子发布；源文件与输出路径设边界检查。重封装使用视频流 copy 与指定 noise filter，校验后原子改名；旧有效输出复核后跳过，失败保留旧文件。
- **测试与命令**：新增测试先因缺少 tools 包而失败，再逐步实现。最终 `python -m unittest tests.test_workdata_tools -v` **10 项通过**；`python -m compileall main.py gazelle tests tools`、`python -m unittest discover -s tests -v`（**553 项、4.161 s、无 skip**）、`python main.py --help`、`python main.py --list-models`、`git diff --check` 均退出 0。553 包括当前工作树提前准备、未纳入本提交的 5 项 TASK-123 测试；本提交相对 TASK-131 新增 11 项（10 工具 + 1 文档）。完整门覆盖了最终 TASK-132 内容。非致命 warning 为已有无效视频测试的 OpenCV 提示、Git LF/CRLF 转换。字节码及离线日志在 `%TEMP%/gazelle-task132-*`。
- **真实清单命令**：现有 Gazelle Python 执行 `-m tools.workdata.inventory --root <raw> --out <data>/inventory/inventory.json`；其中 raw 为 `E:\Gazelle_Workdata\秋田大学様解析用動画`，data 为 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata`。退出 0，**40 文件 / 7 会话 / 29 MP4 / 11 AVI**；全部 11 AVI 的 needs_remux 为真。20260903 覆盖规则生效：カメラ1→cam_b/front，カメラ2→cam_a/right。会话计数（cam_a/cam_b/cam_e）：20260821=1/1/1，20260828=1/1/1，20260903=3/3/1，20260911=3/3/1，20260925=3/3/1，20261002=3/2/1，20261009=3/3/1。
- **真实重封装命令**：同解释器执行 `-m tools.workdata.remux --inventory <data>/inventory/inventory.json --out-root <data>/remux`，两轮均未使用 force。首轮退出 1（9 成功，2 因尾部定位仅读 29 帧失败）；修正定位方法后第二轮退出 **0**（9 个旧输出重新校验后跳过，2 个重新生成）。最终 **11/11 校验通过**；总输出 **11,366,097,123 bytes**。逐文件用时合计首轮 116.733 s，第二轮 112.797 s（不含另做的定位诊断/清单扫描）。数据根保留 `remux_report.first_attempt.json`、最终 `remux_report.json` 和 `seek_diagnostic.json`，失败临时媒体已删除。
- **定位诊断**：20260821 カメラ2，OpenCV 总帧数 72058；seek 到 72028 读 29 帧，首/末时间 3608697.246 / 3610163.898 ms；seek 到 71998 连续读 60 帧，首/末时间 3607197.261 / 3610163.898 ms。末帧相同，证明是 VFR 直接定位最后 30 帧的偏移。现在尾部先读至多 60 帧，再要求最后连续 30 帧；没有放宽 30 帧、包数或时长要求。另一个受影响文件为 20260828 設備カメラ。
- **读取器复核**：PowerShell here-string 交给 Gazelle Python，选首个重封装文件 `20260821_表情解析用カメラ1.mp4`，使用生产 `VideoFrameReader` 前 600 帧逐帧断言 `int(round(timestamp_ms)) > previous`；**600 帧、0 违规、退出 0**。
- **外部活动**：真实 ffprobe 探测、SHA-256 读取、FFmpeg 无损 stream copy、OpenCV 头中尾与 600 帧解码；进程 BelowNormal。仅 CPU 与磁盘，没有 GPU、模型、下载、网络连接、环境改动；源目录只读。清单、报告、视频、诊断临时文件均在仓库外，未上传。命令日志在既有 runs/task-131 下的 `inventory-task132.log`、`remux-task132.log`、`remux-task132-retry.log`。
- **反证式复核**：伪造错误包数、时长、PTS、29 帧解码均被拒绝；强制刷新失败保留旧输出；首次失败不发布目标；哈希缓存命中不读文件，变更失效；未知摄像机/路径越界拒绝；实际复核验证旧输出跳过路径。
- **状态与限制**：Codex 已静态检查、已实际运行；工具与数据可交审。头中尾抽查和包统计不等于逐帧完整解码或科学准确率验证；Claude 独立验收待进行。

#### 自主决定（A）

- 以较宽尾部解码窗口处理实测 VFR seek 偏移，保留连续 30 帧验收目标，见诊断数字与回归。
- 增加源根/相对路径边界与读期间文件变化检测；失败不发布清单或媒体。
- 长 CPU 检查期间在同一主线程准备后续 TASK-123；其文件独立暂存，不混入本提交。

#### 范围外改动

无。只有本任务工具、测试、文档；派生物不进 Git。

#### 待 Claude 判断（B）

无阻塞问题；请审查尾部 seek 自主决定、清单字段与真实统计。

#### 待用户决定（C）

无。

| 输入文件 | 输入非空包 | 输出包 | 输出 bytes | 全部校验 |
| --- | ---: | ---: | ---: | --- |
| `20260821/20260821_表情解析用カメラ1.avi` | 72000 | 72000 | 1887871510 | 通过 |
| `20260821/20260821_表情解析用カメラ2.avi` | 72058 | 72058 | 1721092238 | 通过 |
| `20260821/20260821_設備カメラ.avi` | 54285 | 54285 | 840016498 | 通过 |
| `20260828/20260828_表情解析用カメラ1.avi` | 36051 | 36051 | 945084803 | 通过 |
| `20260828/20260828_表情解析用カメラ2.avi` | 36054 | 36054 | 903628796 | 通过 |
| `20260828/20260828_設備カメラ.avi` | 27271 | 27271 | 471855823 | 通过 |
| `20260903/20260903_設備カメラ.avi` | 54253 | 54253 | 922405380 | 通过 |
| `20260911/20260911_設備カメラ.avi` | 54198 | 54198 | 933656704 | 通过 |
| `20260925/20260925設備カメラ.avi` | 54312 | 54312 | 886600311 | 通过 |
| `20261002/20261002設備カメラ.avi` | 54285 | 54285 | 908370160 | 通过 |
| `20261009/20261009設備カメラ.avi` | 54294 | 54294 | 945514900 | 通过 |


## 3. 审查结论（Claude 追加）

### 2026-10-16 第 1 轮审查

- 审查目标（SHA 范围）：实现提交 `1936ef2`，记录提交 `e7244d0`；审查时 HEAD 为 `c5473bf`。
- 独立复跑结果，均由 Claude 实际运行，对数据根只读：
  - 完整离线门：562 项通过，无 skip。
  - 清单：40 个文件、7 次录制，各会话摄像机数量与作业数据分析一致。`cam_a` 为 right，`cam_b` 为 front，`cam_e` 为 overview；`20260903` 的 6 个人脸文件来源为 `override`，カメラ1 对应 `cam_b`。11 个 `needs_remux` 全部是 AVI；40 个 SHA-256 无缺失。
  - 重封装报告：11 个文件全部 `valid`；输出包数等于输入非空包数；时长与输入一致；头、中、尾各连续解码 30 帧；磁盘上的文件大小与报告一致。
  - 生产读取器读取 `remux\20260911\20260911_設備カメラ.mp4` 前 600 帧：帧率 14.969，帧数 54198，等于输入非空包数；违规 0，全部来自容器。
  - 独立代码审查确认：子进程不使用 shell，命令参数符合契约，日文路径正确；临时文件与原子替换、失败时保留旧输出均正确；SHA 缓存失效逻辑、源目录边界检查正确；Python 文件全部为 ASCII。
- A 级自主决定：路径边界与读取期间的变化检测、与 TASK-123 分开暂存，认可。尾部解码窗口只部分认可：现在只要定位后能连续解码 30 帧就通过，并未确认读到文件结尾，所以“要求最后连续 30 帧”的说法不准确。由于是流复制，且包数、时长、PTS 另有校验，现有 11 个输出仍然有效。
- 发现，均不阻塞，已移交 TASK-135：加强尾部检查并补失败用例；补 `needs_remux` 与仅修改时间变化的缓存测试；四份用户文档改设独立的研究数据工具小节。
- 结论：accepted。
