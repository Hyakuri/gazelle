# Claude × Codex 协同开发方案（v0.6，2026-10-16）

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

0. 新的 Codex 会话第一次执行前，以及权限设置变更后，先做环境预检（§5「Codex 运行环境」）。不通过的项目按 §3.5 处理：先试不改配置的替代办法；只影响部分工作的缺失项不阻塞其余工作；只有工作区本身不可写时才停下请用户处理。不修改任何配置。
1. 读 STATE.md。若 `writer` 指向 Claude，或 `next_actor` 不是 `codex`，只做只读分析，不写文件，并说明原因。若 `writer` 是自己上次中断留下的 `codex`，确认没有其他 agent 正在写入后可以继续。
2. 把 `writer` 改为 `codex`。
3. 若工作区有 Claude 留下的未提交文档改动（`docs/collab/**`、`docs/superpowers/specs/**`、`AGENTS.md`、`CLAUDE.md`），先只提交这些路径，提交信息为 `Record coordinator updates`，然后推送。
4. 执行 `current_task`：实施、测试、离线门全部通过后按任务提交并推送。遇到问题按 §3.5 分级处理：能自己解决的先解决并记录；需要 Claude 判断或用户决定的，写明证据与方案后交出，同时继续不受影响的工作与后续任务。契约正文仍由 Claude 修改，Codex 在实施报告中记录偏差。
5. 在任务文件末尾追加「实施报告」，写明提交 SHA、命令与结果、证据类型、未运行的检查，以及 §3.5 规定的四个小节；提交并推送。
6. 更新 STATE.md 中归 Codex 维护的字段：任务状态改为 `ready-for-review`、`last_pushed` 写最新 SHA。
7. 若控制块的 `after_current` 指定了下一个任务，把 `current_task` 换成它并回到第 4 步；否则把 `next_actor` 改为 `claude`。只有剩余工作全部依赖用户决定时，才把 `next_actor` 设为 `user`。
8. 把 `writer` 改回 `none`，提交并推送 STATE.md，结束本轮。

### 3.2 Claude 一轮

1. 读 STATE.md。若 `writer` 不是 `none`，只做只读分析，不写文件。
2. 把 `writer` 改为 `claude`。
3. 审查 `last_accepted` 之后到 `last_pushed` 的提交：读 diff、独立复跑离线门、需要时跑真实 smoke，在任务文件写「审查结论」。逐项确认实施报告中的 A 级自主决定：认可的写进契约，不认可的列为必须修复项。对 B 级问题给出分析与决定，更新契约或设计。把 C 级问题整理到 STATE.md「给用户的说明」与「待决问题」。
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
| `last_accepted`、`pr`、阶段、分支 | Claude |
| 「待决问题」表 | 两方都可以新增；Claude 处理 B 级并标记结果，用户回答 C 级后由 Claude 标记 |

### 3.5 问题处理与升级（分级自主）

用户 2026-10-16 决定：Codex 先自己尝试解决问题；需要用户回答或判断的事项交给用户；需要详细分析与判断的事项交给 Claude。遇到问题时只暂停受影响的那一部分，其余工作照常进行，不要整轮停下。

| 级别 | 适用情形 | Codex 的做法 |
| --- | --- | --- |
| A 自行处理 | 自己的代码或测试失败；工具、命令或库的用法问题；不改配置、不提权就能绕过的环境问题；真实数据与预期略有出入，但按契约目标有明确合理的处理方式；契约本意明确的错误，即契约自身的目标、验收标准或示例已说明本意；为完成任务必需的少量相邻改动 | 先做根因分析再修复；在实施报告「自主决定」中记录问题、证据、做法与影响；继续执行 |
| B 交 Claude 判断 | 影响研究语义、指标或评估协议、输出 schema、公共接口，或跨任务的接口与顺序；契约本意不明确，存在多个都合理但结果不同的做法；真实数据推翻了契约或设计的前提；想删除、放宽或改写验收标准；同一问题两次修复无进展，重新做根因分析后仍没有把握 | 在实施报告「待 Claude 判断」中写明现象、证据、已尝试的做法、方案与利弊、推荐。推荐方案可逆且只影响本任务时，可以先按推荐实施并标为“暂定”。继续不依赖该问题的工作与后续任务；本轮结束时把 `next_actor` 设为 `claude` |
| C 交用户决定 | 需要尚未获得的授权，见 §7「仍需逐项授权」；目标、范围或研究取舍需要用户偏好；需要用户亲自操作，例如登录、批准命令、画区域、标注 | 在回复中直接提问，写明原因、选项与推荐；记入实施报告与 STATE.md「待决问题」；继续不受影响的工作 |

硬边界，任何级别都不能越过：

- `AGENTS.md` 的 Git 安全规则：不 force push，不改写已推送的历史，不做破坏性清理，不合并 PR。
- 不修改 Conda 环境；未经授权不下载；源数据只读；不提交、不上传数据与媒体。
- 不降低验证标准来掩盖失败：不放宽断言，不排除失败样本，不悄悄改动指标。
- 单写入者规则：`writer` 指向其他 agent 时不写仓库文件。

常见情形的处理：

