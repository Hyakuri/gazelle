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
| current_task | `docs/collab/tasks/TASK-134-synchronized-proxies.md` |
| after_current | `docs/collab/tasks/TASK-121-validation-annotation-toolkit.md`，然后结束本轮并把 `next_actor` 改为 `claude` |
| environment | `Gazelle-next`：`C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`（用户 2026-10-17 决定 D16）。现有 `Gazelle` 作为回退保留，不改动 |
| last_pushed | `5b26155ec8e3ed4a612a68150e5b6d003b302f50`（TASK-133 实现；其后为报告与 STATE 推进，实时 HEAD 以 Git 为准） |
| last_accepted | `e7244d0`（2026-10-16 第 1 轮审查：TASK-131、TASK-132 通过。TASK-001 也已通过，但其提交位于 TASK-123 之后，待 TASK-123 修复通过后一并计入） |
| 更新 | 2026-10-17，Claude：环境评估完成；用户决定 D16（尽早切换，项目改用 `Gazelle-next`）与 D17（同意 TASK-136）。第 2 轮交 Codex，第一项为 TASK-137 |

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

## 任务队列（阶段 2）

| 轮次 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| Codex 第 1 轮 | TASK-131 读取器：容器时间戳、严格递增、截断即失败 | accepted | 537 项离线测试；29 段各 600 帧无违规；AVI 失败与 300 帧 GPU smoke 均已实测 |
| Codex 第 1 轮 | TASK-132 作业数据清单与 AVI 无损重封装 | accepted | 40 文件清单；11/11 重封装校验通过；生产读取器 600 帧检查通过 |
| Codex 第 1 轮 | TASK-123 全局摄像机画面中的区域标记工具 | changes-requested | 84 候选帧和本机页面通过；正式区域不存在；Claude 四区域试用待验收 |
| Codex 第 1 轮 | TASK-001 参数在 `--overwrite` 删除前校验 | accepted | 562 项最终离线门通过；static/json 两条旧结果保护回归通过 |
| Claude | 审查第 1 轮，试用区域标记工具 | 完成 | 见「第 1 轮审查结论」 |
| 用户 | 用 TASK-123 的工具画出区域，约 10 分钟 | 待前置 | Codex 在 PR #6 报告 TASK-123 修复后即可进行 |
| Codex 第 2 轮 | TASK-137 项目环境切换到 `Gazelle-next`（仓库侧） | ready-for-review | 563 项离线门；三组 300 帧 smoke；前两组非计时字段与对照完全一致；B 级依赖事实差异见报告 |
| Codex 第 2 轮 | TASK-123 修复必须修复 1 至 5 | ready-for-review | 569 项离线门；84 候选帧；合成浏览器试画、拖动、顶点删除/撤销、导出通过；用户可开始正式画区域 |
| Codex 第 2 轮 | TASK-135 第 1 轮审查的后续加固 | ready-for-review | 572 项离线门；11/11 输出在更严格尾部校验下通过且未重写；r4 漂移与文档已修复 |
| Codex 第 2 轮 | TASK-133 画面时钟识别、时间映射与同步检验 | ready-for-review | 40/40 映射、12/12 参考读数；605 项工作树离线门通过；运动同步 9/42 通过，33 项按 Q-007 交 Claude |
| Codex 第 2 轮 | TASK-134 5 Hz 同步代理视频 | ready | 依赖 TASK-133 |
| Codex 第 2 轮 | TASK-121 多视角同步片段的区域标注工具（D12 r2） | ready | 依赖 TASK-134 与用户的区域文件 |
| Claude | 审查第 2 轮，完整试标 pilot 片段 | 未开始 | |
| 用户 | 标注 26 段，约 2 小时 | 待前置 | 可与第 3 轮并行 |
| Codex 第 3 轮 | TASK-136 Gazelle 输入预处理移到推理设备 | ready | GZ-25；用户 2026-10-17 同意 D17；本轮第一项 |
| Codex 第 3 轮 | TASK-102 新轨迹首帧立即确认（D2） | ready | GZ-03 |
| Codex 第 3 轮 | TASK-002 面部射线与 roll 符号对齐 | ready | GZ-02 |
| Codex 第 3 轮 | TASK-101 人脸与姿态关联修正（D1） | blocked | 等 TASK-102 审查通过；GZ-01 |
| Claude | 阶段 2 验收：离线门、作业数据真实 smoke、同步精度、修复前后对比 | 未开始 | |

