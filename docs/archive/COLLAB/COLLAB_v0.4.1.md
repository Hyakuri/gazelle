# Claude × Codex 协同开发方案（v0.4，2026-10-15）

本文件是 Claude 与 Codex 共用的协作规则，补充而不替代 `AGENTS.md`。冲突时的优先级：用户当前指令，然后 `AGENTS.md`，然后本文件。
用户的《当前对话执行范式 v1.1》按其自身规则只在明确采用的对话中生效，本文件不代替采用（见 §6）。

## 0. 一句话

两个 agent 都在 `C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle` 中工作，只通过 `docs/collab/` 里的文件沟通。
**唯一入口是 `docs/collab/STATE.md`**：它写明当前阶段、分支、轮到谁、当前任务文件和接下来做什么。
Codex 把结果提交并推送到 GitHub 阶段分支留档，并在阶段分支的 draft PR 页面发报告；用户在 PR 页面查看进展，在自己的独立目录同步该分支后验收。

## 1. 角色

| 角色 | 承担者 | 负责 | 不做 |
| --- | --- | --- | --- |
| 协调与验收 | Claude | 分析开发状态；制定与修改执行方案、设计规范、任务契约；按提交 SHA 审查每个任务；阶段验收（含真实 smoke）；维护 STATE.md 的协调字段、ROADMAP、`analysis/`、`evidence/` | 不执行 git 写操作（add、commit、push、建分支）；用户明确要求的阶段建立与开 draft PR 除外 |
| 执行与留档 | Codex | 读懂当前任务并实施；测试；写执行记录与结果总结；提交并推送阶段分支；把 Claude 写入的文档改动一并提交；编写报告 | 不修改任务契约段、ROADMAP 与设计规范；不新建分支或 PR、不合并、不 force push |
| 决策与最终验收 | 用户 | 决定需要决策的事项；在独立目录同步 GitHub 并验收 | 无需粘贴文件 |

## 2. 固定入口与读取顺序

每次开始工作，无论 Claude 还是 Codex，都按这个顺序读取：

1. `AGENTS.md`：Codex 会自动加载；Claude 通过 `CLAUDE.md` 导入。它指向第 2 步。
2. `docs/collab/STATE.md`：控制块写明 `writer`、`next_actor`、`current_task` 与本轮结束后的动作。
3. `current_task` 指向的任务文件 `docs/collab/tasks/TASK-*.md`。
4. 任务文件引用的设计规范、代码与证据。

用户只需要对 Codex 说“继续”，对 Claude 说“继续”。判断“现在该谁做什么”只看 STATE.md，不看文件修改时间。

## 3. 标准循环

### 3.1 Codex 一轮

1. 读 STATE.md。若 `writer` 不是 `none`，或 `next_actor` 不是 `codex`，停止并说明原因。
2. 把 `writer` 改为 `codex`。
3. 若工作区有 Claude 留下的未提交文档改动（`docs/collab/**`、`docs/superpowers/specs/**`、`AGENTS.md`、`CLAUDE.md`），先只提交这些路径，提交信息为 `Record coordinator updates`，然后推送。
4. 执行 `current_task`：实施、测试、离线门全部通过后按任务提交并推送。
5. 在任务文件末尾追加「实施报告」，写明提交 SHA、命令与结果、证据类型、未运行的检查；提交并推送。
6. 更新 STATE.md 中归 Codex 维护的字段：任务状态改为 `ready-for-review`、`last_pushed` 写最新 SHA。
7. 若控制块的 `after_current` 指定了下一个任务，把 `current_task` 换成它并回到第 4 步；否则把 `next_actor` 改为 `claude`。
8. 把 `writer` 改回 `none`，提交并推送 STATE.md，结束本轮。

### 3.2 Claude 一轮

1. 读 STATE.md。若 `writer` 不是 `none`，只做只读分析，不写文件。
2. 把 `writer` 改为 `claude`。
3. 审查 `last_accepted` 之后到 `last_pushed` 的提交：读 diff、独立复跑离线门、需要时跑真实 smoke，在任务文件写「审查结论」。
4. 通过则把任务改为 `accepted` 并更新 `last_accepted`；不通过则改为 `changes-requested` 并写明必须修复项。
5. 更新 ROADMAP 与下一个任务契约，设置 `current_task`、`after_current` 与 `next_actor`。
6. 把 `writer` 改回 `none`。Claude 不提交，这些文件由 Codex 下一轮第 3 步提交。

