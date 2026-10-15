# 协同状态（唯一入口）

Codex 与 Claude 每次开始工作先读本文件，再按控制块行事。字段归属与循环步骤见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md) §3。

## 控制块

| 字段 | 当前值 |
| --- | --- |
| stage | 阶段 2：作业数据可用、多机同步、正确性修复，建立区域标注 |
| branch | `feature/stage2-correctness`（基于 PR #5 head `bbec056`） |
| pr | 待 Codex 创建（见「给 Codex 的说明」第 1 条）；正文来源 `docs/collab/STAGE2_PR_BODY.md` |
| writer | none |
| next_actor | codex |
| current_task | `docs/collab/tasks/TASK-131-video-reader-timestamps-and-truncation.md` |
| after_current | `docs/collab/tasks/TASK-132-workdata-inventory-and-avi-remux.md`，然后 `docs/collab/tasks/TASK-001-overwrite-safe-validation.md`，然后停止并把 `next_actor` 改为 `claude` |
| last_pushed | 尚未推送。本地有 6 个阶段提交，最后一个的主题是 `Prepare the stage draft PR and collaboration state` |
| last_accepted | `bbec056`（迁移验收基线，Gate A/B/C 通过） |
| 更新 | 2026-10-15，Claude |

## 任务队列（阶段 2）

| 轮次 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| Codex 第 1 轮 | TASK-131 读取器：容器时间戳、严格递增、截断即失败 | ready | GZ-07、GZ-21，P0 |
| Codex 第 1 轮 | TASK-132 作业数据清单与 AVI 无损重封装 | ready | 数据 P0、GZ-22 |
| Codex 第 1 轮 | TASK-001 参数在 `--overwrite` 删除前校验 | ready | GZ-04 |
| Claude | 审查第 1 轮 | 未开始 | |
| Codex 第 2 轮 | TASK-133 画面时钟识别、时间映射与同步检验 | ready | 依赖 TASK-132 |
| Codex 第 2 轮 | TASK-134 5 Hz 同步代理视频 | ready | 依赖 TASK-133 |
| Codex 第 2 轮 | TASK-121 多视角同步片段的区域标注工具（D12 r2） | ready | 依赖 TASK-134 |
| Claude | 审查第 2 轮，完整试标 pilot 片段 | 未开始 | |
| 用户 | 回答 Q7、Q8；标注 26 段，约 2 小时 | 待前置 | 可与第 3 轮并行 |
| Codex 第 3 轮 | TASK-102 新轨迹首帧立即确认（D2） | ready | GZ-03 |
| Codex 第 3 轮 | TASK-002 面部射线与 roll 符号对齐 | ready | GZ-02 |
| Codex 第 3 轮 | TASK-101 人脸与姿态关联修正（D1） | blocked | 等 TASK-102 审查通过；GZ-01 |
| Claude | 阶段 2 验收：离线门、作业数据真实 smoke、同步精度、修复前后对比 | 未开始 | |

第 3 阶段（多摄像机注视区域推断）的设计提案见 [ROADMAP.md](ROADMAP.md)，等你批准 D13 至 D15 后再写契约。

## 给 Codex 的说明

- **本轮第一步：首次推送并创建 draft PR。** 用户已于 2026-10-15 要求开 draft PR；Claude 的推送被本机工具权限拦截，所以由你执行。
  1. 确认当前分支是 `feature/stage2-correctness`，`git status` 干净，`git log --oneline bbec056..HEAD` 恰好列出 6 个提交：`61067da`、`e4c6f6c`、`9e59c90`、`5034bae`、`9d540ba`，以及主题为 `Prepare the stage draft PR and collaboration state` 的提交。不一致时停止并报告。
  2. 执行 `git push -u origin feature/stage2-correctness`，再用 `git ls-remote --heads origin feature/stage2-correctness` 确认。推送被拒绝时停止并报告，不 force push。
  3. 创建 draft PR：

     ```powershell
     gh pr create --draft --base feature/mediapipe-head-tracking --head feature/stage2-correctness --title "Stage 2: work-data readiness, synchronization, and correctness fixes" --body-file docs/collab/STAGE2_PR_BODY.md
     ```

  4. 把 PR 编号与链接写入控制块 `pr`（这一次由你填写），`last_pushed` 写当前 HEAD；提交 STATE.md，主题为 `Record stage draft PR`，然后推送。
