# 跨 Agent 协作流程

[English](AGENT_WORKFLOW.md) | [迁移指南](HANDOFF_CN.md) |
[任务模板](handoff/TASK_TEMPLATE.md)

## 1. 共用规则与明确负责人

`AGENTS.md` 是共用项目规则，`CLAUDE.md` 通过 import 引用它，避免维护两套约束。
按任务阅读相关文档和当前任务记录。本流程是人工协调约定，不是自动调度器、
文件锁、权限配置或不同产品之间的消息通道。

默认由一位 agent（Codex 或 Claude）负责实现，另一位可对稳定快照进行只读审查。
角色可以交换，由用户指定每个任务唯一的协调者。普通 ChatGPT/Claude 网页聊天
不会因这些文件而获得本地仓库权限：需要明确提供文档和 diff，或使用获授权的
本地 coding client。不同产品的对话和记忆不会因此自动同步。

## 2. 任务生命周期

1. 协调者记录目标、baseline SHA、工作区差异、验收、写入归属、资源和发布授权。
   简单任务可在聊天中记录，多阶段或跨会话任务使用模板落盘。
2. 实现者核对实际工作区，确认范围并实施、验证。冲突仅阻塞相关工作。
3. 审查前冻结写入；交付 HEAD、staged/unstaged diff 和相关新文件，或带哈希的
   快照。只有 HEAD 无法覆盖未提交变更。
4. 审查者报告严重度、具体文件/行、证据、复现及缺口；不编辑代码、不切换或重置
   工作区、不安装环境、不擅自运行测试。快照变化后需复审受影响部分。
5. 实现者修复问题。必需独立审查不可用时标记待验收；DONE 不能代替证据。
6. 换人前先停止正在写入的进程，记录最终文件和命令结果，释放资源，由接手者确认
   baseline。只有获授权的集成负责人执行 stage、commit、push 或 PR comment。

持久化任务记录只由协调者编辑，辅助 agent 返回报告，不抢写同一份记录。不同
checkout/电脑应指定一份唯一的协调记录并分发已确认副本。时间戳过期不等于可接管；
未收到交接确认或旧写入者仍运行时，应暂停接管，仍可做独立只读工作。

## 3. 同机资源协调

| 资源 | 协调规则 |
| --- | --- |
| 同一 checkout / Git index | 同时仅一个写入者，即使修改不同文件；不并行 checkout/stage/commit |
| 审查者 | 只读稳定快照；测试可能写文件，需在任务中单独分配 |
| 并行实现 | 必须已获授权、隔离 checkout、明确接口归属；现有禁止擅自新建分支规则仍有效 |
| GPU | 默认一次一个获分配的任务；并行需容量依据与授权，记录 device 和进程负责人 |
| Conda `Gazelle` | 可共享运行时读取；修改依赖需独占并遵循获批的 sandbox-first 流程 |
| Torch Hub / MediaPipe cache | 优先预准备后只读复用，准备和刷新串行，禁止并行 force-download |
| 输出和临时媒体 | 每任务/agent 独立目录，不对他人结果使用 `--overwrite` |
| 端口、子进程、临时 pycache | 按任务分配，记录 PID，仅清理自己拥有的资源 |
| GitHub | 一个获授权发布者更新现有 PR，不竞争 push |

worktree 不能隔离共享 Git 元数据操作、环境、GPU、缓存和输出。本次交接不会
自动创建 branch/worktree。不要用自动同步文件夹合并两个活动 checkout；跨电脑
应交换已获准的 commits，或附带基线的已审查 patch/快照。

## 4. 验证和科研语义

采用 AGENTS 的风险分级：纯文案做静态检查，行为变化做相关回归和完整离线验收。
指标、坐标、时序、阈值、接口与兼容性变化即使只有一行也需要独立审查。默认测试
不使用模型、网络、CUDA 或真实 FFmpeg。可选真实测试需要授权、资源归属、精确
命令，并单独报告结果。

报告须区分观察事实、解释和建议。渲染模式对比保留原始 observation 和 prediction
status，不把 head-pose ray 或模型热图峰值称为测量得到的真实眼睛视线。

## 5. 客户端接手检查

从仓库根目录启动，让 agent 说明当前可见规则来源、角色、可写文件、禁令和待验收项。
区分启动时加载与后来手动读取。global/目录 override 或客户端设置可能影响加载；
发现冲突先报告，不擅自改设置。切换客户端后再次确认。

Codex 支持按目录发现 AGENTS；Claude Code 支持 CLAUDE.md import，本项目通过
显式引用共用规则。实际支持受版本和设置影响，本次未启动 Claude 或验证新的 Codex
会话。官方依据（2026-10-14 核对）：[Codex instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、
[Claude Code memory](https://code.claude.com/docs/en/memory)。

本流程不需要也不会安装插件、配置模型 API/凭据、创建常驻 agent 或无人值守自动化。