### 3.3 用户

- `next_actor` 为 `user` 时，按 STATE.md「给用户的说明」行事：做决策，或在独立目录同步 `last_accepted` 并验收。
- 验收结果直接告诉 Claude。

### 3.4 STATE.md 字段归属

| 字段 | 维护者 |
| --- | --- |
| `writer` | 开始写入的一方改为自己，结束时改回 `none` |
| `next_actor` | 结束本轮的一方设置 |
| `current_task`、`after_current` | Claude；Codex 只在 3.1 第 7 步按 `after_current` 推进 |
| 任务队列中的状态 | Codex 改为 `ready-for-review`；其余状态由 Claude 改 |
| `last_pushed` | Codex |
| `last_accepted`、`pr`、阶段、分支、待决事项 | Claude |

## 4. Git 与 GitHub 规则

- 阶段分支：`feature/stage2-correctness`，基于 PR #5 的 head `bbec056`。
- 每个任务至少一个 focused commit；主题行用英文祈使句；正文写 `Task: TASK-xxx`。
- 只按明确路径暂存；禁止 `git add -A` 与 `git add .`。提交前检查 `git status`、暂存路径与 `git diff --check`。
- 不提交 `models/`、`outputs/`、媒体文件、JSONL、权重、缓存、凭据，也不提交验证集的帧、标注，以及作业数据的任何派生物（清单、时间映射、代理视频、报告数据）。
- 普通推送；被拒绝时 `git fetch` 后停止并报告，不 rebase、不 force push、不合并。
- 不新建分支或 PR，除非本文件 §7 的授权记录写明用户已批准。
- 报告：任务文件的「实施报告」是正式执行报告，随提交上传。
- draft PR：阶段分支对应一个 draft PR，编号见 STATE.md，base 为 PR #5 的 head 分支 `feature/mediapipe-head-tracking`。
  - Codex 每次推送任务提交后，在该 PR 发一条评论：先英文，再一行 `---`，再中文；内容按 `AGENTS.md` 的 GitHub Reporting 七项。
  - PR 正文的来源是 `docs/collab/STAGE2_PR_BODY.md`，由 Claude 在阶段节点维护（审查结论、阶段验收、计划调整）。Codex 在每轮第 3 步提交 Claude 的文档改动后，若该文件有变化，执行 `gh pr edit <编号> --body-file docs/collab/STAGE2_PR_BODY.md` 同步。
  - 任何一方都不改 PR 标题、draft 状态与 base，不合并。

## 5. 审查与验收

| 层级 | 内容 | 执行者 |
| --- | --- | --- |
| L0 静态 | diff、编码、Markdown、引用、保留约束 | Codex，Claude 复核 |
| L1 聚焦 | 受影响契约的单测与最小复现 | Codex |
| L2 离线门 | `AGENTS.md` Validation 的六条命令 | Codex 跑，Claude 独立复跑 |
| L3 真实 smoke | 本地 CUDA、MediaPipe、FFmpeg；仅缓存资源；输出写到仓库外 | 任务契约指定 |
| L4 阶段验收 | 阶段内全部任务 accepted 后，Claude 跑完整离线门与真实 smoke 矩阵，写 `evidence/<日期>-stage<N>-acceptance.md` | Claude |
| L5 最终验收 | 用户在独立目录同步 `last_accepted` 并验证 | 用户 |

涉及指标、坐标、时序、阈值、接口或兼容性的改动，即使只有一行，也需要 Claude 审查。

**GPU 与数据资源规则**

