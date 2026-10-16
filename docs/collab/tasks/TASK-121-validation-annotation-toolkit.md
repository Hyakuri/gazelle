# TASK-121：多视角同步片段的注视区域标注工具（决策 D12 r2）

状态：ready（依赖 TASK-134 与 TASK-123）
创建：2026-10-15（Asia/Tokyo），同日改为 r2　协调者：Claude　实现者：Codex　验收：用户（标注体验）与 Claude（工具审查）
设计：[作业数据验证集规范 r2](../../superpowers/specs/2026-10-15-workdata-validation-set-design.md) §2 至 §6。
授权：用户 2026-10-15 批准 D12 r2。2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。
摄像机角色（用户 2026-10-15 确认）：前方为 `cam_b`（通常名为カメラ2），右侧为 `cam_a`（通常名为カメラ1），全局为 `cam_e`（設備カメラ）。一律按 TASK-132 的物理编号取文件，不按文件名。
修订：r1 的单帧视线点标注（sample1、sample2）已撤回，本契约整体替换 r1。

## 1. 契约

### 目标

交付一套本机工具，让用户在浏览器中同步查看三个视角的 60 秒片段，以 0.2 秒为时间步高效、可中断地标注注视区域，生成可校验的数据集与标注文件。

### 必须实现

代码放在新目录 `tools/validation/`（含 `__init__.py`），只使用标准库与 `Gazelle-next` 环境已有的包。

1. **片段抽样** `sample_segments.py`：
   - 输入：TASK-134 的 `session.json` 与旁注文件；参数 `--seed`（默认 20261015）、`--per-session`（默认 4，重叠不足 45 分钟的录制取 2）、`--segment-seconds`（默认 60）、`--dataset-root`。
   - 按规范 §3 分层抽样、避开缺口、加入试标片段（2026-09-07 22:20:00 至 22:21:00）。
   - 写 `manifest.json`：数据集版本、种子、方法、重抽记录；每段的会话、起始时钟时刻、在代理网格中的帧号范围、所用三段代理视频的 SHA-256、时间映射版本。
   - 目标目录已存在时拒绝覆盖，除非显式 `--overwrite`。
2. **抽帧** `extract_frames.py`：每段每个时间步生成一张拼接 JPEG，写入 `<dataset>/frames/<segment_id>/<step>.jpg`，在 manifest 中记录哈希。布局：左列上为前方（`cam_b`）、下为右侧（`cam_a`），各 640×360；右侧为全局（`cam_e`），1280×720；共 1920×720，质量 85；每个视角左上角标注其角色名。
3. **类别配置**：TASK-123 的正式区域文件带有有效的完成标记时（导出时写入，记录完成时间与区域文件的 SHA-256，且至少一个 `target`、恰好一个 `cell`；以 TASK-123 修复后的实现为准），用 TASK-123 的类别生成函数得到 `<dataset>/classes.json`，并把 `roi_reference.png` 复制到数据集根目录；否则复制 `tools/validation/default_classes.json`（提交，内容为规范 §4.1 的默认类别、按键与颜色）。工具只从 `<dataset>/classes.json` 读取类别。manifest 记录所用区域文件的 SHA-256。
4. **标注服务** `annotate_server.py`：
   - 标准库 HTTP 服务，只绑定 `127.0.0.1`；HTML 与 JavaScript 内联，不引用任何外部资源。
   - 界面与操作按规范 §5：同步显示三视角；`<dataset>/roi_reference.png` 存在时显示参考图，否则显示文字定义；播放与暂停（1× 与 0.5×）、单步 0.2 秒与 1 秒、数字键从当前步起设定类别直到下一个变化点、删除变化点、撤销、彩色时间轴、跳到下一个未标注步、标记他人入镜的起止。
   - 每次修改即原子写入标注文件并保留上一版备份；重启后从未完成处继续。
   - `--labels-path` 指定其他标注文件，供试用与审查，不污染正式标注；`--annotator` 记录标注者。
   - 业务逻辑与 HTTP 层分离，便于不开端口直接测试。
