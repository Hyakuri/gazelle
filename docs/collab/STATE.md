# 协同状态（唯一入口）

Codex 与 Claude 每次开始工作先读本文件，再按控制块行事。字段归属与循环步骤见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md) §3。

## 控制块

| 字段 | 当前值 |
| --- | --- |
| stage | 阶段 2：作业数据可用、多机同步、正确性修复，建立区域标注 |
| branch | `feature/stage2-correctness`（基于 PR #5 head `bbec056`） |
| pr | [#6](https://github.com/Hyakuri/gazelle/pull/6)（draft）；正文来源 `docs/collab/STAGE2_PR_BODY.md` |
| writer | codex |
| next_actor | codex |
| current_task | `docs/collab/tasks/TASK-139-content-calibrated-sync.md`（用户本轮已批准 D18，见 Q-010） |
| after_current | `docs/collab/tasks/TASK-102-spawn-frame-confirmation.md`，然后 `docs/collab/tasks/TASK-002-face-ray-sign-alignment.md`，然后结束本轮并把 `next_actor` 改为 `claude` |
| environment | `Gazelle-next`：`C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`（用户 2026-10-17 决定 D16）。现有 `Gazelle` 作为回退保留，不改动 |
| last_pushed | `3242aed`（TASK-139 最终数值误差守卫；其后报告提交以实时 Git 为准） |
| last_accepted | `b527287`（2026-10-17 第 2 轮审查：此前全部提交已通过，包括 TASK-001、TASK-123 修复、TASK-135、TASK-137。其后的 TASK-133 只部分通过，TASK-134、TASK-121 的结论见下表） |
| 更新 | 2026-10-17，Claude：第 2 轮审查完成；同步问题已查明，建议同步协议 r2（D18，待用户批准）。第 3 轮交 Codex，第一项为 TASK-138 |

## 第 3 轮交接记录（Codex，2026-10-17）

- TASK-138 → TASK-136 → TASK-139 → TASK-102 → TASK-002 均已实施、提交并推送；TASK-102/002 在等待 TASK-139 CPU 批次时完成。各任务为 `ready-for-review`，不代表独立验收。最终相关代码离线门 **643 tests / 12.248s / 0 skip**；compileall、help、list-models、diff-check 通过。仅主线程 Inline Execution，无子代理。
- **用户授权与区域**：D18 已直接批准，见 Q-010；下方第 2 轮的“待决定/现在可以画区域”是历史说明，勿要求用户重做。用户已完成正式区域并批准唯一修正 `work_area.kind: target → cell`。TASK-138 保留全部顶点、名称和颜色，完成 4 targets + 1 cell 的 v2 导出；最终只读复核区域、完成标记、参考图和 classes 哈希均未变。
- **TASK-136**：6 次真实 300 帧 CUDA 对照，4K static 推理中位数 123.142→42.298 ms（降低 65.651%）；预测状态/峰坐标对照通过。**TASK-102**：四次真实 30 帧对照，A/B 首帧 no_head 均 1→0，provisional 显式记录；身份质量仍待独立审查。**TASK-002**：符号性质测试与转码旋转组通过；第 15 帧缺少 face pose、原图旋转组漏检，Q-011 未解决。
- **TASK-139**：40/40 v2 基础映射有效；六会话校准通过，20260911 E 的 MAD=0.101424 s 超过 0.08，最佳分段比=0.592274 未满足减半。完成 **18/21 新代理、297,855 帧**，视频/旁注/哈希/两套解码计数一致；1009 A 保留 9 个缺口步。新代理残差 **12/18 对通过**，时钟 **54/54 可评估、49/54 通过**；六份验证 JSON、18 张事件条图已生成。0821/0828 本机各门通过，其余四会话失败按原数值保留。详见 TASK-139 最终报告和 Q-012。
- **正式标注仍不能开始**：0911 三段代理及验证阻塞，七会话数据集预检明确失败；没有生成六会话替代集或 `roi_r2`，没有写正式 labels。旧代理和试用集原路径未覆盖/移动；新部分产物在 `gazelle_data\workdata\proxies_v2_pending`。完整替换与改名切换等协议判断后执行。
- 最终 guard 修复提交 `3242aed` 后，只读数值重放确认真实数据时间值不变；媒体保留 `d7431e0`/`bbcbc31` 原指纹，没有伪装为最终提交后重跑。12 个拟合全域误差保守上界 0.002502 ms，40 个端点重放最大误差 7.15e-7 s；说明见 TASK-139。
- 普通沙盒预检与授权 yun Git/GitHub 例外分别记录；`Gazelle-next` 使用、原 Gazelle 保留。真实 CPU/GPU/MediaPipe、缓存/网络、FFmpeg 活动详见各任务，不用 mocks 代替实测。未安装、修改环境、下载新资源或上传媒体/标注/权重/缓存/凭据，源目录只读；20261016 未纳入。旧数据与忽略文件保留。
- **Claude 接手**：先按稳定提交复跑与审查 A 级决定，处理 Q-012 的实际同步失败/分段与 OSD 定义，以及 Q-011 的真实样例问题；目视核对全部事件。TASK-101 继续 blocked，必须等 TASK-102 审查通过。`last_accepted` 保持 `b527287`，最终用户在独立 checkout 验收。

## 第 2 轮审查结论（Claude，2026-10-17）

| 任务 | 结论 | 要点 |
| --- | --- | --- |
| TASK-137 | accepted | 15 个版本、回退文件（同一 Git blob）、AGENTS.md 只改环境句子、四份文档均核对；三次真实 smoke 与 Claude 的参照运行逐项相同。Q-006 Codex 正确，评估记录已更正 |
| TASK-123 | accepted | 浏览器实测五项必须修复全部通过：内部区域可选可拖、参考图四区域边线齐全、双击 3 个顶点、完成标记导出后生成且修改即失效、自定义颜色不撞色。应修项转入 TASK-138 |
| TASK-135 | accepted | r4 表格与 10 分钟无漂移回归正确，尾部检查满足各项。应修：尾部时间比较未扣除 0.033 s 起始时间，余量只有 0.333 ms，转入 TASK-138 |
| TASK-133 | 部分通过 | 时钟识别、锚点、身份核实与读取修复通过；时间映射与同步检验 changes-requested，由 TASK-139 取代（见同步分析） |
| TASK-134 | accepted（生成机制） | 网格、最近帧、缺口、来源旁注与原子发布正确；Q-008 做法确认。现有代理的时间轴继承上游误差，不能用于正式数据集，由 TASK-139 重新生成 |
| TASK-121 | changes-requested | Claude 完整试标 pilot 300 步，工具主体可用。阻塞问题：一次按键会标满整段并自动记为完成（GZ-27），由 TASK-138 修复 |

同步结论见 [evidence/2026-10-17-sync-analysis.md](evidence/2026-10-17-sync-analysis.md)：

- 三台摄像机的画面时钟各自设定。以前方 B 为基准，右侧 A 偏 −0.63 至 +2.83 秒；全局 E 偏 −0.95 至 +2.47 秒，并有漂移。
- E 的显示时钟有亚秒级跳变，而帧时间稳定。
- 用画面运动测得的偏移离散只有 0.02 至 0.07 秒，可以校准到 0.2 秒以内。
- 现有 21 段代理与 27 段试用集只能用于试用工具。

Claude 实际运行的检查：

- 完整离线门 607 项与两个页面 harness；
- TASK-137 的版本、文件与 smoke 复核；
- 区域工具与标注工具在内置浏览器中的完整试用（pilot 300 步）；
- 两个重封装文件的尾部时间核对；
- 21 段代理逐帧解码与七次录制的跨机运动分析。

另有两份独立代码审查。详见各任务文件 §3。

## 第 1 轮审查结论（Claude，2026-10-16）

| 任务 | 结论 | 要点 |
| --- | --- | --- |
| TASK-131 | accepted | 独立复跑全部通过；契约 r3 的回退公式有累积漂移，已修订为 r4，由 TASK-135 实施 |
| TASK-132 | accepted | 清单与 11 个重封装文件经核对有效；尾部解码检查偏弱，由 TASK-135 加强 |
| TASK-123 | changes-requested | 浏览器实测发现 5 项必须修复：叠放顺序使内部区域无法编辑、参考图丢失目标区域、双击闭合产生重复顶点、区域文件在完成前就已存在、类别键与颜色缺少约束 |
| TASK-001 | accepted | 无阻塞问题 |

Claude 实际运行的检查：完整离线门 562 项；29 个 MP4 分段 17,400 帧的时间戳检查；原始 AVI 截断检查；不加载 MediaPipe 的 300 帧 GPU smoke；清单与重封装报告逐项核对；区域工具在内置浏览器中的完整试用。另有两份独立代码审查。详见各任务文件 §3。

## 第 1 轮交接记录（Codex，2026-10-16）

- TASK-131 → TASK-132 → TASK-123 → TASK-001 均已实现、提交并推送，状态为 `ready-for-review`，不是独立验收通过。完整执行记录在各任务的「实施报告」。最终离线门 **562 项通过，无新增 skip**。
- 真实检查：29 个 MP4 各 600 帧，时间戳违规 0；原始 AVI 正确以截断失败退出；300 帧 GPU smoke 成功；40 文件清单、11/11 AVI 重封装校验通过；84 张候选帧通过哈希与尺寸验证，本机页面加载通过。
- 区域工具服务与临时浏览器页已关闭，正式 `roi_regions.json` 不存在。Claude 下一步按原验收要求，用临时 `--regions-path` 试画四个默认区域并复核参考图；用户之后再画正式区域。没有开始第 2 轮。
- 外部活动、失败与自主决定均已记录，特别是 Torch Hub 缓存回退、MediaPipe 原生遥测连接失败、OpenCV 尾部 seek 偏移与修正。没有下载、环境修改或数据上传；源目录只读，派生物留在仓库外。
- PR #6 已分别发布 TASK-131、TASK-132、TASK-123、TASK-001 英中双语报告。无待用户授权或阻塞性契约问题；各 A 级决定与独立复跑仍请 Claude 审查。`last_accepted` 保留迁移基线，未代替验收更新。

## 第 2 轮交接记录（Codex，2026-10-17）

- TASK-137 → TASK-123 修复 → TASK-135 → TASK-133 → TASK-134 → TASK-121 已按顺序实现、提交并推送到既有 draft PR #6，各任务 §2 为执行报告；状态为 `ready-for-review`，不是独立验收通过。仅主线程 Inline Execution，没有子代理；本轮没有开始 TASK-136。
- 项目已切换到现有 `Gazelle-next`，原 Gazelle 回退环境保留。普通沙盒的仓库、三个外部目录与临时目录写入预检已通过；Git/GitHub 使用已授权 yun 上下文，不把它写成普通沙盒认证通过。没有安装、卸载、修改 Conda 或下载资源。
- 最终相关代码离线门 **607 tests / 10.748s / 0 skip**，compileall、help、list-models、两个 Node harness、diff-check 通过。此前 TASK-137 的三组 300 帧真实 smoke、TASK-123 的 84 候选与合成浏览器交互、TASK-135 的 11/11 重封装尾部复核均已记录，不能替代 Claude 独立复跑。
- TASK-133：40/40 时间映射、12/12 参考时钟；运动同步 **9/42** 通过，33 项失败保留。TASK-134：**21/21 段、352,062 帧**，40 源文件均到 EOF，容器帧数差异超过 0.5% 的文件为 0；一文件实际少 48 帧（0.110223%）。固定代理时钟抽查 **60/63**：两项识别缺失、一项 −1.4s 超限，后者在原始源帧复现。
- TASK-121：默认类别试用集 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial` 已生成 **27 段、8,100 张**拼接图，独立抽样完全一致、两轮全量图片校验通过，总用时 832.060s；真实页面加载全部片段与首帧通过，实际监听仅 `127.0.0.1:8781`。临时页面、服务及本轮计算进程已关闭。
- 正式 `roi_regions.json`、试用集的正式 `labels.json` 和 Codex 临时加载标签文件均不存在。用户完成区域后还需生成正式数据集；当前试用集不能作为已满足科学同步精度的正式数据。`20261002_s01` 按固定种子保留在已知早期偏移区段，没有剔除。
- **Claude 接手重点**：独立复跑并确认各 A 级决定；处理 Q-006 依赖事实、Q-007 物理运动同步、Q-008 连续网格内部缺口、Q-009 OCR 与早期时间映射偏移。按 TASK-121 §3 用独立 `--labels-path` 完整试标 300 步 pilot，再运行严格 labels validate。Codex 的合成试标和真实首帧加载不代替该步骤。
- 四份用户文档同步；真实媒体、派生 JSON、模型、缓存与凭证未提交或上传，源数据只读。各任务 PR 评论均采用 English、`---`、中文摘要。`last_accepted` 保持 `e7244d0`，等待 Claude 更新。

## 任务队列（阶段 2）

| 轮次 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| Codex 第 1 轮 | TASK-131 读取器：容器时间戳、严格递增、截断即失败 | accepted | 537 项离线测试；29 段各 600 帧无违规；AVI 失败与 300 帧 GPU smoke 均已实测 |
| Codex 第 1 轮 | TASK-132 作业数据清单与 AVI 无损重封装 | accepted | 40 文件清单；11/11 重封装校验通过；生产读取器 600 帧检查通过 |
| Codex 第 1 轮 | TASK-123 全局摄像机画面中的区域标记工具 | accepted（第 2 轮修复后） | 见「第 2 轮审查结论」 |
| Codex 第 1 轮 | TASK-001 参数在 `--overwrite` 删除前校验 | accepted | 562 项最终离线门通过；static/json 两条旧结果保护回归通过 |
| Claude | 审查第 1 轮，试用区域标记工具 | 完成 | 见「第 1 轮审查结论」 |
| 用户 | 用 TASK-123 的工具画出区域，约 10 分钟 | **现在可以开始** | 命令见「给用户的说明」 |
| Codex 第 2 轮 | TASK-137 项目环境切换到 `Gazelle-next`（仓库侧） | accepted | |
| Codex 第 2 轮 | TASK-123 修复必须修复 1 至 5 | accepted | |
| Codex 第 2 轮 | TASK-135 第 1 轮审查的后续加固 | accepted | 尾部时间比较的起始时间偏差转入 TASK-138 |
| Codex 第 2 轮 | TASK-133 画面时钟识别、时间映射与同步检验 | 部分通过 | 识别、锚点、身份核实通过；时间映射与同步检验由 TASK-139 取代 |
| Codex 第 2 轮 | TASK-134 5 Hz 同步代理视频 | accepted（生成机制） | 现有代理的时间轴不能用于正式数据集，由 TASK-139 重新生成 |
| Codex 第 2 轮 | TASK-121 多视角同步片段的区域标注工具（D12 r2） | changes-requested | 一次按键标满整段并自动完成（GZ-27），由 TASK-138 修复 |
| Claude | 审查第 2 轮，完整试标 pilot 片段 | 完成 | 见「第 2 轮审查结论」与同步分析 |
| 用户 | 决定 D18：同步协议 r2 | **待决定** | 见「给用户的说明」与 Q-010 |
| Codex 第 3 轮 | TASK-138 标注与区域工具的后续修复 | ready-for-review | 611 tests、两个 Node harness、300 步浏览器验证及 11/11 只读尾部复核通过；见任务 §2 |
| Codex 第 3 轮 | TASK-136 Gazelle 输入预处理移到推理设备 | ready-for-review | 616 tests；6 次 300 帧 CUDA 对照通过，4K static 中位数降低 65.651%；见任务 §2 |
| Codex 第 3 轮 | TASK-139 同步协议 r2：以 B 为基准的画面内容校准 | ready-for-review | 643 tests；18/21 代理完成，残差 12/18、时钟 49/54 通过；0911 与七会话数据集阻塞，见 Q-012 |
| Codex 第 3 轮 | TASK-102 新轨迹首帧立即确认（D2） | ready-for-review | 633 tests；四次真实 30 帧对照，A/B 首帧 no_head 均 1→0；见任务 §2 |
| Codex 第 3 轮 | TASK-002 面部射线与 roll 符号对齐 | ready-for-review | 637 项离线门通过；转码旋转组通过；帧 15 无 pose 与原图漏检见 Q-011 |
| Codex 第 3 轮 | TASK-101 人脸与姿态关联修正（D1） | blocked | 等 TASK-102 审查通过；GZ-01 |
| 用户 | 标注 26 段，约 2 小时 | 待前置 | 需 TASK-138、TASK-139 与正式区域都完成后，按新数据集标注 |
| Claude | 阶段 2 验收：离线门、作业数据真实 smoke、同步精度、修复前后对比 | 未开始 | |

第 3 阶段（多摄像机注视区域推断）的设计已于 2026-10-15 获批（D13 至 D15），任务契约在阶段 2 验收时编写，见 [ROADMAP.md](ROADMAP.md)。
摄像机角色：前方为カメラ2（`cam_b`），右侧为カメラ1（`cam_a`），全局为設備カメラ（`cam_e`）；一律按物理编号取文件。

## 给 Codex 的说明

- **本轮最终收据（Codex，2026-10-17）**：当前轮次实现与可运行验证已结束，详见上方「第 3 轮交接记录」；不得把下方原始调度说明当作重新开始本轮的指令。正式 ROI 原 JSON 精确备份与授权修正核对在 `gazelle_runs\task-138\`，输出在 `gazelle_data\workdata\roi\`。该授权不扩展为任意修改正式区域；正式标注仍等同步问题与独立验收。

- **本轮开始**：按协作方案 §3.1 第 3 步，先提交 Claude 留下的文档改动（`Record coordinator updates`）并推送，再用 `gh pr edit 6 --body-file docs/collab/STAGE2_PR_BODY.md` 同步 PR 正文。
  - 新文件：`evidence/2026-10-17-sync-analysis.md`、`tasks/TASK-138-annotation-and-roi-followups.md`、`tasks/TASK-139-content-calibrated-sync.md`。
  - 同时提交：各任务文件 §3 的第 2 轮审查结论、问题登记表 §7，以及评估记录中 Q-006 的更正。
- **本轮顺序**：TASK-138 → TASK-136 → TASK-139 → TASK-102 → TASK-002，然后结束本轮。
  - TASK-139 只在「待决问题」中 Q-010 显示用户已批准 D18 时执行。未批准就跳过，在报告中说明，并继续后面的任务。
  - TASK-101 仍等 TASK-102 审查通过。
- **数据**：
  - 现有 21 段代理、27 段试用集与时间映射，只用于工具试用与对照，不得用于正式数据集或评估。
  - 不要删除它们；TASK-139 会把它们改名备份。
  - 源目录新出现的 `20261016` 不纳入研究集。
- **区域**：用户可能在本轮期间画正式区域，`roi_regions.json` 与完成标记由用户产生。Codex 不要创建、修改或删除它们；TASK-138 的测试与试用一律用临时路径。
- **MediaPipe**：用户 2026-10-16 决定开发阶段接受遥测（GZ-23），可以照常运行 MediaPipe。
- **环境**：所有 Python 命令使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`。现有 `Gazelle` 环境作为回退保留，不要使用，也不要修改；不在任何环境中安装或卸载包。
- **问题处理按协作方案 §3.5 分级自主**：能自己解决的先解决并记录；设计层面的问题交 Claude，同时继续不受影响的工作；只有需要新授权、用户偏好或用户亲自操作时才问用户。硬边界不变。
- **GitHub 命令**：用户 2026-10-16 给予常设批准（协作方案 §7），本分支与 PR #6 的发布类命令可以直接在用户上下文 `yun` 中运行。
- 每个任务推送后，在 PR #6 发一条英中双语评论（协作方案 §4），包含 §3.5 规定的四个小节。
- 数据规则（协作方案 §5）：`E:\Gazelle_Workdata\` 只读；派生数据写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`；长时间 CPU 任务以低优先级运行；GPU 推理前检查空闲显存。
- 字节码：用 `-I` 运行 Python 时 `PYTHONPYCACHEPREFIX` 不生效；需要隔离时改用 `-X pycache_prefix=<仓库外的短路径>`。

## 给 Claude 的说明

- `next_actor` 为 `claude` 时：按提交 SHA 审查 `last_accepted` 之后的任务，复跑离线门，核对真实检查的数字；逐项确认实施报告中的 A 级自主决定，处理 B 级问题（协作方案 §3.2）。
- 审查 TASK-138：在内置浏览器中实测一键标满后的未看纹理、“本段完成”的启用条件与修改后清除；用 `--segment` 单独严格校验 pilot；核对完成标记中的导出哈希与抽样复制校验。
- 审查 TASK-139：
  - 复算残差滞后。分析脚本 `gazelle_runs\claude-review-r2\sync\analyze_sync.py` 可在新代理上直接运行；注意它对 A 与 B、A 与 E 两对的符号与“X 相对 Y”相反。
  - 目视核对每会话 3 个事件的三视角条图。
  - 检查 0911、0925、1009 的台阶已消失或被正确分段。
  - 通过后在「给用户的说明」写明正式标注的启动方法。
- 在阶段节点更新 `docs/collab/STAGE2_PR_BODY.md` 的状态表，由 Codex 同步到 GitHub。
- 待办：用 `bbec056` 的导出快照在一段同步代理上做修复前基线运行，作为 TASK-101、TASK-102 的对照。
- 字节码：Claude 自己运行 Python 时也用 `-X pycache_prefix`，不要用 `-I` 配合环境变量。

## 给用户的说明

第 2 轮审查已完成：TASK-137、TASK-123、TASK-135 通过；TASK-133 部分通过；TASK-134 的生成机制通过；TASK-121 退回修改。详见「第 2 轮审查结论」。

- **请你决定 D18：同步协议 r2。**
  - 三台摄像机的画面时钟各自设定，按画面时钟对齐后仍差最多约 3 秒（见 `evidence/2026-10-17-sync-analysis.md`）。
  - 推荐：以前方摄像机 B 为基准，右侧 A 与全局 E 用画面运动测出偏移与漂移后校准，精度 0.2 秒以内。
  - 这会把 D13 中“画面时钟上的 5 Hz”改为“以前方摄像机画面时钟为基准、内容校准后的 5 Hz”；网格、分辨率与片段长度不变。实施为 TASK-139，约需 6 小时后台 CPU。
- **下一步**：对 Codex 说“继续”。若已决定 D18，请同时告诉 Codex，例如“继续，D18 批准”；Claude 也会在 Q-010 中记录。
- **正式标注暂不开始**：要等三件事完成，即 TASK-138（修复标注工具）、TASK-139（重新生成同步代理）与正式区域。届时这里会写明启动方法。
- **源目录新增 `20261016`**：目前不纳入研究集。若希望纳入，请告诉 Claude，可作为后续补充。
- **已记录的决定**：
  - D16、D17（2026-10-17）：项目使用 `Gazelle-next`，激活命令为 `conda activate Gazelle-next`，现有 `Gazelle` 保留作回退；TASK-136 在第 3 轮实施。
  - MediaPipe 遥测（2026-10-16）：开发阶段接受，研究完成后再做安全处理。
- **画区域（现在可以开始，约 10 分钟）**：在仓库根目录运行：

  ```powershell
  C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe -m tools.validation.roi_server --candidates C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\roi\candidates.json --annotator yun
  ```

  然后用浏览器打开终端显示的本机地址，按 `tools/validation/ROI_GUIDE_CN.md` 操作：先画三个目标区域，最后画工作区，画完点击“导出参考图与类别”。导出之后若再修改区域，需要重新导出。
- **之后**：正式数据集生成后，标注 26 个一分钟片段，约 2 小时，可分多次。
- **可选**：若某名作业者出现在多个日期，提供每个日期的匿名作业者编号（例如 W1、W2），即可做严格的按作业者留一评估。
- **已记录的决定**：分级自主与常设批准（2026-10-16）；摄像机角色、区域标记方式、作业者与机位、D4、D12 r2、D13 至 D15（2026-10-15）。

## 待决问题

两方都可以新增；处理方式见协作方案 §3.5。

| 编号 | 级别 | 提出者 | 内容 | 位置 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-001 | B | Codex | TASK-131 第 4 步在 2000 FPS 时取整后不递增，违反 R1 | TASK-131 实施报告与审查结论 | 已解决：契约 r3 |
| Q-002 | C | Claude | MediaPipe 0.10.35 的遥测如何处理（GZ-23） | 问题登记表 §5 | 已决定（2026-10-16）：开发阶段接受遥测，研究完成后再做安全处理 |
| Q-003 | B | Codex | Torch Hub 加载 DINOv2 时联网探测（GZ-24） | 问题登记表 §5 | 已决定：与 D8 一并在第 4 阶段处理 |
| Q-004 | C | Claude | D16：何时切换到候选环境 `Gazelle-next` | `evidence/2026-10-17-env-next-evaluation.md` §0、§7 | 已决定（2026-10-17）：尽早切换；现有 `Gazelle` 保留作回退，项目改用 `Gazelle-next`；仓库侧由 TASK-137 完成 |
| Q-005 | C | Claude | D17：是否实施 TASK-136（Gazelle 输入预处理移到推理设备） | 同上；`tasks/TASK-136-gazelle-device-preprocessing.md` | 已决定（2026-10-17）：同意，第 3 轮开头实施 |
| Q-006 | B | Codex | TASK-137 与环境评估称 pydeprecate/defusedxml 不再需要，但实际仍是 trackers/supervision 的必需依赖 | TASK-137 实施报告 | 已解决（2026-10-17）：Codex 正确，评估记录已更正；不显式固定可以接受 |
| Q-007 | B | Codex | TASK-133 运动同步仅 9/42 通过；画面时钟一致不等于物理运动同步 | TASK-133 实施报告 | 已查明（2026-10-17）：三机画面时钟各自设定，A 偏 −0.63 至 +2.83 秒，E 偏 −0.95 至 +2.47 秒并有漂移；E 的显示时钟有亚秒级跳变。见同步分析；改方法需用户批准，见 Q-010 |
| Q-008 | B | Codex | TASK-134 固定连续网格与“完全落在重叠时段”存在冲突：20260903 共同覆盖有 0.079/0.134 秒内部缺口 | TASK-134 实施报告 | 已确认（2026-10-17）：采用 Codex 的做法（整体网格、记录覆盖缺口、最近帧与半步长缺口标记），TASK-139 中作为默认行为 |
| Q-009 | B | Codex | TASK-134 固定抽查 60/63：两项识别缺失，20261002 E/k1750 为 −1.4 秒超限 | TASK-134 实施报告 | 已查明（2026-10-17）：超限来自 20261002 E 前 571 秒的显示时钟成片偏移（−0.93 秒）加整秒读数下限；新抽查规则（邻帧补读、E 按 ±2 秒粗查）在 TASK-139 实施 |
| Q-010 | C | Claude | D18：采用同步协议 r2（以前方摄像机 B 为基准，A 与 E 用画面运动校准偏移与漂移）；D13 的时间轴定义随之改为“以 B 的画面时钟为基准、内容校准后的 5 Hz” | `evidence/2026-10-17-sync-analysis.md` §7；`tasks/TASK-139-content-calibrated-sync.md` | Codex 收讫用户直接批准（2026-10-17）：“D18 批准，按你的推荐进行。” TASK-139 的用户授权已满足；Claude 后续归档决定 |
| Q-011 | B | Codex | TASK-002：原始 GIF 与转码视频第 15 帧均无 face head-pose；原图旋转组漏检，转码旋转组 roll 与方向检查通过 | TASK-002 §2；外部 task-002/comparison.json、extra-comparison.json | 待 Claude 在同素材/环境独立复跑并判断真实样例；未替换验收帧或降低门槛，计算性质测试已通过 |
| Q-012 | B | Codex | TASK-139 协议边界及真实失败：MAD 可掩盖少数台阶；正台阶可能无解；B 时间轴与各自 OSD 容差冲突；新代理六对残差超限 | TASK-139 §2 最终报告；外部 task-139/protocol-edge-cases.json、0911-split-diagnostics.json、final-output-audit.json | 0911 E：53 窗、MAD=0.101424>0.08，最佳分段比=0.592274；同样本互相关与参考一致。新代理 0903 E-B/A-E、0925 A-B/A-E、1009 A-B/E-B 残差失败；1002 A 三项 +2.8/+2/+2 s、1009 A 两项 +1.8/+1.4 s 的 OSD 超限。18/21 代理、12/18 残差对、49/54 时钟通过，七会话数据集阻塞。未改门槛、删窗口或会话；推荐 Claude 先复核源帧/固定产物再修订契约，尚未暂定实施 |

## 已完成

| 事项 | 状态标签 | 证据 |
| --- | --- | --- |
| 交接包恢复、overlay 哈希核对（Gate A） | 已实际运行 | `evidence/2026-10-14-destination-acceptance.md` |
| 模型缓存迁移，212 文件 SHA-256 一致 | 已实际运行 | `_handoff_archive\models-cache-transfer-20261014.json`（仓库外） |
| 离线门 531 测试通过（Gate B） | 已实际运行 | 同上 |
| 真实 smoke：prepare-only、图像 3 种、视频 2 种（Gate C） | 已实际运行 | 同上；产物在 `_handoff_archive\smoke-20261014\`（仓库外） |
| 全库只读分析：104 个问题，87 确认，17 驳回 | 已满足本轮验收（协调者自审） | `analysis/` |
| 项目目标确认（v2，依据用户 2026-10-15 的回答） | 已确认 | `PROJECT_GOALS_CN.md` |
| 作业数据分析：清单、编码、时间戳、同步、视角、样例来源 | 已实际运行（只读） | `analysis/2026-10-15-workdata-analysis.md` |
| D1、D2 设计规范与任务契约 | 已提出，方向已获用户批准 | `../superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md` |
| 验证集规范 r2 与第 3 阶段设计 | 已获用户批准（2026-10-15） | `../superpowers/specs/2026-10-15-workdata-validation-set-design.md`、`../superpowers/specs/2026-10-15-multicamera-attention-design.md` |
| 用户决定：摄像机角色、区域标记方式、作业者与机位、D4、D12 r2、D13 至 D15 | 已确认 | `PROJECT_GOALS_CN.md` §4 |
| Codex 只读接手核对（HEAD `ef203a4`）：理解一致；指出 TASK-131 截断容差错误、研究工具文档同步冲突、会话写权限仍在旧目录 | 契约问题已由 Claude 修正；权限待用户设置 | `tasks/TASK-131-video-reader-timestamps-and-truncation.md`、`QUICKSTART_CN.md` |
| Codex 第 1 轮预检、首次推送与 draft PR #6；报告 TASK-131 第 4 步的高帧率边界冲突 | 已实际运行（Codex） | `tasks/TASK-131-video-reader-timestamps-and-truncation.md` 实施报告 |
| TASK-131 契约 r3 澄清；分级自主与常设批准写入协作方案 | 已修订（协调者） | `tasks/TASK-131-video-reader-timestamps-and-truncation.md` 审查结论、`COLLABORATION_PLAN_CN.md` §3.5 与 §7 |
| Codex 第 1 轮：TASK-131、TASK-132、TASK-123、TASK-001 实现与真实检查 | 已实际运行（Codex） | 各任务文件 §2 |
| Claude 第 1 轮审查：离线门、时间戳、截断、GPU smoke、清单与重封装、区域工具浏览器试用 | 已实际运行（Claude）；TASK-131、132、001 accepted，TASK-123 changes-requested | 各任务文件 §3 |
| 候选环境 `Gazelle-next` 评估：MediaPipe 1.1.1 分析、离线门、真实 GPU 运行、视频读取与渲染比对、速度分析、优化探针与管线级实测；独立审查代理逐项核对数字，已按结果修正 | 已实际运行（Claude）；原 `Gazelle` 环境未改 | `evidence/2026-10-17-env-next-evaluation.md` |
| 用户决定 D16（尽早切换，项目改用 `Gazelle-next`，原环境保留）与 D17（同意 TASK-136） | 已确认（2026-10-17） | 同上 §0 |
| Codex 第 2 轮：TASK-137、123 修复、135、133、134、121 实现与真实运行 | 已实际运行（Codex） | 各任务文件 §2 |
| Claude 第 2 轮审查：离线门、TASK-137 复核、两个工具的浏览器实测与 pilot 完整试标、21 段代理跨机运动分析；两份独立代码审查 | 已实际运行（Claude）；结论见「第 2 轮审查结论」 | 各任务文件 §3；`evidence/2026-10-17-sync-analysis.md` |

## 注意

- 模型缓存 `models/`、运行输出、验证集与作业数据的派生物都不在 Git 中，也不上传到任何服务。
- overlay 文件为 LF，checkout 其余为 CRLF；`git diff --check` 只提示不报错，提交时 Git 统一为 LF。
- 「复核确认」结论来自同产品只读代理，不等于独立验收。
