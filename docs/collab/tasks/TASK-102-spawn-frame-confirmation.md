# TASK-102：新轨迹首帧立即确认（决策 D2）

状态：ready
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
问题来源：GZ-03（登记表 C007、C011）。设计：[2026-10-15 规范 §3](../../superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md)。
授权：用户 2026-10-15 批准 D2 按 Claude 的推荐执行。

## 1. 契约

### 目标

视频中每条新轨迹的首帧（包括第 0 帧）立即输出观测到的头部，并在上游 ByteTrack 正式分配 ID 后沿用同一个 `person_id`。输出增加 `tracking.provisional`，让分析可以识别尚未确认的首帧。

### 必须实现

按规范 §3 实现，要点如下：

1. `ByteTrackHeadTracker._map_tracked_candidates`（`gazelle/runtime/perception/tracking.py`）区分四类行：已知、新确认、spawn、低分未匹配。spawn 行的判据是 raw ID 为 `-1` 且候选置信度 ≥ `track_activation_threshold`。在 `_TRACKER_CONFIGURATION` 旁注明这一判据依赖的三个配置值。
2. 维护 `pending_spawns`。有效窗口为当前帧号减 spawn 帧号不超过 2。新确认行与 spawn 行按 IoU ≥ `minimum_iou_threshold` 做一对一贪心关联，排序键为（IoU 降序、public ID 升序、候选索引升序）。
3. 关联后沿用 spawn 帧作为首帧，`track_age_frames` 从 spawn 帧开始计数。
4. `TrackedHeadCandidate` 增加 `provisional: bool`；`HeadPerception` 增加 `provisional: bool = False`。
5. `ShortOcclusionBridge` 不为 provisional 候选创建或刷新桥接状态。
6. `head_observations` 的 `tracking` 对象增加 `provisional`，始终输出布尔值。图像模式与 `tracked_only` 恒为 `false`。
7. `reset()`、`close()` 与 tracker 失效时清空 `pending_spawns`。
8. 不读取、不修改上游 tracker 的任何私有属性。

### 非目标

- 不改 `_TRACKER_CONFIGURATION` 的任何数值。
- 不改桥接时长、衰减常数、`--head-track-max-gap-ms` 的含义。
- 不做 D1 的候选池与选择逻辑（TASK-101）。
- 不新增 CLI 选项。

### 依据材料

- 规范：`docs/superpowers/specs/2026-10-15-face-pose-association-and-track-confirmation-design.md` §1.1、§3、§6、§8。
- 代码：`gazelle/runtime/perception/tracking.py`（全文）、`gazelle/runtime/perception/contracts.py:108-136`、`gazelle/runtime/perception/provider.py:152-182`、`gazelle/runtime/perception/outputs.py:134-160`。
- 上游语义：`C:\Users\yun\anaconda3\envs\Gazelle\Lib\site-packages\trackers\core\bytetrack\tracker.py` 的 `update`、`_spawn_new_tracks`，以及 `bytetrack\utils.py` 的 `_get_alive_tracklets`。
- 受影响测试：`tests/test_head_tracking.py`（`FakeTracker._echo` 在 `:90-99`；`test_filters_untracked_sentinel_and_returns_stable_candidates` 在 `:370`；`test_untracked_sentinel_never_consumes_public_id` 在 `:639`），`tests/test_mediapipe_head_provider.py`，`tests/test_outputs.py`，`tests/test_usage_docs.py`。

### 不可变约束

- AGENTS.md 的 Runtime Invariants 与 Research And Data Integrity 全部保持。
- 每帧 `person_id` 唯一且非负；`frame_index` 严格递增检查与时间戳单调检查不变。
- 默认测试不联网、不下载、不使用 CUDA、不调用真实 FFmpeg。
- `run_config.json` 的键集合不变。

### 允许动作

- 修改：`gazelle/runtime/perception/tracking.py`、`gazelle/runtime/perception/contracts.py`、`gazelle/runtime/perception/provider.py`（仅为传递 `provisional`）、`gazelle/runtime/perception/outputs.py`、对应测试文件、`tests/test_usage_docs.py`、四份用户文档的相关段落。
- 按 [协作方案](../COLLABORATION_PLAN_CN.md) §4 在阶段分支提交并推送。
- 运行下方离线验证；运行下方真实 smoke（已获本地运算授权，仅用缓存资源，输出写到仓库外）。可只读使用作业数据补充真实 smoke：TASK-131 合入后，用 FFmpeg 流复制从 MP4 分段或 TASK-134 的代理视频截取 15 秒片段到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\` 再运行，不写入 `E:\Gazelle_Workdata\`。sample1 只作冒烟输入；sample2 不属于目标场景，不再使用。运行任何 GPU 推理前按协作方案 §5 检查空闲显存。

### 禁止

新建分支或 PR、合并、force push；修改 Conda 环境；下载；修改上面未列出的文件；写入或修改用户独立目录或 `E:\Gazelle_Workdata\` 中的任何文件。

### 验收标准

1. 复刻上游语义的 fake tracker 下：第 0 帧输出该头，`provisional` 为 true、`track_age_frames` 为 1；第 1 帧同一 `person_id`，`provisional` 为 false、`track_age_frames` 为 2。
2. spawn 后漏检一帧、第 2 帧才确认时，仍关联到同一 `person_id`。
3. 同帧两个 spawn 一对一关联；与所有 pending spawn 的 IoU 都低于 0.20 的新 raw ID 分配新 `person_id`。
4. 置信度低于 0.50 的 `-1` 行从不占用 `person_id`（替代原 `test_untracked_sentinel_never_consumes_public_id` 的含义，并改名）。
5. provisional 头在下一帧漏检时，不产生 `tracked_only` 行。
6. 在 `trackers` 可导入时才运行的集成测试：真实 `ByteTrackHeadTracker(30.0)` 对置信度 0.8 的同一候选连续两帧，第 0 帧与第 1 帧都输出 `person_id == 0`，第 0 帧 provisional。
7. `head_observations` 的 `tracking.provisional` 在图像、视频、`tracked_only` 三种情况下都输出且取值正确。
8. 四份文档说明第 0 帧与新轨迹首帧的新行为和 `tracking.provisional` 字段；`tests/test_usage_docs.py` 在两份 USAGE 中锁定 `tracking.provisional`。
9. 完整离线门通过：无失败，skip 只允许增加第 6 条集成测试在缺包时的那一个。
10. 真实 smoke：用 `assets/Sunny_1.gif` 转出的 30 帧视频，按 2026-10-14 证据中 video A 与 video B 的参数各跑一次。第 0 帧不再是 `no_head`；新轨迹首帧 `provisional` 为 true；报告 `no_head` 帧数、不同 `person_id` 数、`tracked_only` 行数，并与基线对比。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-102-pycache"
& $py -m unittest tests.test_head_tracking tests.test_mediapipe_head_provider tests.test_outputs tests.test_video_pipeline tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

真实 smoke 参考 `docs/collab/evidence/2026-10-14-destination-acceptance.md` 的 video A 与 video B 命令，输出根目录用 `$env:TEMP\gazelle-task-102\`。

### 其他

- 需独立审查：是。改变跟踪身份语义与输出 schema。
- 需真实 smoke：是。
- 文档同步：需要，四份文档加 `tests/test_usage_docs.py`。
- 风险与回退：IoU 关联在拥挤场景可能错配；一帧误检会出现一帧。回退方式是 `git revert` 本任务的提交。
- 依赖：无。作业数据补充 smoke 需要 TASK-131 已合入。

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
