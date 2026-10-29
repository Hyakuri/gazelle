# TASK-NNN：<短标题>

> 模板。由 Claude 填写并作为「契约」段的唯一编辑者；Codex 只追加「实施报告」段；
> Claude 追加「审查结论」段。状态流转见 `docs/rules/COLLABORATION_PLAN_CN.md` §3。

状态：proposed | active | ready-for-review | changes-requested | accepted | handed-off | merged | blocked
创建：YYYY-MM-DD（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）

## 1. 契约（v1.1 §3）

- 目标：
- 非目标：
- 交付物：
- 依据材料（文件 + 版本）：分支 `…`，基线 HEAD `…`；相关 spec/plan；相关代码与测试路径
- 不可变约束：AGENTS.md「Runtime Invariants」「Research And Data Integrity」全部；本任务额外：…
- 允许动作：读全库；写以下路径：…；运行 L0–L2 验证；按协作方案 §4 在阶段分支提交并推送；不新建分支或 PR、不合并、不 force push、不安装、不下载；真实推理仅在本契约明确要求时进行
- 验收标准（可检验）：
  1. …
  2. …
- 验证命令（Codex 必跑，Claude 复跑）：
  ```powershell
  $env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-NNN-pycache"
  python -m unittest tests.test_xxx -v
  python -m compileall main.py gazelle tests
  python -m unittest discover -s tests -v
  python main.py --help
  python main.py --list-models
  git diff --check
  git status --short
  ```
- 需独立审查：是/否（指标/坐标/时序/阈值/接口/兼容性改动 = 是）
- 需真实 smoke（L3）：否 | 是（命令、输入、输出根目录、授权依据）
- 文档同步：不需要（原因）| 需要（README.md / README_CN.md / docs/usage/USAGE.md / docs/usage/USAGE_CN.md / tests/test_usage_docs.py）
- 风险与回退：
- 依赖任务：

## 2. 实施报告（Codex 追加，勿改上文）

- 接手核对：分支 / HEAD / `git status -sb` / 可见规则来源
- 变更文件（含新增、未跟踪）：
- 命令、退出码、测试数、warnings/skips：
- 证据类型：静态 / mock 单测 / 真实模型-GPU-FFmpeg / 正式实验
- 外部活动（网络/下载/缓存/环境）：无 | …
- 反证式复核（v1.1 §9）：检查过的反例、边界、最可能失败路径及结论
- 自主决定（A 级，协作方案 §3.5）：问题、证据、做法、影响；无则写“无”
- 范围外改动：文件与理由；无则写“无”
- 待 Claude 判断（B 级）：现象、证据、已尝试的做法、方案与利弊、推荐、是否已暂定实施；无则写“无”
- 待用户决定（C 级）：问题、原因、选项、推荐；无则写“无”
- 未运行检查、限制、阻塞：
- 状态标签（v1.1 §12）：已实施 / 已静态检查 / 已实际运行 / 待独立验收
- 下一步建议：

## 3. 审查结论（Claude 追加）

- 审查目标：HEAD + diff 快照（哈希或时间）
- 独立复跑结果：
- 发现（严重度 / 文件:行 / 证据 / 复现）：
- 结论：accepted | changes-requested（列出必须修复项）
- 集成记录：commit SHA / push / PR（仅在授权下）

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
- 合并状态：