第 3 阶段（多摄像机注视区域推断）的设计已于 2026-10-15 获批（D13 至 D15），任务契约在阶段 2 验收时编写，见 [ROADMAP.md](ROADMAP.md)。
摄像机角色：前方为カメラ2（`cam_b`），右侧为カメラ1（`cam_a`），全局为設備カメラ（`cam_e`）；一律按物理编号取文件。

## 给 Codex 的说明

- **本轮开始**：按协作方案 §3.1 第 3 步，先提交 Claude 留下的文档改动（`Record coordinator updates`）并推送。`docs/collab/STAGE2_PR_BODY.md` 已更新，用 `gh pr edit 6 --body-file docs/collab/STAGE2_PR_BODY.md` 同步 PR 正文。
- **本轮顺序**：TASK-137 → TASK-123 修复 → TASK-135 → TASK-133 → TASK-134 → TASK-121，然后结束本轮。
- **TASK-123 修复**：按任务文件 §3「必须修复」1 至 5 实施，建议修复项尽量一并处理。修复推送后，在 PR #6 的评论里单独写一句“区域工具已修复，用户可以开始画区域”，让用户知道何时可以开始。
- **MediaPipe**：用户 2026-10-16 决定开发阶段接受遥测（GZ-23），可以照常运行 MediaPipe。
- **环境（2026-10-17 起）**：所有 Python 命令改用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，包括离线门、测试与真实运行。
  - 现有 `Gazelle` 环境作为回退保留，不要使用，也不要修改。
  - 不在任何环境中安装或卸载包。
  - 任务契约里尚未开始的部分已改为新路径。已验收任务的报告中出现的旧路径是历史记录，不要照着运行。
  - 评估记录见 `evidence/2026-10-17-env-next-evaluation.md`。
  - 预检的解释器一项也按新路径检查（协作方案 §5）。
- **TASK-137 先做**：仓库侧的切换，包括 `environment.yml`、`environment_py311.yml`、AGENTS.md 中的环境句子、四份用户文档与 `tests/test_usage_docs.py`。在它提交之前，AGENTS.md 中仍写着 `Gazelle`；本说明优先，以用户 2026-10-17 的决定为准。
- **新文件**：本次提交的 Claude 文档改动中包含 `evidence/2026-10-17-env-next-evaluation.md`、`tasks/TASK-136-gazelle-device-preprocessing.md` 与 `tasks/TASK-137-switch-to-gazelle-next.md`。TASK-136 已为 ready，排在第 3 轮开头，本轮不要实施。
- **问题处理按协作方案 §3.5 分级自主**：能自己解决的先解决并记录；设计层面的问题交 Claude，同时继续不受影响的工作；只有需要新授权、用户偏好或用户亲自操作时才问用户。硬边界不变。
- **GitHub 命令**：用户 2026-10-16 给予常设批准（协作方案 §7），本分支与 PR #6 的发布类命令可以直接在用户上下文 `yun` 中运行。
- 每个任务推送后，在 PR #6 发一条英中双语评论（协作方案 §4），包含 §3.5 规定的四个小节。
- 数据规则（协作方案 §5）：`E:\Gazelle_Workdata\` 只读；派生数据写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`；长时间 CPU 任务以低优先级运行；GPU 推理前检查空闲显存。
- 字节码：用 `-I` 运行 Python 时 `PYTHONPYCACHEPREFIX` 不生效；需要隔离时改用 `-X pycache_prefix=<仓库外的短路径>`。

## 给 Claude 的说明

