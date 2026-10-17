# Gazelle 开发与优化路线图

维护者：Claude（协调者）。最近更新：2026-10-15（Asia/Tokyo），按你当天确认的目标与[作业数据分析](analysis/2026-10-15-workdata-analysis.md)重排。
依据：[项目目标](PROJECT_GOALS_CN.md)、[代码库分析](analysis/2026-10-14-codebase-analysis.md)、[问题登记表](analysis/2026-10-14-issue-register.md)、[验收证据](evidence/2026-10-14-destination-acceptance.md)。
执行规则见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md)；当前轮到谁、做哪一项，以 [STATE.md](STATE.md) 为准。

## 状态图例

`ready` = 契约已写好，可执行；`blocked` = 等前置任务；`proposed` = 范围已定，契约待写；`needs-decision` = 等你决策；`accepted` = Claude 审查通过；`done` = 你已验收。

## 总体路线

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 1 | 迁移与基线 | done |
| 2 | 作业数据可用、多机同步、正确性修复，建立区域标注 | 进行中 |
| 3 | 多摄像机注视区域推断与统计 | 设计已批准，阶段 2 验收后开始 |
| 4 | 工程加固 | proposed |
| 5 | 多人同时推断 | 未开始 |
| 远期 | 实时处理 | 不纳入当前计划 |

原“阶段 4：Multi-Pose 库式接口”按你的决定移除，以后需要时再立项。

## 阶段 1：迁移与基线（done）

交接包恢复、模型缓存迁移、Gate A/B/C 通过；全库分析；协同框架落盘。基线 `bbec056`。

## 阶段 2（进行中，分支 `feature/stage2-correctness`，draft PR 见 STATE.md）

| 轮次 | 任务 | 状态 | 问题 | 规模 | 真实运行 |
| --- | --- | --- | --- | --- | --- |
| 1 | [TASK-131](tasks/TASK-131-video-reader-timestamps-and-truncation.md) 读取器：容器时间戳、严格递增、截断即失败 | accepted | GZ-07、GZ-21 | M | CPU 读取检查；一次 GPU smoke |
| 1 | [TASK-132](tasks/TASK-132-workdata-inventory-and-avi-remux.md) 作业数据清单与 AVI 无损重封装 | accepted | 数据 P0、GZ-22 | M | FFmpeg 流复制 |
| 1 | [TASK-123](tasks/TASK-123-overview-region-marking-tool.md) 全局摄像机画面中的区域标记工具 | accepted（第 2 轮修复后） | Q8 | M | CPU，抽取候选帧 |
| 1 | [TASK-001](tasks/TASK-001-overwrite-safe-validation.md) 参数在 `--overwrite` 删除前校验 | accepted | GZ-04 | S–M | 否 |
| 2 | [TASK-137](tasks/TASK-137-switch-to-gazelle-next.md) 项目环境切换到 `Gazelle-next`（仓库侧） | accepted | D16 | S–M | GPU smoke 三次 |
| 2 | [TASK-135](tasks/TASK-135-round1-followups.md) 第 1 轮审查的后续加固 | accepted | GZ-07、GZ-21 | S–M | CPU，重新校验重封装 |
| 2 | [TASK-133](tasks/TASK-133-osd-clock-time-maps.md) 画面时钟识别、时间映射与同步检验 | 部分通过（时间映射由 TASK-139 取代） | 同步、GZ-22、GZ-26 | L | CPU |
| 2 | [TASK-134](tasks/TASK-134-synchronized-proxies.md) 5 Hz 同步代理视频 | accepted（生成机制；代理由 TASK-139 重新生成） | 同步 | M | CPU，数小时 |
| 2 | [TASK-121](tasks/TASK-121-validation-annotation-toolkit.md) 多视角同步片段的区域标注工具（D12 r2） | changes-requested（TASK-138） | F2、GZ-27 | L | CPU |
| 你 | 用区域标记工具画出区域，约 10 分钟 | **现在可以开始** | — | — | — |
| 你 | 决定 D18：同步协议 r2 | 待决定 | GZ-26 | — | — |
| 3 | [TASK-138](tasks/TASK-138-annotation-and-roi-followups.md) 标注与区域工具的后续修复 | ready（本轮第一项） | GZ-27 | M | CPU，浏览器实测 |
| 3 | [TASK-136](tasks/TASK-136-gazelle-device-preprocessing.md) Gazelle 输入预处理移到推理设备 | ready（D17 已同意） | GZ-25 | S–M | 是，CUDA smoke |
| 3 | [TASK-139](tasks/TASK-139-content-calibrated-sync.md) 同步协议 r2：以前方摄像机为基准的画面内容校准 | proposed（待 D18） | GZ-26 | L | CPU，约 6 小时后台 |
| 3 | [TASK-102](tasks/TASK-102-spawn-frame-confirmation.md) 新轨迹首帧立即确认（D2） | ready | GZ-03 | M | 是 |
| 3 | [TASK-002](tasks/TASK-002-face-ray-sign-alignment.md) 面部射线与 roll 符号对齐 | ready | GZ-02 | M | 是 |
| 3 | [TASK-101](tasks/TASK-101-face-pose-association.md) 人脸与姿态关联修正（D1） | blocked（等 TASK-102） | GZ-01 | L | 是 |
| 你 | 标注 26 段，约 2 小时 | 待前置（TASK-138、TASK-139 与正式区域） | — | — | — |
| — | 阶段 2 验收：离线门、作业数据真实 smoke、同步精度、修复前后对比 | 未开始 | — | — | Claude 执行 |

