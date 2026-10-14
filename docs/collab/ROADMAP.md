# Gazelle 开发与优化路线图

维护者：Claude（协调者）。最近更新：2026-10-15（Asia/Tokyo）。
依据：[项目目标](PROJECT_GOALS_CN.md)、[代码库分析](analysis/2026-10-14-codebase-analysis.md)、[问题登记表](analysis/2026-10-14-issue-register.md)、[验收证据](evidence/2026-10-14-destination-acceptance.md)。
执行规则见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md)；当前轮到谁、做哪一项，以 [STATE.md](STATE.md) 为准。

## 状态图例

`ready` = 契约已写好，可执行；`blocked` = 等前置任务；`proposed` = 范围已定，契约待写；`needs-decision` = 等你决策；`accepted` = Claude 审查通过；`done` = 你已验收。

## 阶段 1：迁移与基线（done）

交接包恢复、模型缓存迁移、Gate A/B/C 通过；全库分析；协同框架落盘。基线 `bbec056`。

## 阶段 2：正确性与安全修复（进行中，分支 `feature/stage2-correctness`）

| 顺序 | 任务 | 状态 | 问题组 | 规模 | Claude 审查 | 真实 smoke |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [TASK-001](tasks/TASK-001-overwrite-safe-validation.md) 参数在 `--overwrite` 删除前校验 | ready | GZ-04 | S–M | 是 | 否 |
| 2 | [TASK-102](tasks/TASK-102-spawn-frame-confirmation.md) 新轨迹首帧立即确认（D2） | ready | GZ-03 | M | 是 | 是 |
| 3 | [TASK-002](tasks/TASK-002-face-ray-sign-alignment.md) 面部射线与 roll 符号对齐规范 | ready | GZ-02 | M | 是 | 是 |
| 4 | [TASK-101](tasks/TASK-101-face-pose-association.md) 人脸与姿态关联修正（D1） | blocked | GZ-01 | L | 是 | 是 |
| 5 | 阶段 2 验收 | 未开始 | 全部 | — | Claude 执行 | 是 |

设计依据：[2026-10-15 规范](../superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md)。
Codex 可以连续执行 1、2、3，然后交给 Claude 审查；4 必须等 2 审查通过。

## 阶段 3：工程加固（无需新的科学决策）

| 任务 | 状态 | 问题组 | 要点 |
| --- | --- | --- | --- |
| TASK-003 打包修正 | proposed | GZ-06 | 新增 `gazelle/__init__.py`，`setup.py` 只含 `gazelle` 子包；环境内重装验证需你授权 |
| TASK-004 运行时边界加固 | proposed | GZ-09、C056、C032、C038、C057 | 帧尺寸一致性、拒绝清理含输入的目录、FFmpeg 不继承 stdin、不写 NaN、显式 CUDA 不可用时提前失败 |
| TASK-005 测试加固 | proposed | GZ-07、GZ-20 | reader 时间戳、0.50 边界、轴向射线、`torch.hub` 目录恢复、samples 守卫、管线级跟踪集成 |
| TASK-006 文档同步批次 | proposed | GZ-17、GZ-10、GZ-12、GZ-14、GZ-15 | README_CN 省略、样例模板、射线键名、`--force-download` 范围与恢复、bridge 有效上限、`predict_frame` 默认状态 |
| TASK-007 研究脚本加固 | proposed | GZ-08 | VAT 预处理跨平台、评测严格加载、`hubconf.py` 安全加载、指标黄金值测试 |
| TASK-008 验收脚本与 CLI 易用性 | proposed | P2、P3、P5 | 一键离线验收脚本；拒绝带媒体后缀的 `--output-dir`；`run_config.json` 记录代码版本与关键依赖版本 |

## 待你决策

| 决策 | 内容 | Claude 的建议 |
| --- | --- | --- |
| D1 | 单人模式人脸与姿态关联 | **已批准**，见 TASK-101 |
| D2 | 新轨迹首帧策略 | **已批准**，见 TASK-102 |
| D3 | 子格头框（GZ-05） | 预测记录增加 `head_map_empty`，不改框与状态 |
| D4 | 时间戳时钟（GZ-07） | 回退时钟用解析后的 FPS 并保证单调，记录时间戳来源 |
| D5 | 桥接与跟踪窗口（GZ-12） | 两侧窗口由 `--head-track-max-gap-ms` 统一推导；多人桥接后空间去重 |
| D6 | 失败路径（GZ-13） | 维持致命失败；JSON 加载期全量校验；删除后置；写完成标记 |
| D7 | 图像预测状态（GZ-14） | `predictions.json` 增加帧级 `status` |
| D8 | DINOv2 与 checkpoint 完整性（GZ-10、GZ-11） | 固定 commit、校验权重 SHA-256、strict 校验移到替换前 |
| D9 | MediaPipe 阈值与裁剪（GZ-16） | 冻结当前默认阈值；裁剪内 `num_faces=1` |
| **D10** | **保守门控重新设计（F1）** | 门控不再以 Face Landmarker 成功为前提，改为头框质量加 Gazelle 自身 in/out 分数；先用 D12 的标注数据比较各策略，再定默认值。过渡期分析建议使用 `--gazelle-head-mode observed` |
| D11 | 单人模式主体身份长期稳定（F4） | 躯干优先跟踪或输出稳定的主体编号；sample2 在 13 分钟内出现 525 个 ID |
| **D12** | **目标场景验证集（F2）** | 从 sample1、sample2 抽取 200 至 300 帧，标注头框、视线目标点或区域、是否在画面内；作为所有感知与门控改动的量化验收 |
| P-merge | PR 堆叠链（P1） | 阶段 2 验收后，从 PR #2 起逐层合并到 `main`，或开一个汇总 PR；由你选择 |
| P-pr | 阶段分支的 draft PR | 建议开，用于在 GitHub 页面汇总每个任务的双语报告 |

D10 与 D12 对研究结论影响最大。D12 是 D10 的前提：没有标注，任何门控方案都只能凭感觉选。

## 阶段 4：Multi-Pose 库式接口

前提是回答 `PROJECT_GOALS_CN.md` 的 Q5：由 Multi-Pose 自己提供跟踪和头框，还是复用本仓库的感知链。
候选内容：声明并导出公共编程面；`predict_frame` 提供 in/out 分类入口；`torch.hub` 目录临时设置后恢复；`MediaPipeHeadProvider.create` 的配置契约类型化；`FramePacket` 去留（GZ-15）。

## 阶段 5：交接遗留研究方向

每项都需要独立规范与你的批准：场景切换重置（GZ-19）、躯干优先跟踪（D11）、虹膜与头姿与 heatmap 与区域融合、标定视线、摄像头模式、异步推理、音频重混、视频 heatmap 导出、在当前环境复现上游 GazeFollow 与 VAT 指标（需要数据集）。