- `next_actor` 为 `claude` 时：按提交 SHA 审查 `last_accepted` 之后的任务，复跑离线门，核对真实检查的数字；逐项确认实施报告中的 A 级自主决定，处理 B 级问题（协作方案 §3.2）。
- 复核 TASK-123：在内置浏览器中按指南顺序（工作区最后画）画区域，确认能从画面选中内部区域并拖动顶点、双击能闭合、导出的参考图显示所有区域、完成标记与类别约束生效。通过后把 TASK-001 与 TASK-123 一并计入 `last_accepted`。
- 审查 TASK-135：r4 表格与漂移回归、加强后的尾部检查、四份文档的独立小节。
- 审查 TASK-121 时，用 `--labels-path` 指向临时文件，在内置浏览器完整试标 pilot 片段。通过后在「给用户的说明」写明标注启动方法。
- 在阶段节点更新 `docs/collab/STAGE2_PR_BODY.md` 的状态表，由 Codex 同步到 GitHub。
- 待办：用 `bbec056` 的导出快照在一段同步代理上做修复前基线运行，作为 TASK-101、TASK-102 的对照。
- 字节码：Claude 自己运行 Python 时也用 `-X pycache_prefix`，不要用 `-I` 配合环境变量。

## 给用户的说明

第 1 轮审查已完成：TASK-131、TASK-132、TASK-001 通过；TASK-123 退回修改，Codex 本轮第一项就会修复。下一步请对 Codex 说“继续”。

- **已记录你 2026-10-17 的决定：环境切换（D16）与 TASK-136（D17）。**
  - 项目从现在起使用 `Gazelle-next`（Python 3.14、PyTorch 2.14、MediaPipe 1.1.1 等），激活命令为 `conda activate Gazelle-next`。
  - 现有 `Gazelle` 原样保留作回退。
  - 仓库侧的切换由 Codex 在第 2 轮第一项 TASK-137 完成；TASK-136 排在第 3 轮开头。
  - 评估结论：输出与原环境等价；4K 输入下单次调用约慢 20%，TASK-136 完成后可快约 2 倍。见 `evidence/2026-10-17-env-next-evaluation.md`。
- **下一步**：对 Codex 说“继续”。
- **已记录你 2026-10-16 的决定：MediaPipe 遥测（GZ-23）。** 开发阶段接受 `mediapipe` 发送使用遥测；研究完成后再做安全方面的处理。Codex 与 Claude 可以照常运行 MediaPipe。
- **画区域**：等 Codex 在 PR #6 报告“区域工具已修复”后再开始，约 10 分钟。在仓库根目录运行：

  ```powershell
  C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe -m tools.validation.roi_server --candidates C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\roi\candidates.json --annotator yun
  ```

  然后用浏览器打开终端显示的本机地址，按 `tools/validation/ROI_GUIDE_CN.md` 操作，画完后点击“导出参考图与类别”。
- **之后**：第 2 轮审查通过后，标注 26 个一分钟片段，约 2 小时，可分多次。
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
| Q-006 | B | Codex | TASK-137 与环境评估称 pydeprecate/defusedxml 不再需要，但实际仍是 trackers/supervision 的必需依赖 | TASK-137 实施报告 | 已暂定按实际元数据编写用户文档，移除显式 pin 而不卸载；请 Claude 修正契约/评估事实，不阻塞后续任务 |
| Q-007 | B | Codex | TASK-133 全部 7 会话/21 窗口已检查，运动同步仅 9/42 对比通过；画面时钟一致不等于物理运动同步 | TASK-133 实施报告（含 40 文件与全部窗口统计） | 保留 33 项失败，不修正时钟或放宽阈值；建议逐事件人工核对后决定校准协议。TASK-134 继续按画面时钟生成可重建代理，物理同步结论待 Claude |
| Q-008 | B | Codex | TASK-134 固定连续网格与“完全落在重叠时段”存在冲突：20260903 共同覆盖有 0.079/0.134 秒内部缺口 | TASK-134 实施报告 | 暂定按 §3.5：默认拒绝多区间，显式 `--allow-internal-gaps` 保留总体起止间的固定网格、完整记录覆盖缺口，并沿用最近帧与半步长缺口标记；不删区间、不拼接压缩时钟。输出可重建，待 Claude 确认 |

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

## 注意

- 模型缓存 `models/`、运行输出、验证集与作业数据的派生物都不在 Git 中，也不上传到任何服务。
- overlay 文件为 LF，checkout 其余为 CRLF；`git diff --check` 只提示不报错，提交时 Git 统一为 LF。
- 「复核确认」结论来自同产品只读代理，不等于独立验收。