- 本机 GPU 与你的其他实验共用。任何 GPU 推理开始前，先运行 `nvidia-smi --query-gpu=memory.used,memory.total --format=csv`。空闲显存少于 4 GB，或有本项目以外的进程正在大量使用 GPU 时，不启动推理，在报告中写明“GPU 被占用，未运行”，把该检查标为待补。
- MediaPipe 只用 CPU，不受此限制。长时间的 CPU 任务（重封装、时钟识别、代理视频编码）以低于正常的优先级运行，因为 CPU 也与用户的其他实验共用。
- 作业数据只读：`E:\Gazelle_Workdata\` 是目标场景的主数据，不得写入。派生数据（清单、重封装、时间映射、代理视频）写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`。
- `C:\Users\yun\Documents\GitHub\gazelle\samples\` 下的 sample1 只作冒烟输入；sample2 不属于目标场景，不再用于验证或评估。不得写入该目录。
- 运行输出写到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\`，验证集写到 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\`。上述目录都在 Git 之外，也不上传到任何服务。
- 作业视频含可识别的作业者面部。仓库中的报告只写汇总数字、文件名与时钟读数，不放图像，不写人名与企业名。

## 6. 执行范式与证据分级

- Codex：每个新的 Codex 对话由用户说一次采用 v1.1；之后按 v1.1 原样执行，仅主线程、不开子代理。建议为本项目保持一个长期 Codex 对话。
- Claude：主线程负责契约、决策与审查结论；可以用只读子代理做大范围调查与反证复核，但进入契约的关键结论必须由主线程亲自复现或用实测数据核对。
- 证据词：已实际运行、主线程复现、复核确认、推断。完成状态使用 v1.1 §12 的六个标签。

## 7. 授权记录

| 日期 | 授权内容 | 对象 |
| --- | --- | --- |
| 2026-10-14 | 在本目录修改文件；调用本地运算设备（GPU、FFmpeg）测试 | Claude、Codex |
| 2026-10-15 | Codex 负责 GitHub 上传与报告：提交并推送到阶段分支 | Codex |
| 2026-10-15 | 基于 PR #5 建立新阶段分支：Claude 已在本地建立分支并完成阶段建立提交；首次推送由 Codex 执行（Claude 的推送两次被本机工具权限拦截） | Claude、Codex |
| 2026-10-15 | D1、D2 按 Claude 的推荐执行 | Claude、Codex |
| 2026-10-15 | D10、D12 按 Claude 的推荐执行 | Claude、Codex |
| 2026-10-15 | 只读使用独立目录中的 sample1、sample2，用于真实 smoke、阶段验收与验证集（之后 sample2 因不属于目标场景停用） | Claude、Codex |
| 2026-10-15 | 为阶段分支开 draft PR，在开头记录阶段目标与状态，在 GitHub 页面汇总报告 | Claude 准备正文与提交；因 Claude 的推送被本机工具权限拦截，由 Codex 推送并创建；Codex 发报告评论 |
| 2026-10-15 | PR #2 至 #5 的堆叠链在项目达到目标功能后再集中梳理合并 | 用户决定，任何一方不得提前合并 |
| 2026-10-15 | 用户提供 `E:\Gazelle_Workdata` 并要求详细分析。协调者据此理解为：只读用于分析、数据准备、标注与真实运行，派生物只留在本机仓库之外。用户可以收窄此范围 | Claude、Codex |
| 2026-10-15 | 用户确认摄像机角色（カメラ2 前方、カメラ1 右侧、設備カメラ全局）；区域由用户在全局摄像机画面上标记；同一日期为同一作业者、机位固定；批准 D4、D12 r2、D13 至 D15 | Claude、Codex |

仍需逐项授权：合并、修改 PR 标题或 base 或 draft 状态、修改 Conda 环境、下载资源、写入或修改用户独立目录或 `E:\Gazelle_Workdata\`、把任何数据上传到外部服务。

## 8. 文档索引

| 文件 | 用途 | 维护者 |
| --- | --- | --- |
| `STATE.md` | 唯一入口：控制块、任务队列、给下一位的说明 | 见 §3.4 |
| `PROJECT_GOALS_CN.md` | 项目目标、需求基线、错误与疏漏、待确认问题 | Claude |
| `ROADMAP.md` | 阶段、任务队列、待决策项 | Claude |
| `analysis/` | 代码库分析报告与问题登记表 | Claude |
| `evidence/` | 验收与真实运行证据 | Claude |
| `tasks/TASK-*.md` | 单任务契约、实施报告、审查结论 | 契约与审查归 Claude，实施报告归 Codex |
| `QUICKSTART_CN.md` | 给用户的最短操作说明 | Claude |
| `STAGE2_PR_BODY.md` | 阶段 2 draft PR 正文的来源 | Claude 维护，Codex 同步到 GitHub |
| `../superpowers/specs/` | 已批准设计规范 | Claude |
