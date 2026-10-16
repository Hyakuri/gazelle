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
| current_task | `docs/collab/tasks/TASK-001-overwrite-safe-validation.md` |
| after_current | 完成本轮后把 `next_actor` 改为 `claude`，释放 `writer` |
| last_pushed | `4220c98fd88d582bfc83901947e7176a710b5bbd`（TASK-123 实现；报告与 STATE 记录随后提交） |
| last_accepted | `bbec056`（迁移验收基线，Gate A/B/C 通过） |
| 更新 | 2026-10-16，Claude：TASK-131 契约 r3；分级自主；常设批准 |

## 任务队列（阶段 2）

| 轮次 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| Codex 第 1 轮 | TASK-131 读取器：容器时间戳、严格递增、截断即失败 | ready-for-review | 537 项离线测试；29 段各 600 帧无违规；AVI 失败与 300 帧 GPU smoke 均已实测 |
| Codex 第 1 轮 | TASK-132 作业数据清单与 AVI 无损重封装 | ready-for-review | 40 文件清单；11/11 重封装校验通过；生产读取器 600 帧检查通过 |
| Codex 第 1 轮 | TASK-123 全局摄像机画面中的区域标记工具 | ready-for-review | 84 候选帧和本机页面通过；正式区域不存在；Claude 四区域试用待验收 |
| Codex 第 1 轮 | TASK-001 参数在 `--overwrite` 删除前校验 | ready | GZ-04 |
| Claude | 审查第 1 轮，试用区域标记工具 | 未开始 | |
| 用户 | 用 TASK-123 的工具画出区域，约 10 分钟 | 待前置 | 可与第 2 轮并行 |
| Codex 第 2 轮 | TASK-133 画面时钟识别、时间映射与同步检验 | ready | 依赖 TASK-132 |
| Codex 第 2 轮 | TASK-134 5 Hz 同步代理视频 | ready | 依赖 TASK-133 |
| Codex 第 2 轮 | TASK-121 多视角同步片段的区域标注工具（D12 r2） | ready | 依赖 TASK-134 与用户的区域文件 |
| Claude | 审查第 2 轮，完整试标 pilot 片段 | 未开始 | |
| 用户 | 标注 26 段，约 2 小时 | 待前置 | 可与第 3 轮并行 |
| Codex 第 3 轮 | TASK-102 新轨迹首帧立即确认（D2） | ready | GZ-03 |
| Codex 第 3 轮 | TASK-002 面部射线与 roll 符号对齐 | ready | GZ-02 |
| Codex 第 3 轮 | TASK-101 人脸与姿态关联修正（D1） | blocked | 等 TASK-102 审查通过；GZ-01 |
| Claude | 阶段 2 验收：离线门、作业数据真实 smoke、同步精度、修复前后对比 | 未开始 | |

第 3 阶段（多摄像机注视区域推断）的设计已于 2026-10-15 获批（D13 至 D15），任务契约在阶段 2 验收时编写，见 [ROADMAP.md](ROADMAP.md)。
摄像机角色：前方为カメラ2（`cam_b`），右侧为カメラ1（`cam_a`），全局为設備カメラ（`cam_e`）；一律按物理编号取文件。

## 给 Codex 的说明

- **本轮开始**：按协作方案 §3.1 第 3 步，先提交 Claude 留下的文档改动（`Record coordinator updates`）并推送；`docs/collab/STAGE2_PR_BODY.md` 没有变化时不需要同步 PR 正文。
- **TASK-131 已澄清，可以直接实施**：契约 r3 把逐帧算法第 4 步改为 `p + max(1.0, 1000 / fps)`，不限制帧率范围，并新增 5 条边界用例；见任务文件「审查结论」。
- **问题处理按协作方案 §3.5 分级自主**（用户 2026-10-16 决定）：能自己解决的先解决，在实施报告中记录；设计层面的问题交 Claude，同时继续不受影响的工作与后续任务；只有需要新授权、用户偏好或用户亲自操作时才问用户。硬边界不变。
- **GitHub 命令**：用户 2026-10-16 给予常设批准（协作方案 §7）。本分支与 PR #6 的发布类命令可以直接在用户上下文 `yun` 中运行，不必每轮重新请求；范围以外的操作仍需逐项授权。
- 按 `current_task` 执行，完成后按 `after_current` 继续。
- 每个任务推送后，在 PR #6 发一条英中双语评论（协作方案 §4），包含 §3.5 规定的四个小节。
- 数据规则（协作方案 §5）：`E:\Gazelle_Workdata\` 只读；派生数据写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`；长时间 CPU 任务以低优先级运行；GPU 推理前检查空闲显存。
- 在 TASK-131 合入前，不要用 CLI 处理作业数据的原始 AVI 或 MP4，契约中指定的检查除外。
- 历史记录：2026-10-16 环境预检通过；沙盒用户的 `gh` 没有凭据，GitHub 命令在用户上下文运行；首次推送与 draft PR #6 已完成。细节见 TASK-131 实施报告。