- TASK-131 排在最前：读取器不修好，任何作业数据都无法可靠处理。
- TASK-123 放在第 1 轮，让你在第 2 轮生成代理视频的同时画出区域。TASK-121 依赖同步代理视频与你的区域文件，所以标注在第 2 轮之后开始，与第 3 轮开发并行。
- 摄像机角色（你 2026-10-15 确认）：前方为カメラ2，右侧为カメラ1，全局为設備カメラ。所有工具按物理编号取文件，因为 2026-09-03 文件夹的文件名互换。
- 设计依据：[D1、D2 规范](../superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md)、[验证集规范 r2](../superpowers/specs/2026-10-15-workdata-validation-set-design.md)。
- 已撤回：原 TASK-122（单机门控评估脚本）与 TASK-110（修改单机门控默认值）。门控比较并入第 3 阶段的 TASK-143。

## 阶段 3：多摄像机注视区域推断（设计已批准）

设计：[多摄像机注视区域推断设计](../superpowers/specs/2026-10-15-multicamera-attention-design.md)。你已于 2026-10-15 批准 D13 至 D15。Claude 在阶段 2 验收时，按阶段 2 工具的实际输出格式把下列任务写成完整契约。开始第 3 阶段时请你决定：继续使用本分支，或从阶段 2 验收点新开分支与 draft PR。

| 任务 | 内容 |
| --- | --- |
| TASK-141 单机特征提取 | 在前方与右侧摄像机的同步代理上运行感知与 Gaze-LLE，导出头部姿态、in/out、热图区域质量；在全局摄像机上导出姿态关键点，并按你画出的区域计算双手所在区域 |
| TASK-142 区域融合与时序平滑 | 逐时间步分类，时序平滑，输出停留片段 |
| TASK-143 评估 | 按录制日期留一交叉验证；逐时间步与片段级指标；单机与融合消融；门控策略比较（原 D10） |
| TASK-144 统计报告与复核视频 | 每次录制的区域占比、时长分布、切换与离开工作统计；三视角拼接复核视频 |

## 阶段 4：工程加固（原阶段 3，无需新的科学决策）

| 任务 | 状态 | 问题组 | 要点 |
| --- | --- | --- | --- |
| TASK-003 打包修正 | proposed | GZ-06 | 新增 `gazelle/__init__.py`，`setup.py` 只含 `gazelle` 子包；环境内重装验证需你授权 |
| TASK-004 运行时边界加固 | proposed | GZ-09、C056、C032、C038、C057 | 帧尺寸一致性、拒绝清理含输入的目录、FFmpeg 不继承 stdin、不写 NaN、显式 CUDA 不可用时提前失败 |
| TASK-005 测试加固 | proposed | GZ-20 | `0.50` 边界、轴向射线、`torch.hub` 目录恢复、samples 守卫、管线级跟踪集成；读取器时间戳部分已并入 TASK-131 |
| TASK-006 文档同步批次 | proposed | GZ-17、GZ-10、GZ-12、GZ-14、GZ-15 | README_CN 省略、样例模板、射线键名、`--force-download` 范围与恢复、bridge 有效上限、`predict_frame` 默认状态 |
| TASK-007 研究脚本加固 | proposed | GZ-08 | VAT 预处理跨平台、评测严格加载、`hubconf.py` 安全加载、指标黄金值测试 |
| TASK-008 验收脚本与 CLI 易用性 | proposed | P2、P3、P5 | 一键离线验收脚本；拒绝带媒体后缀的 `--output-dir`；`run_config.json` 记录代码版本与关键依赖版本 |

