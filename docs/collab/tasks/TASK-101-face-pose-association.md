# TASK-101：人脸与姿态关联修正与连续性选择（决策 D1）

状态：blocked（等待 TASK-102 审查通过）
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
问题来源：GZ-01（主线程新发现，见分析报告 §5）。设计：[2026-10-15 规范 §4](../../superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md)。
授权：用户 2026-10-15 批准 D1 按 Claude 的推荐执行。

## 1. 契约

### 目标

任何模式下都不再把一个人的脸与另一个人的姿态融合成同一个头框；单人模式在多人入镜时稳定地跟住同一个主体。

### 必须实现

按规范 §4 实现，要点如下：

1. **候选池**：新增唯一定义的 `candidate_pool_size(max_heads)`，返回 `max(max_heads, 3)`。`MediaPipeBackend` 取前 `pool` 个人脸检测做 landmark 裁剪，`PoseLandmarkerOptions.num_poses = pool`；`FaceLandmarkerOptions.num_faces` 不变。
2. **关键点包含约束**：`associate_face_pose` 在原几何门控之外，增加规范 §4.2 的锚点测试（鼻点；否则至少两个头部关键点；否则双肩；否则失败）。
3. **统一匹配**：删除 `build_head_candidates` 中 `max_heads == 1` 的特殊分支，所有情况都走配对匹配；对外签名与“返回前 `max_heads` 个”的语义不变。
4. **选择**：`arbitrate_perceptions` 增加可选参数 `previous_selection`，按规范 §4.4 的三步确定选择：空间连续（有新观测）、身份连续（含桥接）、按原优先级补足；返回保持原顺序。
5. **provider**：视频模式把整个候选池交给 tracker；每帧选择后记录 `(person_id, head_bbox)`，并对所有 `max_heads` 调用 `bridge.retain_person_ids`。图像模式先按优先级选择，再把 `person_id` 重新编号为 `0..n-1`。
6. `HeadPerception` 的 `provisional`（TASK-102 引入）在选择过程中原样保留。

### 非目标

- 不改资格判定、in/out 阈值、保守门控（决策 D10）。
- 不做主体长期身份稳定或躯干优先跟踪（决策 D11）。
- 不改 `FaceLandmarkerOptions.num_faces`（决策 D9）。
- 不改跟踪参数与桥接参数（决策 D5）。
- 不新增 CLI 选项；不改 `run_config.json` 键集合。

### 依据材料

- 规范：§1.2、§4、§6、§7、§8、§9。
- 代码：`gazelle/runtime/perception/fusion.py`（全文）、`gazelle/runtime/perception/mediapipe_backend.py:64-121`、`:279-443`、`gazelle/runtime/perception/provider.py:16-232`、`gazelle/runtime/perception/gaze_policy.py:64-89`、`gazelle/runtime/perception/contracts.py`。
- 受影响测试：`tests/test_head_fusion.py`（`associate_face_pose` 与 `fuse_head_candidates` 用例需补姿态关键点；`test_one_person_selection_is_deterministic`；`test_inconsistent_face_pose_selects_higher_quality`）；`tests/test_mediapipe_backend.py`（检测截断与 `num_poses`）；`tests/test_mediapipe_head_provider.py`（`test_single_person_post_bridge_arbitration_prunes_stale_identity`、图像编号）；`tests/test_gaze_policy.py`（仲裁用例）。
- 基线数据：`C:\Users\yun\Documents\Claude_Code\_handoff_archive\smoke-20261014\`。

### 不可变约束

- AGENTS.md 的 Runtime Invariants 与 Research And Data Integrity 全部保持。
- 送入 `GazellePredictor` 的头框仍为规范化、有限、裁剪后非空，并与 `person_id` 顺序对齐。
- `gaze_eligible` 仍是保守建议，`gazelle_selected` 仍记录实际调度。
- 默认测试隔离规则不变。

### 允许动作

- 修改：上面“依据材料”列出的四个代码文件与 `contracts.py`、对应测试、`tests/test_usage_docs.py`、四份用户文档的相关段落。
- 按协作方案 §4 在阶段分支提交并推送。
- 运行离线验证与下方真实 smoke（仅缓存资源，输出写到仓库外）。

### 禁止

新建分支或 PR、合并、force push；修改 Conda 环境；下载；修改上面未列出的文件；未经用户许可处理其独立目录中的视频。

### 验收标准

1. 合成场景：A、B 两人相邻，最高置信的人脸属于 A、最高置信的姿态属于 B。输出中不存在横跨两人的融合框；A 的姿态存在时与 A 的脸融合。
2. 锚点测试四个分支各有用例：鼻点在内与在外、两个头部关键点、只有双肩、没有可用关键点。
3. 连续选择：两个候选置信度逐帧交替领先时，单人模式输出始终是同一人；同一物理位置出现新的 tracker 身份时，新观测取代旧身份的 `tracked_only`；主体被遮挡时保持为 `tracked_only` 直到桥接过期，之后才切换。
4. 图像模式输出的 `person_id` 从 0 连续编号。
5. backend 用例确认人脸裁剪数量与 `num_poses` 都等于候选池大小。
6. 四份文档说明锚点规则、至少 3 个候选、连续选择规则、视频 ID 不保证从 0 开始；`tests/test_usage_docs.py` 锁定对应 token。
7. 完整离线门通过，无失败，无新增 skip。
8. 真实 smoke（Sunny 30 帧视频，video A 与 video B 参数；外加 `assets/the_office.png`）：
   - 姿态鼻点落在人脸派生头框之外的 `face_pose` 感知数为 0。
   - 报告选中主体切换次数、`gaze_eligible` 帧数、Gazelle 推理次数、in/out 分布，并与 2026-10-14 基线对比。
   - 统计脚本放在仓库外或 `docs/collab/evidence/` 的说明中给出命令，不提交生成的媒体与 JSONL。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-101-pycache"
& $py -m unittest tests.test_head_fusion tests.test_mediapipe_backend tests.test_mediapipe_head_provider tests.test_gaze_policy tests.test_video_pipeline tests.test_image_pipeline tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。改变感知融合语义、选择策略与核心算法。
- 需真实 smoke：是。
- 文档同步：需要。
- 风险与回退：连续性可能在主体被遮挡时短暂保留旧主体；多人入镜时选中的人可能与旧版本不同。回退方式是 `git revert` 本任务的提交。
- 依赖：TASK-102 已审查通过。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 证据类型：
- 真实 smoke 结果与基线对比：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