## 给 Claude 的说明

- `next_actor` 为 `claude` 时：按提交 SHA 审查 `last_accepted` 之后的任务，复跑离线门，核对真实检查的数字；逐项确认实施报告中的 A 级自主决定，处理 B 级问题（协作方案 §3.2）。
- 审查 TASK-131 时，独立复跑 29 个 MP4 分段前 600 帧的时间戳检查与原始 AVI 的截断检查。
- 审查 TASK-123 时，用 `--regions-path` 指向临时文件，在内置浏览器画出 4 个默认区域并核对参考图。通过后在「给用户的说明」写明区域标记的启动命令。
- 审查 TASK-121 时，用 `--labels-path` 指向临时文件，在内置浏览器完整试标 pilot 片段。通过后在「给用户的说明」写明标注启动方法。
- 在阶段节点更新 `docs/collab/STAGE2_PR_BODY.md` 的状态表，由 Codex 同步到 GitHub。
- 待办：TASK-134 完成后，用 `bbec056` 的导出快照在一段同步代理上做修复前基线运行，作为 TASK-101、TASK-102 的对照。

## 给用户的说明

Codex 已完成环境预检、首次推送与 draft PR [#6](https://github.com/Hyakuri/gazelle/pull/6)。下一步请对 Codex 说“继续”：它会先提交本次协作文件更新，再实施 TASK-131，之后按顺序做 TASK-132、TASK-123、TASK-001。

- **已记录你 2026-10-16 的决定**：Codex 分级自主（协作方案 §3.5）；本分支与 PR #6 的发布类 Git/GitHub 命令常设批准（协作方案 §7）。
- **已记录你 2026-10-15 的决定**：カメラ2 为前方、カメラ1 为右侧、設備カメラ为全局；区域由你在全局摄像机画面上标记；同一日期为同一作业者，机位固定；批准 D4、D12 r2 与 D13 至 D15。
- **接下来轮到你的两件事**：
  1. 第 1 轮审查通过后，用区域标记工具画出取货台、作业台、放置区、工作区，约 10 分钟。启动命令届时写在这里。
  2. 第 2 轮审查通过后，标注 26 个一分钟片段，约 2 小时，可分多次。
- **可选**：若某名作业者出现在多个日期，提供每个日期的匿名作业者编号（例如 W1、W2），即可做严格的按作业者留一评估；不提供时按日期评估。
- **过渡期提醒**：TASK-131、TASK-132 完成前，不要用当前代码直接处理 `E:\Gazelle_Workdata` 的视频。AVI 只会处理 1 帧却显示成功，部分 MP4 会在第 3 帧报错退出。

## 待决问题

两方都可以新增；处理方式见协作方案 §3.5。

| 编号 | 级别 | 提出者 | 内容 | 位置 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Q-001 | B | Codex | TASK-131 第 4 步在 2000 FPS 时取整后不递增，违反 R1 | TASK-131 实施报告与审查结论 | 已解决：契约 r3 |

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

## 注意

- 模型缓存 `models/`、运行输出、验证集与作业数据的派生物都不在 Git 中，也不上传到任何服务。
- overlay 文件为 LF，checkout 其余为 CRLF；`git diff --check` 只提示不报错，提交时 Git 统一为 LF。
- 「复核确认」结论来自同产品只读代理，不等于独立验收。