5. **标注读写与校验** `labels.py`：实现规范 §4.3 的 schema；`validate` 子命令检查标注与 manifest 一致、区间覆盖每一步且不重叠；提供把区间展开为逐步数组的函数。
6. **标注指南** `tools/validation/ANNOTATION_GUIDE_CN.md`：中文说明类别定义与判定规则（规范 §4）、操作步骤、快捷键、预计用时、隐私注意事项。
7. **测试**（默认隔离：不联网、不下载、不用 CUDA、不读真实视频、不调用真实 FFmpeg）：抽样可复现；每层一段；缺口重抽；manifest schema；标注 schema 的合法与非法样例；区间展开；原子写入、备份与续标；不开端口调用请求处理函数，覆盖读取片段、保存修改、拒绝非法输入。
8. **在真实数据上生成数据集**（仅 CPU）：用 TASK-134 的代理视频生成 26 段加 1 段试标片段。正式区域文件带有有效的完成标记、且其 SHA-256 与当前文件一致时，写入 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2\`；否则用默认类别写入 `...\gazelle_validation\roi_r2_trial\`，并在实施报告中说明正式数据集待区域文件就绪后重新生成。运行校验；启动服务并确认能加载第一段（用 `--labels-path` 指向临时文件），确认后关闭服务进程。

### 非目标

- 不改运行时代码（`gazelle/`）与 CLI。
- 不做区域推断与评估（第 3 阶段）。
- 不在界面中显示任何模型预测。

### 依据材料

- 规范 r2；TASK-134 的代理视频、`session.json` 与旁注 schema。
- 本文件 r1 的工具结构（服务与逻辑分离、原子写入、`--labels-path`）在 r2 中保留。

### 不可变约束

- 规范 r2 §2 的隐私与数据规则：代理视频、帧、标注不进 Git、不上传；不写入源目录与用户的验收目录。
- AGENTS.md 的默认测试隔离规则。不修改 Conda 环境，不下载。

### 允许动作

新建 `tools/validation/**` 与 `tests/test_validation_*.py`；更新四份用户文档的「研究数据工具」小节与 `tests/test_usage_docs.py`；读取数据根；在 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\` 下创建数据集；按协作方案 §4 提交并推送（只提交代码、测试、默认类别配置与指南），并在 draft PR 发英中双语评论。

### 禁止

提交任何帧、代理视频、标注或输出；新建分支或 PR、合并、force push；修改环境；下载；修改 `gazelle/` 下的运行时代码。

### 验收标准

1. 新增测试全部通过，完整离线门通过，无新增 skip。
2. 数据集包含 27 段（26 段加试标片段）、每段 300 个时间步的拼接帧、manifest 与 `classes.json`；校验命令退出码为 0。
3. 同一种子重复抽样得到相同片段（实施报告附比较命令与结果）。
4. 标注服务只监听 `127.0.0.1`；页面不请求任何外部 URL。
5. `git status` 与提交记录中没有图像、视频或标注数据。
6. Claude 审查时用 `--labels-path` 指向临时文件，在内置浏览器完整标注试标片段，该文件通过校验；正式标注文件保持不存在或不变。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-121-pycache"
& $py -m unittest discover -s tests -p "test_validation_*.py" -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（Claude 审查代码并实际试用界面）。
- 需真实运行：生成数据集，仅 CPU。
- 文档同步：需要。在四份用户文档的「研究数据工具」小节（TASK-132 建立）中加入本任务的工具：写明用途、在仓库根目录运行的入口命令、读取什么、写到哪里、是否调用 FFmpeg、是否使用 GPU 或网络，并链接 `tools/validation/ANNOTATION_GUIDE_CN.md`。`README.md` 与 `README_CN.md` 只放简介与指向 USAGE 的链接；`docs/USAGE.md` 与 `docs/USAGE_CN.md` 放工具表。中英文语义一致；`tests/test_usage_docs.py` 在两份 USAGE 中锁定本任务的入口模块名。原因：这些工具由用户或 Codex 直接运行，属于用户可见的用法，适用 AGENTS.md 的文档同步规则（2026-10-15 按 Codex 接手核对修正）。
- 风险与回退：工具问题只影响标注效率与数据集，不影响运行时；回退方式是 `git revert`，数据集目录可删除重建。
- 依赖：TASK-134；TASK-123 修复后的工具，以及用户画好并导出、带完成标记的正式区域文件（只有文件存在不算就绪，2026-10-16 按审查修订）。区域文件尚未画好时，先用默认类别完成开发与测试，正式数据集等区域文件就绪后再生成。

## 2. 实施报告（Codex 追加，不要修改上文）

### 2026-10-17 Codex 实现与实测；独立试标待 Claude

- 实现提交：`a59d0515fe298054d6661831784bb75b9dd3aa2b`，`Add reproducible multiview annotation toolkit`，已推送到既有分支/draft PR #6。报告与交接 STATE 随后提交。没有开始第三轮。
- 本轮按 STATE 在唯一仓库内 Inline Execution；所有 Python 均使用现有 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，字节码在仓库外。原 Gazelle 环境未使用或修改。
- 新增 `sample_segments.py`、`extract_frames.py`、`labels.py`、`annotate_server.py`、内联页面、默认类别与中文指南；四组隔离 Python 测试、Node 页面 harness；同步四份用户文档与文档检查。已有 `tools/validation/__init__.py` 沿用，没有修改 Gazelle runtime。
- 抽样采用默认 seed 20261015、四个时间分层（不足 45 分钟为两个）；每段 300 步，三机缺口按时间步并集计数，超过 2 秒最多重抽 10 次；加入固定 2026-09-07 22:20:00 pilot，标明不进入正式评估。没有按画面内容挑片段。
- 只有区域文件完成标记和 SHA 有效、并具有 target/cell 时使用正式类别与参考图；否则使用默认类别。目标已存在时拒绝；显式 overwrite 先整体改名保存旧目录，不删除既有标注。
- 精确读取代理帧、校验代理 SHA，拼接 1920×720、JPEG85，逐帧哈希记录。服务业务与 HTTP 分离，只绑定 127.0.0.1，全部资源本地；Host/Origin、CSRF、大小限制和 CSP；不显示模型预测。
- 标注覆盖包含尚未判断的 null，和有效类别 unknown 区分；连续区间、变化点、删除/撤销、他人入镜、备注、原子保存/备份、revision 冲突保护与续标均已实现。严格 validate 拒绝未完成区间。

### 数据集生成与复现

- 输出：`C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial`。
- **27 段（26 正式候选 + 1 pilot），每段 300 步，共 8,100 张拼接 JPEG**；哈希和尺寸校验 exit 0。类别来源 `default-trial`，区域完成状态 `False`；本轮正式区域尚未就绪，因此这是默认类别试用集，正式集待区域导出后重新生成。
- `manifest.json` SHA-256：`a8ba987f3b899f33fc6a5173d213f7eded168fbd48e4f2cdbbd44f8814cf0680`；`classes.json`：`51b0b8535288b635fce190cc9e6e06dfba2eefc3dc899a738721242cc385cec1`。这些是汇总哈希，manifest、帧、视频与标注本身未进 Git。
- 外部脚本 `gazelle_runs/task-121-generate-real.py` 总用时 832.060s。它执行 CLI 抽样后另行调用 `plan(proxies_root, seed=20261015)`，逐项比较 27 段完整元数据，**完全一致**；复现检查 65.830s，证据 `task-121-reproducibility.json`。

- `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe -m tools.validation.sample_segments --proxies-root C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\proxies --dataset-root C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial --regions-path C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\roi\roi_regions.json`：exit 0，65.458s。
- `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe -m tools.validation.extract_frames --dataset-root C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial`：exit 0，508.442s。
- `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe -m tools.validation.extract_frames --dataset-root C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial --validate-only`：exit 0，192.302s。

抽样结果（epoch 是画面显示时钟的数值表示，不追加时区校准）：

| 片段 | 起始代理帧 | 起始时钟 epoch s | pilot | 抽样次数 |
| --- | ---: | ---: | --- | ---: |
| 20260911_pilot | 6072 | 1788819600.000 | True | 1 |
| 20260821_s01 | 1730 | 1786158347.800 | False | 1 |
| 20260821_s02 | 6121 | 1786159226.000 | False | 1 |
| 20260821_s03 | 12599 | 1786160521.600 | False | 1 |
| 20260821_s04 | 17430 | 1786161487.800 | False | 1 |
| 20260828_s01 | 85 | 1787599815.400 | False | 1 |
| 20260828_s02 | 4832 | 1787600764.800 | False | 1 |
| 20260903_s01 | 244 | 1788307249.000 | False | 1 |
| 20260903_s02 | 6089 | 1788308418.000 | False | 1 |
| 20260903_s03 | 12460 | 1788309692.200 | False | 1 |
| 20260903_s04 | 16740 | 1788310548.200 | False | 1 |
| 20260911_s01 | 3216 | 1788819028.800 | False | 1 |
| 20260911_s02 | 6424 | 1788819670.400 | False | 1 |
| 20260911_s03 | 13110 | 1788821007.600 | False | 1 |
| 20260911_s04 | 14026 | 1788821190.800 | False | 1 |
| 20260925_s01 | 1918 | 1790049962.200 | False | 1 |
| 20260925_s02 | 6000 | 1790050778.600 | False | 1 |
| 20260925_s03 | 9555 | 1790051489.600 | False | 1 |
| 20260925_s04 | 15800 | 1790052738.600 | False | 1 |
| 20261002_s01 | 547 | 1790719290.800 | False | 1 |
| 20261002_s02 | 7399 | 1790720661.200 | False | 1 |
| 20261002_s03 | 10992 | 1790721379.800 | False | 1 |
| 20261002_s04 | 15778 | 1790722337.000 | False | 1 |
| 20261009_s01 | 3201 | 1791256219.800 | False | 1 |
| 20261009_s02 | 5967 | 1791256773.000 | False | 1 |
| 20261009_s03 | 9241 | 1791257427.800 | False | 1 |
| 20261009_s04 | 13946 | 1791258368.800 | False | 1 |

### 验证命令、真实浏览器与失败记录

```powershell
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
node tests/roi_page_test.cjs
node tests/annotation_page_test.cjs
git diff --check
git status --short
```

- 最终相关代码的完整离线门 **607 tests / 10.748s / 0 skip，exit 0**；编译、两条 CLI、两个 Node harness、diff-check 全通过。日志 `gazelle_runs/round2-*-final.log`。默认测试使用合成帧/临时目录/假边界，不访问网络或真实 FFmpeg、CUDA、模型。非致命输出为 OpenCV 合成坏容器的 `moov atom not found` 与 Git LF/CRLF 提示。
- 合成浏览器实测：类别变化点、unknown、删除/撤销、他人入镜区间、备注即时保存与刷新恢复；严格 labels validate 通过。两段合成数据还验证未完成入镜起点阻止切片，取消后可切片；先复现 Node 失败再修复。截图只含合成测试图，留在外部日志目录。
- 真实 fixed pilot 预检：300 张、1920×720、哈希验证通过，41.203s；单段试用页面加载第一帧，无正式标签写入。该先行 probe 不充当 27 段完成证据。
- 最终完整数据集页面实际加载：27 个片段选项，首段 `20260911_pilot`，300 时间步；首帧 complete，1920×720；只读检查后关闭临时标签页与服务。启动使用 `--labels-path` 指向 `codex_load_trial.json`，正式 `labels.json` 保持不存在；没有代用户判断真实注视类别。
- 最终进程监听实测为且仅为 `127.0.0.1:8781`（psutil 读取自身服务连接）；页面唯一图像资源为本机 `/frame/20260911_pilot/0`，浏览器 warn/error 为空。最终服务 PID 226380 按命令行和数据集路径确认后终止；进程退出 1 是这次主动清理，非服务运行故障。页面只读加载也未创建 `codex_load_trial.json`。
- 本机端口检查曾被 PowerShell 权限拒绝；改为按已知 PID 与完整服务命令行确认自己启动的进程后关闭，没有提权或修改系统设置。一次 UI 的标签定位无匹配，依据页面实际 select 元素继续操作，不是产品加载失败。
- 外部证据：`task-121-sample.log`、`task-121-extract.log`、`task-121-dataset-validation.log`、`task-121-real-summary.json`、`task-121-browser-load.json`；合成标签严格校验日志及真实 pilot probe 独立保留。

### 自主决定（A 级）

- 三机缺口取并集，避免同一缺失时刻重复累计；每层在能容纳整段的起点范围均匀抽样，保留所有重抽记录。
- 默认类别是 trial；已存在数据目录显式 overwrite 时保留成带时间戳备份，避免删除用户标注。
- 序列化 autosave 队列配合服务器 revision/文件哈希冲突检查；备注 input 即保存。图片未加载完成前禁止判断，未完成入镜起点禁止切片，防止标签绑定到错帧或丢失区间。
- 只读加载不创建 labels；可用不同 labels-path 独立试用。

### 范围外改动

- `tests/annotation_page_test.cjs`：用现有 Node 做 DOM 行为隔离验证，补足 Python HTTP 测试无法覆盖的浏览器操作；没有引入依赖或外部资源。其余文件均在契约范围。

### 待 Claude 判断（B 级）

- Q-007、Q-008、Q-009 从上游继承：运动事件同步未确认，内部覆盖缺口策略待确认，代理固定时钟抽查 60/63 通过（两项缺失、一项原始源帧也复现的 −1.4s 超限）。当前试用集验证工具/可重现采样，不证明科学同步或标注准确性。建议先审查这些证据，再决定正式数据集与评估使用。
- 固定抽出的 `20261002_s01` 位于该摄像机映射的早期偏移区段，仍按原种子保留，没有因失败而排除或另挑片段。缺口检查只衡量最近源帧距离，不能代替真实时钟/物理同步精度检查；正式使用仍须先解决上游同步问题。
- Claude 尚需在独立稳定状态下完整试标 300 步 pilot，使用临时 labels-path 并运行严格校验；Codex 的合成试标和真实首帧加载不能替代这一验收。

### 待用户决定（C 级）

无新增授权问题。正式区域绘制与 26 段人工标注是现有流程中的用户步骤，尚未完成；不能以默认类别 trial 替代。

### 外部活动、反证复核与完成状态

- 真实 CPU/OpenCV 代理解码、JPEG 写入与 loopback 浏览器服务已发生；TASK-121 没有调用 FFmpeg 子进程、模型、CUDA、下载或修改 Conda，也没有向外部发送数据。原始视频只读；全部代理、帧、标签与日志在授权外部目录。
- 反证检查：坏 SHA/维度、manifest 不一致、非法或不完整区间、冲突保存均拒绝；default trial 和完成标记分支有测试；同种子两次完整比较一致；最终全量 8,100 帧校验完成，正式标签仍不存在。真实 UI 检查只证明加载/基本操作，不证明人工判断质量。
- 代码、离线门、试用数据生成/复现/校验与本机页面加载：**已实际运行**；Claude 独立审查、完整 pilot 试标、用户正式区域与标注、阶段科学正确性：**待独立验收**。四份用户文档同步完成；源码/文档提交不含任何真实媒体或标注。

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 试标结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户标注体验与问题：