## 阶段 5：多人同时推断

在单人区域推断稳定后立项。按你的回答，可以独立于 Multi-Pose 开发。候选内容：多主体身份（D11）、每人一条注视时间线、人与人之间的注视关系。

## 决策

| 决策 | 内容 | 状态与建议 |
| --- | --- | --- |
| D1 | 单人模式人脸与姿态关联 | 已批准，TASK-101 |
| D2 | 新轨迹首帧策略 | 已批准，TASK-102 |
| D3 | 子格头框（GZ-05） | 待决：预测记录增加 `head_map_empty`，不改框与状态 |
| D4 | 时间戳时钟（GZ-07） | **已批准**，并入 TASK-131 |
| D5 | 桥接与跟踪窗口（GZ-12） | 待决：两侧窗口由 `--head-track-max-gap-ms` 统一推导；多人桥接后空间去重 |
| D6 | 失败路径（GZ-13） | 待决：维持致命失败；JSON 加载期全量校验；删除后置；写完成标记 |
| D7 | 图像预测状态（GZ-14） | 待决：`predictions.json` 增加帧级 `status` |
| D8 | DINOv2 与 checkpoint 完整性（GZ-10、GZ-11） | 待决：固定 commit、校验权重 SHA-256、strict 校验移到替换前 |
| D9 | MediaPipe 阈值与裁剪（GZ-16） | 待决：冻结当前默认阈值；裁剪内 `num_faces=1` |
| D10 | 单机门控默认值（F1） | **暂停**：新目标下门控只影响特征；比较并入 TASK-143，在此之前不改 CLI 默认值 |
| D11 | 主体身份长期稳定（F4） | 待决，第 3、5 阶段一并考虑 |
| D12 | 目标场景验证集（F2） | **已批准 r2**：作业数据的连续片段区域标注，撤回 sample2 |
| D13 | 分析时间轴 | **已批准**：画面时钟上的 5 Hz，1080p 同步代理 |
| D14 | 区域类别与标注方式 | **已批准**：连续 60 秒片段，按变化点标注；类别由你在全局摄像机画面上画出的区域生成 |
| D15 | 融合方法 | **已批准**：逐时间步特征、可解释分类器、HMM 时序平滑，按录制日期留一评估；几何标定留作后续 |
| D16 | 切换到新环境 `Gazelle-next`（Python 3.14、PyTorch 2.14、MediaPipe 1.1.1 等） | **你已决定（2026-10-17）**：尽早切换；现有 `Gazelle` 原样保留作回退，项目改用 `Gazelle-next`。仓库侧由 TASK-137 完成。依据：[环境评估](evidence/2026-10-17-env-next-evaluation.md) |
| D17 | Gazelle 输入预处理移到推理设备（TASK-136） | **你已同意（2026-10-17）**：第 3 轮实施（排在 TASK-138 之后，以便先修复正式标注的阻塞问题）。管线实测 4K 每次调用由约 99 ms 降到 36 至 41 ms，输出等价 |
| D18 | 同步协议 r2：以前方摄像机 B 为基准，右侧 A 与全局 E 用画面运动校准偏移与漂移（TASK-139） | **待你决定，推荐批准。** 依据：[同步分析](evidence/2026-10-17-sync-analysis.md)，三机画面时钟各差最多约 3 秒，运动测量离散 0.02 至 0.07 秒。批准后 D13 的时间轴定义改为“以 B 的画面时钟为基准、内容校准后的 5 Hz” |
| P-merge | PR #2 至 #5 堆叠链 | 你已决定：项目达到目标功能后集中梳理合并 |
| P-pr | 阶段分支 draft PR | 你已批准 |
