# Task Handoff / 任务交接模板

Template only; not an active assignment or permission grant. The coordinator
fills this once for a substantial task and is its sole editor. Keep private
paths/results outside Git unless publication is authorized. Delete no user data.

## Scope / 范围

- Task ID / 任务编号:
- Goal and non-goals / 目标和排除项:
- Acceptance / 验收标准:
- User authorization reference / 用户授权依据:
- Allowed actions / 允许动作:
- Publication authority (none by default) / 发布权限（默认无）:

## Baseline And Ownership / 基线与归属

- Date/time with timezone / 带时区时间:
- Repository, machine, absolute checkout / 仓库、电脑、绝对路径:
- Branch, HEAD, existing PR / 分支、HEAD、现有 PR:
- Staged, unstaged, untracked changes and owners / 全部未提交变更及归属:
- Snapshot/patch path and SHA-256 / 快照或 patch 及哈希:
- Canonical coordinator record location / 唯一协调记录位置:
- Coordinator / 协调者:
- Implementation owner and permitted write paths / 实现者及可写路径:
- Reviewer and stable review target / 审查者及稳定目标:
- Interpreter/environment, GPU, caches, ports, output roots / 资源分配:
- Running jobs/PIDs and owners / 运行进程及归属:

## Progress And Evidence / 进度与证据

- State: proposed / active / ready-for-review / changes-requested /
  accepted / handed-off / blocked
- Decisions, rationale, approved specifications / 决策和批准的规范:
- Changed/new files / 修改与新增文件:
- Commands, exit codes, test counts and artifacts / 命令、退出码、测试数和产物:
- Static vs mocked vs real model/GPU vs formal experiment / 证据类型:
- Network/download/cache reuse and environment changes / 外部活动:
- Review findings and resolutions / 审查问题与解决:
- Unrun checks, limitations, blockers / 未运行检查、限制、阻塞:
- Documentation updates / 文档同步:
- Next concrete action / 下一项具体动作:

## Transfer / 交接确认

- Outgoing owner: writes stopped, jobs stopped/released, final baseline recorded:
- Incoming owner: baseline, permissions and resource ownership acknowledged:
- Unresolved conflicting owner/process: do not take over affected resources:
- Actual commit/push/comment status (never infer from task state):

填写本模板不会建立操作系统锁，也不会授予环境修改、模型下载、训练或发布权限。