- 之后每轮开始时：确认分支与 HEAD；若有 Claude 留下的文档改动，按协作方案 §3.1 第 3 步先提交并推送；若 `docs/collab/STAGE2_PR_BODY.md` 有变化，用 `gh pr edit <编号> --body-file docs/collab/STAGE2_PR_BODY.md` 同步。
- 按 `current_task` 执行，完成后按 `after_current` 继续，最后把 `next_actor` 改为 `claude`。
- 每个任务推送后，在控制块 `pr` 所指的 draft PR 发一条英中双语评论（协作方案 §4）。
- 任一任务的离线门失败且无法在任务范围内修复时，停止后续任务，在实施报告写明阻塞，把 `next_actor` 改为 `claude`。
- 数据规则（协作方案 §5）：`E:\Gazelle_Workdata\` 只读；派生数据写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`；长时间 CPU 任务以低优先级运行；GPU 推理前检查空闲显存。
- 在 TASK-131 合入前，不要用 CLI 处理作业数据的原始 AVI 或 MP4，契约中指定的检查除外。

## 给 Claude 的说明

- `next_actor` 为 `claude` 时：按提交 SHA 审查 `last_accepted` 之后的任务，复跑离线门，核对真实检查的数字。
- 审查 TASK-131 时，独立复跑 29 个 MP4 分段前 600 帧的时间戳检查与原始 AVI 的截断检查。
- 审查 TASK-121 时，用 `--labels-path` 指向临时文件，在内置浏览器完整试标 pilot 片段。通过后在「给用户的说明」写明标注启动方法。
- 在阶段节点更新 `docs/collab/STAGE2_PR_BODY.md` 的状态表，由 Codex 同步到 GitHub。
- 待办：TASK-134 完成后，用 `bbec056` 的导出快照在一段同步代理上做修复前基线运行，作为 TASK-101、TASK-102 的对照。

## 给用户的说明

当前不需要你操作代码。下一步请对 Codex 说“继续”：它会先推送阶段分支并创建 draft PR，之后进展汇总在该 PR 页面，编号会写入控制块 `pr`。

- **请在开始标注前回答**（见 [PROJECT_GOALS_CN.md](PROJECT_GOALS_CN.md) §5）：
  1. Q7：哪台是前方摄像机、哪台是右侧摄像机。证据显示加工时作业者正对文件名为カメラ2 的摄像机，与我之前的记录相反。
  2. Q8：注视区域的类别与边界。
- **稍后回答**：Q9（各次录制是否同一名作业者，今后是否继续录制、机位是否不变）；第 3 阶段的 D13 至 D15（见 [ROADMAP.md](ROADMAP.md)）。
- **可以否决的先行调整**：D12 改为作业数据上的连续片段区域标注，撤回 sample2；D4 时间戳修复并入 TASK-131。
- **过渡期提醒**：TASK-131、TASK-132 完成前，不要用当前代码直接处理 `E:\Gazelle_Workdata` 的视频。AVI 只会处理 1 帧却显示成功，部分 MP4 会在第 3 帧报错退出。

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
| 验证集规范 r2 与第 3 阶段设计提案 | 已提出，等待用户确认 | `../superpowers/specs/2026-10-15-workdata-validation-set-design.md`、`../superpowers/specs/2026-10-15-multicamera-attention-design.md` |

## 注意

- 模型缓存 `models/`、运行输出、验证集与作业数据的派生物都不在 Git 中，也不上传到任何服务。
- overlay 文件为 LF，checkout 其余为 CRLF；`git diff --check` 只提示不报错，提交时 Git 统一为 LF。
- 「复核确认」结论来自同产品只读代理，不等于独立验收。
