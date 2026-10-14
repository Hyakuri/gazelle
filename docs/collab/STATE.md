# 协同状态（唯一入口）

Codex 与 Claude 每次开始工作先读本文件，再按控制块行事。字段归属与循环步骤见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md) §3。

## 控制块

| 字段 | 当前值 |
| --- | --- |
| stage | 阶段 2：正确性与安全修复 |
| branch | `feature/stage2-correctness`（基于 PR #5 head `bbec056`） |
| writer | none |
| next_actor | codex |
| current_task | `docs/collab/tasks/TASK-001-overwrite-safe-validation.md` |
| after_current | `docs/collab/tasks/TASK-102-spawn-frame-confirmation.md`，然后 `docs/collab/tasks/TASK-002-face-ray-sign-alignment.md`，然后停止并把 `next_actor` 改为 `claude` |
| last_pushed | 尚无任务提交（阶段建立提交见 `git log`） |
| last_accepted | `bbec056`（迁移验收基线，Gate A/B/C 通过） |
| 更新 | 2026-10-15，Claude |

## 任务队列（阶段 2）

| 顺序 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | TASK-001 参数在 `--overwrite` 删除前校验 | ready | GZ-04 |
| 2 | TASK-102 新轨迹首帧立即确认（D2） | ready | GZ-03 |
| 3 | TASK-002 面部射线与 roll 符号对齐规范 | ready | GZ-02 |
| 4 | TASK-101 人脸与姿态关联修正（D1） | blocked | 等 TASK-102 审查通过；GZ-01 |
| 5 | 阶段 2 验收 | 未开始 | Claude 跑离线门与真实 smoke 矩阵 |

第 3 阶段候选（契约待写）：TASK-003 打包修正、TASK-004 运行时边界加固、TASK-005 测试加固、TASK-006 文档同步、TASK-007 研究脚本加固、TASK-008 验收脚本与 CLI 易用性。见 [ROADMAP.md](ROADMAP.md)。

## 给 Codex 的说明

- 按 `current_task` 执行，完成后按 `after_current` 依次继续，最后把 `next_actor` 改为 `claude`。
- 本轮首次提交前，工作区里有 Claude 留下的文档改动时，先按协作方案 §3.1 第 3 步单独提交。
- 任一任务的离线门失败且无法在任务范围内修复时，停止后续任务，在实施报告写明阻塞，把 `next_actor` 改为 `claude`。

## 给 Claude 的说明

- `next_actor` 为 `claude` 时：按提交 SHA 审查 `last_accepted` 之后的任务，复跑离线门；TASK-102 与 TASK-002 需要真实 smoke 复核。
- TASK-102 通过后，把 TASK-101 改为 ready 并放入 `current_task`。

## 给用户的说明

当前不需要你操作。等待你决定的事项（不阻塞上面的任务）：

1. D10 保守门控是否按目标场景重新设计（见 `PROJECT_GOALS_CN.md` 第 2、3 节）。
2. D12 能否从 sample1、sample2 标注 200 到 300 帧作为验证集。
3. 是否允许在阶段验收时用你独立目录中的 sample1、sample2 做只读输入的真实 smoke。
4. 是否为阶段分支开 draft PR，用来在 GitHub 页面汇总报告。
5. PR #2 至 #5 的堆叠链何时、以何种方式合并到 `main`。
6. `PROJECT_GOALS_CN.md` 第 4 节的问题 Q1 至 Q6。

## 已完成

| 事项 | 状态标签 | 证据 |
| --- | --- | --- |
| 交接包恢复、overlay 哈希核对（Gate A） | 已实际运行 | `evidence/2026-10-14-destination-acceptance.md` |
| 模型缓存迁移，212 文件 SHA-256 一致 | 已实际运行 | `_handoff_archive\models-cache-transfer-20261014.json`（仓库外） |
| 离线门 531 测试通过（Gate B） | 已实际运行 | 同上 |
| 真实 smoke：prepare-only、图像 3 种、视频 2 种（Gate C） | 已实际运行 | 同上；产物在 `_handoff_archive\smoke-20261014\`（仓库外） |
| 全库只读分析：104 个问题，87 确认，17 驳回 | 已满足本轮验收（协调者自审） | `analysis/` |
| 项目目标重新确认，基于真实视频历史输出的统计 | 已实际运行（只读统计） | `PROJECT_GOALS_CN.md` |
| D1、D2 设计规范与任务契约 | 已提出，方向已获用户批准 | `../superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md` |

## 注意

- 模型缓存 `models/` 与所有输出都不在 Git 中；真实 smoke 输出写到 `%TEMP%` 下的任务目录。
- overlay 文件为 LF，checkout 其余为 CRLF；`git diff --check` 只提示不报错，提交时 Git 统一为 LF。
- 「复核确认」结论来自同产品只读代理，不等于独立验收。