| 情形 | 做法 |
| --- | --- |
| 环境预检有项目不通过 | 先试不改配置的替代办法，例如把 `TMP`、`TEMP` 指向已授权的可写目录，或请用户批准单条命令；只影响部分工作的缺失项不阻塞其余工作；只有工作区本身不可写时才停下 |
| 推送被拒绝 | 按 `AGENTS.md` 执行 `git fetch` 并检查远端变化，不 force push、不 rebase；按 B 级报告，本地开发与提交可以继续 |
| 推送或 `gh` 因认证、网络失败 | 继续本地提交，稍后重试；§7 常设批准范围内的命令可以直接在用户上下文运行 |
| 离线门失败 | 先修复；失败来自本任务以外的既有缺陷或环境时，记录证据并按 B 级报告，继续不依赖它的任务 |
| GPU 被占用 | 先做其他工作，稍后再查；仍被占用则把该检查标为待补 |
| 契约列出的文件不够 | 必需的少量相邻改动按 A 级处理，并在「范围外改动」中逐项列出；涉及公共接口、schema、研究语义或其他任务负责的模块时按 B 级处理 |

任务契约「禁止」一节中“修改其他文件”“修改上面未列出的文件”一类条目，按上表最后一行理解；其余禁止项仍是硬边界。

实施报告与 PR 评论中增加四个小节，没有内容时写“无”：

- 自主决定（A 级）：问题、证据、做法、影响。
- 范围外改动：文件与理由。
- 待 Claude 判断（B 级）：现象、证据、已尝试的做法、方案与利弊、推荐，以及是否已暂定实施。
- 待用户决定（C 级）：问题、原因、选项、推荐。

## 4. Git 与 GitHub 规则

- 阶段分支：`feature/stage2-correctness`，基于 PR #5 的 head `bbec056`。
- 每个任务至少一个 focused commit；主题行用英文祈使句；正文写 `Task: TASK-xxx`。
- 只按明确路径暂存；禁止 `git add -A` 与 `git add .`。提交前检查 `git status`、暂存路径与 `git diff --check`。
- 不提交 `models/`、`outputs/`、媒体文件、JSONL、权重、缓存、凭据，也不提交验证集的帧、标注，以及作业数据的任何派生物（清单、时间映射、代理视频、报告数据）。
- 普通推送。被拒绝时按 `AGENTS.md` 执行 `git fetch` 并检查远端变化，不 rebase、不 force push、不合并；按 §3.5 的 B 级报告，本地开发与提交可以继续。
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

- 本机 GPU 与你的其他实验共用。任何 GPU 推理开始前，先运行 `nvidia-smi --query-gpu=memory.used,memory.total --format=csv`。空闲显存少于 4 GB，或有本项目以外的进程正在大量使用 GPU 时，不启动推理：先做其他工作，稍后再查一次；仍被占用时在报告中写明“GPU 被占用，未运行”，把该检查标为待补。
- MediaPipe 只用 CPU，不受此限制。长时间的 CPU 任务（重封装、时钟识别、代理视频编码）以低于正常的优先级运行，因为 CPU 也与用户的其他实验共用。
- 作业数据只读：`E:\Gazelle_Workdata\` 是目标场景的主数据，不得写入。派生数据（清单、重封装、时间映射、代理视频）写到 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`。
- `C:\Users\yun\Documents\GitHub\gazelle\samples\` 下的 sample1 只作冒烟输入；sample2 不属于目标场景，不再用于验证或评估。不得写入该目录。
- 运行输出写到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\`，验证集写到 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\`。上述目录都在 Git 之外，也不上传到任何服务。
- 作业视频含可识别的作业者面部。仓库中的报告只写汇总数字、文件名与时钟读数，不放图像，不写人名与企业名。

**Codex 运行环境**

Codex 会话的工作区必须是 `C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle`，旧目录的会话不能继续用于本项目。设置方法见 [QUICKSTART_CN.md](QUICKSTART_CN.md)。预检逐项确认：

| 项目 | 检查方法 | 需要的权限 |
| --- | --- | --- |
| 工作区 | `git rev-parse --show-toplevel` 指向上面的目录 | 本目录可写 |
| 数据目录 | 在 `gazelle_data`、`gazelle_runs`、`gazelle_validation` 与 `%TEMP%` 中各新建并删除一个空文件 | 这四处可写 |
| 作业数据 | 列出 `E:\Gazelle_Workdata\秋田大学様解析用動画\` 下的 7 个文件夹 | 只读 |
| 解释器 | `C:\Users\yun\anaconda3\envs\Gazelle\python.exe --version` | 可执行 |
| FFmpeg | `ffmpeg -version` 与 `ffprobe -version` | 可执行 |
| GitHub | `git ls-remote origin` 与 `gh auth status` | 网络 |
| GPU | `nvidia-smi --query-gpu=memory.used,memory.total --format=csv` | 只读，仅记录 |

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
| 2026-10-16 | 分级自主：Codex 先自行解决问题；设计层面的判断交 Claude；需要授权或用户偏好时才问用户；硬边界不变（§3.5） | Codex、Claude |
| 2026-10-16 | 常设批准：Codex 可以在用户账户 `yun` 的上下文中运行本项目的发布类命令，不必每轮重新请求。范围限于阶段分支 `feature/stage2-correctness` 与 draft PR #6：`git fetch`、普通 `git push`、`gh pr view`、`gh pr comment`、`gh pr edit`（只用于按 `docs/collab/STAGE2_PR_BODY.md` 同步正文），以及只读核对 `git ls-remote`、`gh auth status`。不包括 force push、删除分支、新建或合并 PR、修改 PR 的标题、base 或 draft 状态 | Codex |

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
