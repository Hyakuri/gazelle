# 协同状态（唯一入口）

Codex 与 Claude 每次开始工作先读本文件，再按控制块行事。字段归属与循环步骤见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md) §3。

## 控制块

| 字段 | 当前值 |
| --- | --- |
| stage | 阶段 2：作业数据可用、多机同步、正确性修复，建立区域标注 |
| branch | `feature/stage2-correctness`（基于 PR #5 head `bbec056`） |
| pr | [#6](https://github.com/Hyakuri/gazelle/pull/6)（draft）；正文来源 `docs/collab/STAGE2_PR_BODY.md` |
| writer | none |
| next_actor | claude |
| current_task | `docs/collab/tasks/TASK-102-spawn-frame-confirmation.md`（已按授权完成 TASK-140 → TASK-124 → TASK-102 第 2 轮修复的执行与报告；三项待 Claude 审查） |
| after_current | 第 4 轮执行结束，交回 Claude；先审查三项任务并处理 Q-014、Q-015、Q-016，再决定后续任务。正式数据集仍未生成，TASK-101 仍 blocked |
| environment | `Gazelle-next`：`C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`（用户 2026-10-17 决定 D16）。现有 `Gazelle` 作为回退保留，不改动 |
| last_pushed | `e9b37443f102e1956827c68d7ba4d87eab631016`（本轮全部实现及最终报告；其后仅任务状态/报告链接与本 STATE 交接提交，以实时 Git HEAD 为准） |
| last_accepted | `1c761c5`。2026-10-17 第 3 轮审查：此前全部提交已通过，包括 TASK-121 与 TASK-138、TASK-136、TASK-134 的生成机制。TASK-133 的时间映射与同步检验部分由 TASK-139 取代。其后：TASK-139 部分通过；TASK-102 changes-requested；TASK-002 单独通过（`b24dd67`、`d9a4adc`） |
| 更新 | 2026-10-18，Codex：第 4 轮执行结束，释放写入权并交 Claude。离线门 668 项通过；同步 7/7 通过，但 0911 时钟不足、0903 切点定位及 TASK-102 smoke 预期需 B 级判断。未切换正式数据 |

## 第 4 轮交接记录（Codex，2026-10-18）

- **执行范围**：主线程 Inline Execution，无子代理。TASK-140 长时间 CPU 期间完成 TASK-124 与 TASK-102 第 2 轮修复；三项已实施、测试、提交推送并分别发布双语报告，状态为 `ready-for-review`，不代表 Claude 或用户验收。最终相关代码离线门 **668 tests / 12.529s / 0 skip**；compileall main.py gazelle tests tools、help、list-models、diff-check 均通过。之后只改执行报告与状态。
- **TASK-140**：七份 v3 拟合均合格；五会话保留 v2 代理与原来源，0903 三机重建、0911 三机新建。21 段候选代理共 **352,050 帧**，本轮新编码 108,180 帧；视频/旁注/SHA/解码/规格检查通过。25 张事件条图逐像素检查通过，Codex 目视抽查 11 张；全量独立目视仍待 Claude。同步按第 6 条 **7/7 通过**（20 对通过、0903 A–E 4 窗证据不足，推算 A−E=+0.015140 s）。
- **正式数据交付仍阻塞**：总验证 **6/7 通过**，0911 时钟只有 **8/9 可评估**，低于 90%；0903 第一切点 23 个细化窗全无效，切点条图为空工位。未放宽门槛、换时钟样本或删除会话。旧 `proxies`、`timemaps`、`roi_r2_trial` 原路径保留；未创建 `roi_r2` 或正式 labels。新媒体分别留在 `proxies_v2_pending`（保留五会话）和 `proxies_v3_rebuild`（0903/0911），新映射/验证在 `timemaps_v3` / `sync_validation_v3`。
- **TASK-124**：服务端只认已保存的已看范围；播放保存降频，暂停等边界立即保存；错误消息、区域完成状态与 remux 缺失 start_time 均已加固。真实浏览器试用保留 193/300 已看步，重开续播后完成；连续播放写盘间隔 1.032907–1.293548 s，暂停立即保存。只写外部临时试用副本，没有改正式标注。
- **TASK-102 第 2 轮**：临时头胜出时保留已确认桥接，P0/P1 回归通过。真实 30 帧 CUDA/MediaPipe smoke 的模型与编码命令成功，但“原 A 三行 tracked_only 应恢复”的包装断言失败：这些帧实际被合法 provisional 头占用。真实仲裁前诊断确认桥接保留；没有为恢复计数改 selector。Q-016 待 Claude 澄清，TASK-101 保持 blocked。
- **来源与保护**：最终补齐采样指纹并校验 21 份旧旁注/像素，未改写旧样本或生产来源。新代理保留 `745309b` 的生成指纹，不声称最终 guard 后重跑。40/40 来源/重封装 size/mtime 匹配；正式区域、完成标记、参考图、classes 哈希与既有导出一致。原始数据只读，20261016 未纳入。没有环境修改、安装、下载、媒体/标注/权重/缓存/凭据上传。
- **真实活动**：TASK-140 仅 CPU、PyAV/OpenCV、真实 FFmpeg/ffprobe；低优先级长任务最多三进程。TASK-102 使用已有 `gazelle_dinov2_vitb14_inout` 缓存与 CUDA/MediaPipe，Python 审计阻断一次 Hub request 后走缓存；原日志与失败保留。普通沙盒预检与 yun Git/GitHub 授权例外分别记录。所有本轮长任务已退出、临时标注服务已结束，未清理未知/既有忽略文件。
- **Claude 接手**：审查各任务 A 级决定；处理 Q-014 的未定位切点、Q-015 的同源帧时钟补读、Q-016 的 smoke 输入/预期差异；独立复跑与目视后再决定能否正式切换/生成数据集。没有新增 C 级问题，不需用户重做区域或认证。`last_accepted` 维持 `1c761c5`，用户独立 checkout 最终验收仍未完成。
- 提交：`51659db` 协调文档，`745309b` TASK-140 核心，`2dc76be` TASK-124，`97ef104` TASK-102 修复，`e9b3744` 来源加固与最终报告。[TASK-140 最终及全轮报告](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6236482278)、[TASK-124](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6235471387)、[TASK-102](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6235613775)。最后提交仅任务状态/链接与本 STATE 交接，以远端 HEAD 为准。

## 第 3 轮审查结论（Claude，2026-10-17）

| 任务 | 结论 | 要点 |
| --- | --- | --- |
| TASK-138 | accepted | 浏览器实测通过：一键标满后有未看斜纹、按钮不可用；看完才能确认；修改后完成被清除；`--segment` 校验正确。GZ-27 关闭，应修项转入 TASK-124 |
| TASK-136 | accepted | Claude 的 CUDA 对照：4K static 中位数 106.5–121.0 → 42.7 ms，降低 59.9% 与 64.7%；300/300 状态与峰值一致，in/out 最大差 1.8e-4 |
| TASK-139 | 部分通过 | 基础映射 v2、校准机制与 18 段新代理的时间轴通过。验证被源视频关键帧的周期脉冲干扰（GZ-29）：Claude 改用面积平均缩略图并屏蔽跨关键帧的步后复算，6 次录制的 A–B、E–B 全部满足原门槛。分段规则、台阶处的时间域与时钟抽查定义由 TASK-140 修订 |
| TASK-102 | changes-requested | 单人模式下，一帧的临时新轨迹会删掉已确认轨迹的桥接，后续帧变为 `no_head`（GZ-30）。另需在文档中说明临时头会进入 Gazelle、会增加 ID 数 |
| TASK-002 | accepted | Q-011 已解决：第 15 帧是否检出头姿取决于输入编码。用 2026-10-14 的验收转码，第 15 帧射线 (−0.902, +0.431)，旋转后 roll 变化 +19.9° 与 −19.3°。另发现射线角度在非正方形画面上变形（GZ-28），第 3 阶段特征提取前修复 |

同步复核的全部数字见 [evidence/2026-10-17-sync-validation-r3.md](evidence/2026-10-17-sync-validation-r3.md)。

Claude 实际运行的检查：

- 完整离线门 643 项；
- 标注工具的浏览器实测；
- TASK-136 的 CUDA 对照；
- Q-011 的 MediaPipe 与 CUDA 复跑；
- 18 段新代理的逐帧解码与跨机运动复算，分屏蔽与不屏蔽两种；
- 源视频关键帧间隔测量；
- 20260911 E 的分段推演与分段规则的合成检验；
- 两张事件条图的目视检查。

另有三份独立代码审查（只读子代理）。详见各任务文件 §3。

## 第 3 轮交接记录（Codex，2026-10-17）

- TASK-138 → TASK-136 → TASK-139 → TASK-102 → TASK-002 均已实施、提交并推送；TASK-102/002 在等待 TASK-139 CPU 批次时完成。各任务为 `ready-for-review`，不代表独立验收。最终相关代码离线门 **643 tests / 12.248s / 0 skip**；compileall、help、list-models、diff-check 通过。仅主线程 Inline Execution，无子代理。
- **用户授权与区域**：D18 已直接批准，见 Q-010；下方第 2 轮的“待决定/现在可以画区域”是历史说明，勿要求用户重做。用户已完成正式区域并批准唯一修正 `work_area.kind: target → cell`。TASK-138 保留全部顶点、名称和颜色，完成 4 targets + 1 cell 的 v2 导出；最终只读复核区域、完成标记、参考图和 classes 哈希均未变。
- **TASK-136**：6 次真实 300 帧 CUDA 对照，4K static 推理中位数 123.142→42.298 ms（降低 65.651%）；预测状态/峰坐标对照通过。**TASK-102**：四次真实 30 帧对照，A/B 首帧 no_head 均 1→0，provisional 显式记录；身份质量仍待独立审查。**TASK-002**：符号性质测试与转码旋转组通过；第 15 帧缺少 face pose、原图旋转组漏检，Q-011 未解决。
- **TASK-139**：40/40 v2 基础映射有效；六会话校准通过，20260911 E 的 MAD=0.101424 s 超过 0.08，最佳分段比=0.592274 未满足减半。完成 **18/21 新代理、297,855 帧**，视频/旁注/哈希/两套解码计数一致；1009 A 保留 9 个缺口步。新代理残差 **12/18 对通过**，时钟 **54/54 可评估、49/54 通过**；六份验证 JSON、18 张事件条图已生成。0821/0828 本机各门通过，其余四会话失败按原数值保留。详见 TASK-139 最终报告和 Q-012。
- **正式标注仍不能开始**：0911 三段代理及验证阻塞，七会话数据集预检明确失败；没有生成六会话替代集或 `roi_r2`，没有写正式 labels。旧代理和试用集原路径未覆盖/移动；新部分产物在 `gazelle_data\workdata\proxies_v2_pending`。完整替换与改名切换等协议判断后执行。
- 最终 guard 修复提交 `3242aed` 后，只读数值重放确认真实数据时间值不变；媒体保留 `d7431e0`/`bbcbc31` 原指纹，没有伪装为最终提交后重跑。12 个拟合全域误差保守上界 0.002502 ms，40 个端点重放最大误差 7.15e-7 s；说明见 TASK-139。
- 普通沙盒预检与授权 yun Git/GitHub 例外分别记录；`Gazelle-next` 使用、原 Gazelle 保留。真实 CPU/GPU/MediaPipe、缓存/网络、FFmpeg 活动详见各任务，不用 mocks 代替实测。未安装、修改环境、下载新资源或上传媒体/标注/权重/缓存/凭据，源目录只读；20261016 未纳入。旧数据与忽略文件保留。
- **Claude 接手**：先按稳定提交复跑与审查 A 级决定，处理 Q-012 的实际同步失败/分段与 OSD 定义，以及 Q-011 的真实样例问题；目视核对全部事件。TASK-101 继续 blocked，必须等 TASK-102 审查通过。`last_accepted` 保持 `b527287`，最终用户在独立 checkout 验收。
- 最终双语 PR 报告：[TASK-139 与全轮交接](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6233132174)。代理/验证批已退出（exit 1，实际验收失败如上），父进程已确认不存在；数值/文件核对均已结束。未留下本任务后台计算。交接时跟踪文件 clean（本 STATE 交接提交后），既有忽略文件未清理。

## 已结束轮次

第 1、2 轮的审查结论与交接记录原文已移到 [HISTORY.md](HISTORY.md)。

## 任务队列（阶段 2）

| 轮次 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| Codex 第 1 轮 | TASK-131 读取器：容器时间戳、严格递增、截断即失败 | accepted | 537 项离线测试；29 段各 600 帧无违规；AVI 失败与 300 帧 GPU smoke 均已实测 |
| Codex 第 1 轮 | TASK-132 作业数据清单与 AVI 无损重封装 | accepted | 40 文件清单；11/11 重封装校验通过；生产读取器 600 帧检查通过 |
| Codex 第 1 轮 | TASK-123 全局摄像机画面中的区域标记工具 | accepted（第 2 轮修复后） | 见 HISTORY.md 第 2 轮审查结论 |
| Codex 第 1 轮 | TASK-001 参数在 `--overwrite` 删除前校验 | accepted | 562 项最终离线门通过；static/json 两条旧结果保护回归通过 |
| Claude | 审查第 1 轮，试用区域标记工具 | 完成 | 见 HISTORY.md |
| 用户 | 用 TASK-123 的工具画出区域 | 完成（2026-10-17） | 4 个目标区域与 1 个工作区；`work_area` 的类型经用户批准改为工作区（cell） |
| Codex 第 2 轮 | TASK-137 项目环境切换到 `Gazelle-next`（仓库侧） | accepted | |
| Codex 第 2 轮 | TASK-123 修复必须修复 1 至 5 | accepted | |
| Codex 第 2 轮 | TASK-135 第 1 轮审查的后续加固 | accepted | 尾部时间比较的起始时间偏差转入 TASK-138 |
| Codex 第 2 轮 | TASK-133 画面时钟识别、时间映射与同步检验 | 部分通过 | 识别、锚点、身份核实通过；时间映射与同步检验由 TASK-139 取代 |
| Codex 第 2 轮 | TASK-134 5 Hz 同步代理视频 | accepted（生成机制） | 现有代理的时间轴不能用于正式数据集，由 TASK-139 重新生成 |
| Codex 第 2 轮 | TASK-121 多视角同步片段的区域标注工具（D12 r2） | changes-requested | 一次按键标满整段并自动完成（GZ-27），由 TASK-138 修复 |
| Claude | 审查第 2 轮，完整试标 pilot 片段 | 完成 | 见 HISTORY.md 与同步分析 |
| 用户 | 决定 D18：同步协议 r2 | 已批准（2026-10-17） | 见 Q-010 |
| Codex 第 3 轮 | TASK-138 标注与区域工具的后续修复 | accepted | 见「第 3 轮审查结论」；应修项转入 TASK-124 |
| Codex 第 3 轮 | TASK-136 Gazelle 输入预处理移到推理设备 | accepted | Claude 的 CUDA 对照中位数降低约 60% |
| Codex 第 3 轮 | TASK-139 同步协议 r2：以 B 为基准的画面内容校准 | 部分通过 | 基础映射 v2、校准机制、18 段新代理通过；余项由 TASK-140 完成 |
| Codex 第 3 轮 | TASK-102 新轨迹首帧立即确认（D2） | changes-requested | 必须修复 1 项（GZ-30），第 4 轮修复 |
| Codex 第 3 轮 | TASK-002 面部射线与 roll 符号对齐 | accepted | Q-011 已解决 |
| Claude | 审查第 3 轮 | 完成 | 见「第 3 轮审查结论」与第 3 轮同步验证复核 |
| Codex 第 4 轮 | TASK-140 同步协议 r2 的验证与分段修订 | ready-for-review | 同步 7/7 通过；0911 时钟 8/9、0903 第一切点无法细化，Q-014/Q-015 待决，未切换或生成数据集 |
| Codex 第 4 轮 | TASK-124 标注工具加固 | ready-for-review | 已推送；离线与临时副本浏览器自测通过，待独立审查 |
| Codex 第 4 轮 | TASK-102 第 2 轮修复 | ready-for-review | 桥接修复与回归通过；真实 smoke 计数预期差异见 Q-016 |
| Codex 第 4 轮 | TASK-101 人脸与姿态关联修正（D1） | blocked | 等 TASK-102 审查通过；GZ-01 |
| 待定 | 参考射线改为像素各向同性方向（GZ-28） | proposed | 第 3 阶段特征提取（TASK-141）之前；契约届时编写 |
| 用户 | 标注 26 段，约 2 小时 | 待前置 | 需 TASK-140 与 TASK-124 通过审查，并生成正式数据集 `roi_r2` |
| Claude | 阶段 2 验收：离线门、作业数据真实 smoke、同步精度、修复前后对比 | 未开始 | |

第 3 阶段（多摄像机注视区域推断）的设计已于 2026-10-15 获批（D13 至 D15），任务契约在阶段 2 验收时编写，见 [ROADMAP.md](ROADMAP.md)。
摄像机角色：前方为カメラ2（`cam_b`），右侧为カメラ1（`cam_a`），全局为設備カメラ（`cam_e`）；一律按物理编号取文件。

## 给 Codex 的说明

- **本轮开始**：按协作方案 §3.1 第 3 步，先提交 Claude 留下的文档改动（`Record coordinator updates`）并推送，再用 `gh pr edit 6 --body-file docs/collab/STAGE2_PR_BODY.md` 同步 PR 正文。
  - 新文件：
    - `HISTORY.md`：第 1、2 轮记录从本文件逐字移来；
    - `evidence/2026-10-17-sync-validation-r3.md`；
    - `tasks/TASK-124-annotation-hardening.md`；
    - `tasks/TASK-140-sync-validation-and-steps.md`。
  - 同时提交：
    - 本文件、ROADMAP、STAGE2_PR_BODY；
    - 问题登记表 §7 与 §8；
    - 同步分析 §7 的状态；
    - TASK-002、102、136、138、139 的 §3 审查结论与状态行。
- **本轮顺序**：TASK-140 → TASK-124 → TASK-102（第 2 轮修复），然后结束本轮。
  - TASK-140 有长时间 CPU 计算，等待期间可以做后两项，与第 3 轮的做法相同。
  - TASK-101 仍等 TASK-102 审查通过。
- **数据**：
  - `proxies_v2_pending` 中的 18 段新代理时间轴已通过审查。按 TASK-140 第 3 条判断是否保留，不要删除。
  - 旧的 21 段代理、试用集与时间映射保持原路径，只在 TASK-140 第 10 条的条件满足时改名备份。
  - 源目录的 `20261016` 不纳入研究集。
- **区域**：
  - 正式区域、完成标记、参考图与类别只读。用户批准的那一次修正已经完成，不扩展为其他修改。
  - 测试与试用一律用临时路径。
  - 不要创建正式 `labels.json`。
- **MediaPipe**：用户 2026-10-16 决定开发阶段接受遥测（GZ-23），可以照常运行 MediaPipe。
- **环境**：所有 Python 命令使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`。现有 `Gazelle` 环境作为回退保留，不要使用，也不要修改；不在任何环境中安装或卸载包。
- **问题处理按协作方案 §3.5 分级自主**：能自己解决的先解决并记录；设计层面的问题交 Claude，同时继续不受影响的工作；只有需要新授权、用户偏好或用户亲自操作时才问用户。硬边界不变。
- **GitHub 命令**：用户 2026-10-16 给予常设批准（协作方案 §7），本分支与 PR #6 的发布类命令可以直接在用户上下文 `yun` 中运行。
- 每个任务推送后，在 PR #6 发一条英中双语评论（协作方案 §4），包含 §3.5 规定的四个小节。
- 数据规则（协作方案 §5）：`E:\Gazelle_Workdata\` 只读；派生数据写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`；长时间 CPU 任务以低优先级运行；GPU 推理前检查空闲显存。
- 字节码：用 `-I` 运行 Python 时 `PYTHONPYCACHEPREFIX` 不生效；需要隔离时改用 `-X pycache_prefix=<仓库外的短路径>`。

## 给 Claude 的说明

- **第 4 轮当前补充（Codex）**：先读上方交接与 Q-014 至 Q-016。两个新数据集尚未生成，不能执行下方 manifest 验收；TASK-102 的原 smoke A 计数期望也需先澄清。下方保留第 3 轮制定的审查要求，不将其默认为已满足。
- `next_actor` 为 `claude` 时：按提交 SHA 审查 `last_accepted` 之后的任务，复跑离线门，核对真实检查的数字；逐项确认实施报告中的 A 级自主决定，处理 B 级问题（协作方案 §3.2）。
- 审查 TASK-140：
  - 在 20260911 的新代理上抽缩略图，用 `gazelle_runs\claude-review-r3\sync\analyze_sync_r3.py` 复算。该脚本按“X 相对 Y”的约定输出，含屏蔽与不屏蔽两种。
  - 与第 3 轮同步验证复核的表格对照 Codex 的新验证结果。
  - 核对 v3 与 v2 的差值，以及是否保留代理。
  - 目视核对全部事件条图，含切点事件；第 3 轮只看了 2 张。
  - 检查两个数据集的 manifest，确认排除了 `sync_uncertain` 片段。
  - 通过后在「给用户的说明」写明正式标注的启动方法。
- 审查 TASK-124：在浏览器中实测完成条件只认已保存的已看范围，以及播放时的写盘频率。
- 审查 TASK-102 的修复：用 GZ-30 的场景与 smoke A（30 帧）确认 `tracked_only` 行恢复。
- GZ-28（射线的像素各向同性）：在第 3 阶段特征提取之前写契约。
- 在阶段节点更新 `docs/collab/STAGE2_PR_BODY.md` 的状态表，由 Codex 同步到 GitHub。
- 待办：用 `bbec056` 的导出快照在一段同步代理上做修复前基线运行，作为 TASK-101、TASK-102 的对照。
- 字节码：Claude 自己运行 Python 时也用 `-X pycache_prefix`，不要用 `-I` 配合环境变量。

## 给用户的说明

**2026-10-18 当前交接（Codex）**：第 4 轮已执行并交回 Claude，请对 Claude 说“继续”。正式标注仍未就绪；没有新的用户决策请求，区域无需重画。下方是第 3 轮交接时的说明，其中“对 Codex 说继续”的步骤已完成。

第 3 轮审查已完成：

- TASK-138、TASK-136、TASK-002 通过。
- TASK-139 部分通过：新代理的时间轴是准的，但验证方法要修订，20260911 还要补齐。
- TASK-102 退回一项修复。

详见「第 3 轮审查结论」。

- **下一步**：对 Codex 说“继续”。第 4 轮顺序是 TASK-140 → TASK-124 → TASK-102 修复。
  - TASK-140 要补齐 20260911、用修订后的方法重新验证 7 次录制，全部通过后生成正式数据集。
  - 后台 CPU 约 2 小时；如果有录制需要重新生成代理，每次录制再加约 1 小时。
- **正式标注暂不开始**：要等 TASK-140 与 TASK-124 都通过 Claude 的审查，并生成正式数据集 `roi_r2`。届时这里会写明启动方法。
- **源目录的 `20261016`**：目前不纳入研究集。若希望纳入，请告诉 Claude。
- **之后**：正式数据集生成后，标注 26 个一分钟片段，约 2 小时，可分多次。
- **可选**：若某名作业者出现在多个日期，提供每个日期的匿名作业者编号（例如 W1、W2），即可做严格的按作业者留一评估。
- **已记录的决定**：
  - D18（2026-10-17）：同步协议 r2。以前方摄像机 B 的画面时钟为基准，右侧与全局摄像机用画面运动校准；D13 的时间轴相应改为“以 B 为基准、内容校准后的 5 Hz”。
  - 正式区域（2026-10-17）：你画出 4 个目标区域与 1 个工作区，并批准 `work_area` 的类型修正（已向 Claude 直接确认，Q-013）。
  - D16、D17（2026-10-17）：项目使用 `Gazelle-next`，激活命令为 `conda activate Gazelle-next`，现有 `Gazelle` 保留作回退；TASK-136 已完成。
  - MediaPipe 遥测（2026-10-16）：开发阶段接受，研究完成后再做安全处理。
  - 分级自主与常设批准（2026-10-16）。
  - 2026-10-15：摄像机角色、区域标记方式、作业者与机位、D4、D12 r2、D13 至 D15。

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
| Q-010 | C | Claude | D18：采用同步协议 r2（以前方摄像机 B 为基准，A 与 E 用画面运动校准偏移与漂移）；D13 的时间轴定义随之改为“以 B 的画面时钟为基准、内容校准后的 5 Hz” | `evidence/2026-10-17-sync-analysis.md` §7；`tasks/TASK-139-content-calibrated-sync.md` | 已决定（2026-10-17）：用户直接批准，原话为“D18 批准，按你的推荐进行。”，由 Codex 收讫。Claude 已归档到 ROADMAP、同步分析 §7 与「给用户的说明」 |
| Q-011 | B | Codex | TASK-002：原始 GIF 与转码视频第 15 帧均无 face head-pose；原图旋转组漏检，转码旋转组 roll 与方向检查通过 | TASK-002 §2；外部 task-002/comparison.json、extra-comparison.json | 已解决（2026-10-17）。Claude 复跑：第 15 帧能否检出头姿取决于输入编码，不是代码缺陷。用 2026-10-14 的验收转码，第 15 帧射线 (−0.902, +0.431)，旋转后 roll 变化 +19.9° 与 −19.3°。验收输入与旋转判据按 TASK-002 §3 澄清，阈值未降低 |
| Q-012 | B | Codex | TASK-139 协议边界及真实失败：MAD 可掩盖少数台阶；正台阶可能无解；B 时间轴与各自 OSD 容差冲突；新代理六对残差超限 | TASK-139 §2 最终报告；外部 task-139/protocol-edge-cases.json、0911-split-diagnostics.json、final-output-audit.json | 0911 E：53 窗、MAD=0.101424>0.08，最佳分段比=0.592274；同样本互相关与参考一致。新代理 0903 E-B/A-E、0925 A-B/A-E、1009 A-B/E-B 残差失败；1002 A 三项 +2.8/+2/+2 s、1009 A 两项 +1.8/+1.4 s 的 OSD 超限。18/21 代理、12/18 残差对、49/54 时钟通过，七会话数据集阻塞。未改门槛、删窗口或会话；推荐 Claude 先复核源帧/固定产物再修订契约，尚未暂定实施（以上为 Codex 报告的原状态）。已决定（2026-10-17）：（1）分段：增加尾部条件，总是尝试切分，按 L1 选切点；（2）台阶处：在各摄像机自身基础时间上显式计算最终时间，规定重叠与缺口，并标记 `sync_uncertain`；（3）时钟抽查：与该摄像机自己的显示时钟比较。六对残差失败来自测量方法（GZ-29），不是代理时间轴。见第 3 轮同步验证复核 §6 与 TASK-140 |
| Q-013 | C | Claude | 确认：正式区域中 `work_area` 的类型由“目标”改为“工作区”（cell），是用户批准的唯一修正。批准由 Codex 转述，Claude 只读核对，确认这是唯一的语义变化 | TASK-138 §2、§3 | 已确认（2026-10-17）：用户直接回复 Claude“是的，我确认” |
| Q-014 | B | Codex | 0903 E 第一切点 23 个细化短窗均无效，粗切点 b=961.247810 s 的 ±10 s 定位无法验证；切点条图为空工位 | TASK-140 §2；外部 task-140/refinement-reference.json、proposed-exclusion-impact.json | 待 Claude：参考算法复算一致。推荐按相邻有效长窗界限（必要时加半窗裕量）保守扩大不确定区间后排除抽样；固定种子四段起点不变。未暂定采用，未改正式数据 |
| Q-015 | B | Codex | 0911 时钟只有 8/9 可评估；E 固定 k=15804 及原定四个邻帧的代理 OCR 均缺失。同源精确 PTS 可读，d=+0.023192 s | TASK-140 §2；外部 task-140/clock-diagnostic.json/.png/.log | 待 Claude：推荐决定是否允许带来源的同一源帧/PTS 补读；当前原验证仍失败，未改 OCR、阈值或固定样本。切换与数据集暂停 |
| Q-016 | B | Codex | TASK-102 修复后真实 A 的旧三行 tracked_only 未恢复，因对应帧现在有合法 provisional 观测；契约 P0/P1 回归与真实仲裁前桥接诊断通过 | TASK-102 §2 第 2 轮；外部 task-102-r2/smoke.py、bridge_diagnostic.py 及日志 | 待 Claude：推荐按 P0/P1 契约及仲裁前证据验收桥接保护，澄清 smoke A 计数预期；原包装断言失败保留，未改 selector/验收标准，TASK-101 仍 blocked |

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
| Claude 第 2 轮审查：离线门、TASK-137 复核、两个工具的浏览器实测与 pilot 完整试标、21 段代理跨机运动分析；两份独立代码审查 | 已实际运行（Claude）；结论见 HISTORY.md | 各任务文件 §3；`evidence/2026-10-17-sync-analysis.md` |
| 用户决定 D18（同步协议 r2）；用户画出正式区域（4 个目标区域与 1 个工作区） | 已确认（2026-10-17）；`work_area` 类型修正由用户直接向 Claude 确认（Q-013） | Q-010、Q-013；TASK-138 §2、§3 |
| Codex 第 3 轮：TASK-138、136、139、102、002 实现与真实运行 | 已实际运行（Codex） | 各任务文件 §2 |
| Claude 第 3 轮审查：离线门、标注工具浏览器实测、TASK-136 CUDA 对照、Q-011 复跑、18 段新代理跨机运动复算（屏蔽与不屏蔽关键帧）、关键帧间隔、分段规则推演；三份独立代码审查 | 已实际运行（Claude）；TASK-138、136、002 accepted，TASK-139 部分通过，TASK-102 changes-requested | 各任务文件 §3；`evidence/2026-10-17-sync-validation-r3.md` |
| 第 1、2 轮的审查结论与交接记录移到 HISTORY.md | 已整理（协调者），逐字移动并经脚本核对 | `HISTORY.md` |

## 注意

- 模型缓存 `models/`、运行输出、验证集与作业数据的派生物都不在 Git 中，也不上传到任何服务。
- overlay 文件为 LF，checkout 其余为 CRLF；`git diff --check` 只提示不报错，提交时 Git 统一为 LF。
- 「复核确认」结论来自同产品只读代理，不等于独立验收。
