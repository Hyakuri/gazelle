# TASK-102：新轨迹首帧立即确认（决策 D2）

状态：ready-for-review（2026-10-18 第 2 轮修复已提交；真实 smoke 计数预期差异待 Claude 判断，见 §2）
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

### 2026-10-17 实施与验证

- TASK-139 的三个低优先级 CPU 扫描继续运行期间，在同一主线程执行本任务；不依赖同步输出，没有子代理。原始数据和正式 ROI 未改动。
- 实现 `35a0a3a6973b62a4f5bf8f2f16d71a0b7c3514c0` — `Expose provisional heads on each track spawn frame`。11 文件：tracking/contracts/outputs、三组对应测试、usage docs 测试与四份用户文档。provider 已经通过 bridge 传递完整 perception，无须重复改写。
- 四类行分流；pending 保存像素 bbox 和 spawn 帧，帧差 ≤2；按 IoU 降序/public ID/candidate index 贪心一对一关联。已知→新确认→spawn 的处理顺序，输出仍按候选顺序。重复 spawn 保留最初 age 并刷新 pending；失效、reset、close 清空 pending。provisional 不创建或刷新桥接，序列化始终是 bool。
- 只读检查实际 `Gazelle-next` 的 trackers 2.6.1：高分匹配使用 `>=`、新 spawn 返回 −1，当前三项配置仍满足分类依据；新版未确认轨迹漏检后可能更早被清理，适配层 re-spawn 关联同样覆盖该情形。未访问运行中上游 tracker 的私有属性。

#### 命令和结果

解释器 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，字节码 `%TEMP%\gazelle-task-102-pycache`，输出 `gazelle_runs\task-102\`。

| 命令 | 结果 |
| --- | --- |
| 新 spawn 测试和真实 ByteTrack 两帧测试（修改前） | exit 1，2 methods / 3 errors，均因首帧为空而 IndexError，实际复现 |
| `python -m unittest tests.test_head_tracking tests.test_mediapipe_head_provider tests.test_outputs -q` | 首次 96 tests 中仅原 tracking schema 断言失败；按批准字段更新后通过 |
| 聚焦五模块，加同期 PTS 修复两模块 | exit 0，179 tests / 3.498s / 0 skip |
| `python -m compileall main.py gazelle tests tools` | exit 0 |
| `python -m unittest discover -s tests -v` | exit 0，633 tests / 10.938s / 0 skip；含同期 TASK-139 相等 PTS 修复，尚不含其后 TASK-002 新测试 |
| `python main.py --help`、`python main.py --list-models`、`git diff --check` | 均通过 |
| `python ...\task-102\smoke.py` | 最终 exit 0；转换 + 四次模型运行均成功 |
| 四个渲染结果 `ffprobe -v error -count_frames -show_streams -of json <video>` | exit 0，全部 640×360、30 帧；A 为 H.264，B 为 MPEG-4 |

首次 smoke 把内部字段名误当 CLI 选项（`--draw-face-pose-ray` 等），在参数解析时 exit 2、`NETWORK_AUDIT=[]`，尚未加载模型。依据实际 parser 改为 `--face-pose-ray --pose-head-ray --head-box --face-box`，旧错误日志保留为 attempt 文件。没有为通过而修改环境。非致命输出：坏 MP4 单测提示、xFormers 不可用和 MediaPipe 日志初始化提示。

#### 真实对照

从自带 `assets/Sunny_1.gif` 用 FFmpeg `-vf fps=30,scale=640:360 -frames:v 30 -an -threads 2 -c:v libx264 -pix_fmt yuv420p` 生成仓库外 `sunny.mp4`。基线为 `git archive 3d07444` 的只读源码快照，之后为 `35a0a3a`；同一 Gazelle-next 环境与缓存，四次连续运行。

公共参数：`--input <sunny.mp4> --output-dir <external> --cache-dir <repo>\models --device cuda --head-source mediapipe --max-frames 30 --save-rendered --face-pose-ray --pose-head-ray`。A 加 `--max-heads 1 --video-codec avc1`；B 加 `--max-heads 2 --video-codec mp4v --gazelle-head-mode all --gaze-render-mode all-predictions --head-box --face-box`。完整 argv/退出码见 `commands.json`，结果见 `comparison.json`。

| 模式 | no_head（前→后） | 不同 person_id 数（前→后） | tracked_only 行（前→后） | 修复后 provisional 行 |
| --- | --- | --- | --- | ---: |
| A 保守 | 1 → 0 | 2 → 4 | 3 → 0 | 4 |
| B 诊断 | 1 → 0 | 2 → 3 | 4 → 3 | 3 |

两组各 30/30 observation/prediction 行；修复后第 0 帧已有头且 provisional=true。A gaze 为 ok 15 / no_gaze 15，B 为 ok 30。所有 tracking.provisional 都是 bool，全部 tracked_only 为 false。ID 数增加反映原先被隐藏的短暂 spawn，不是身份质量改善的证明。历史 2026-10-14 基线 A 为 ok14/no_gaze15/no_head1、B 为 ok29/no_head1；本次采用同环境、同新生成片段的基线，不能把历史环境和本次所有数值视为严格可比。

#### 复核、活动和限制

- 反证：同帧双 spawn 一对一；相同 IoU 以 ID/候选索引决定；远框及过期 pending 分配新 ID；低分 −1 不占 ID；重新 spawn age 不重置；provisional 下一帧漏检没有幽灵桥接。真实 trackers 两帧集成测试通过，无 skip。
- 真实 CUDA、MediaPipe CPU、FFmpeg 转码/H.264 最终编码及 ffprobe 均发生。启动前检查 GPU 空闲；Python audit 阻止 Torch Hub 请求后缓存回退成功，无下载、缓存 size/mtime 改动、安装或 Conda 修改。原生 MediaPipe 遥测不在 Python audit 覆盖范围。
- A 级：复用既有 fusion `_bbox_iou`，保持算法一致；以传入 tracker 的像素框关联。TrackedHeadCandidate.provisional 默认 false，兼容既有构造；provider 无额外代码改动。
- 范围外：无；TASK-139 相等 PTS 修复单独提交为 `47694e5`。四份用户文档已同步，schema 测试锁定 tracking.provisional。
- B 级：待独立审查拥挤/错配风险、ID 数变化与真实重复 spawn。TASK-101 的跨人融合/候选池问题仍不在本任务范围内。C 级：无。
- 已执行全部契约检查；没有运行可选作业视频补充 smoke。所有媒体和结果在仓库外，不上传。

**已实施、已静态检查、已实际运行；待 Claude 独立审查和用户独立 checkout 验收。**

### 2026-10-18 第 2 轮修复（Codex）

- 按 §3 修复 GZ-30：单人模式只有胜出 perception 已确认时才调用 `retain_person_ids`；provisional 胜出不修剪已有已确认桥接。未改变仲裁顺序、有效性、过期时间、Gazelle selector 或多人的行为。
- 新增 P0/f0–f4、P1/provisional/f5、f6–f8 漏检回归；修改前实际失败（期望 P0、实际空），修改后 f6–f8 均为 P0/`tracked_only` 且 provisional=false。另新增不同 bbox、颠倒候选顺序的 IoU 关联测试，public ID 随 bbox 而非候选顺序关联；新测试使用展开的代码风格。
- 四份用户文档及 usage 检查同步：provisional 在 `all` 下可选中 pose-only、保守模式有有效面部射线也可进入 Gazelle；一帧 spawn 增加 ID 数，下游身份统计先排除 `tracking.provisional=true`。修正单人桥接修剪说明。
- 更正上一轮报告中的推断：已只读核对 trackers 2.6.1 的 `ByteTrackTracklet.__init__`，spawn 连续计数从 **1** 开始，能撑过一帧漏检。“新版未确认轨迹漏检后可能更早被清理”不成立，不作为本次实现依据。

#### 检查与真实活动

解释器仍为 `Gazelle-next`，字节码 `%TEMP%\gazelle-task-102-r2-pycache`；日志、诊断与媒体仅在仓库外 `gazelle_runs/task-102-r2/`。

| 命令 | 结果 |
| --- | --- |
| 两个新增 method 的 red 检查 | 2 tests，桥接回归失败，IoU 测试通过；`regression-red.log` |
| `python -m unittest tests.test_mediapipe_head_provider tests.test_head_tracking -v` | exit 0，64 tests / 6.278s / 0 skip |
| `python -m compileall main.py gazelle tests tools` | exit 0 |
| `python -m unittest discover -s tests -v` | exit 0，667 tests / 13.541s / 0 skip；包含同期 TASK-140 的来源变更拒绝检查 |
| `python main.py --help`、`python main.py --list-models`、`git diff --check` | 均 exit 0 |
| `python .../task-102-r2/smoke.py` | 子进程模型运行 exit 0 / 26.027s；外围“tracked_only 数应恢复”断言 exit 1，原因如下，保留原日志与断言 |
| `ffprobe -v error -count_frames -show_streams -of json <rendered.mp4>` | exit 0，H.264、640×360、30 帧 |
| `python .../task-102-r2/bridge_diagnostic.py` | exit 0，真实 MediaPipe 30 帧仲裁前诊断、真实 ByteTrack 的合成 P0/P1 回归均通过 |

smoke A 复用原 30 帧 `sunny.mp4`，SHA-256 `d342b0ea8304d7bf46bc9276b6a22f50c420e4d349e6fad01c85a6075d74933a`。公共 argv 为 `--input <sunny.mp4> --output-dir <task-102-r2/A-after> --cache-dir <repo>/models --device cuda --head-source mediapipe --max-frames 30 --save-rendered --face-pose-ray --pose-head-ray --max-heads 1 --video-codec avc1`，通过已有 task-136 的离线审计 wrapper 调用。输入未重编码，旧对照未覆盖。

- GPU 前检 4563/16376 MiB、利用率 4%；发生真实 Gazelle CUDA 推理、MediaPipe CPU 和 FFmpeg H.264 编码。30/30 observation/prediction 行及读写帧一致。Python audit 阻止一次 `urllib.Request`，随后 Torch Hub 缓存回退成功；未下载，缓存大小/mtime 无变化，未修改环境。MediaPipe 原生遥测不由此 Python audit 证明。后续 provider-only 诊断不构建 Gazelle、不编码视频，Python 网络事件为空。
- 非致命输出：xFormers 可选路径不可用、MediaPipe 日志/feedback/alignment 提示、坏 MP4 离线回归提示、Git LF/CRLF 提示。没有把这些提示当成推理或测试失败。

#### smoke A 预期差异与反证（交 Claude 判断）

三份输出逐帧比较见 `comparison.json`。原始基线 A 的 `tracked_only=3`，上一轮 A 为 0，本次修复后仍为 **0**；no_head=0、不同 ID=4、provisional=4、预测 ok/no_gaze=15/15 均与上一轮相同。不能报告“smoke A 的 tracked_only 输出行恢复”。

原因已用实际帧核实：原始基线 f6、f7、f13 的三个桥接输出，分别被 TASK-102 允许输出的 pose-only/face-only/pose-only provisional 头替代；下一帧有当前观测，没有“临时头之后继续无观测”的空帧。按现有仲裁顺序，修复不应把这些实际观测改回桥接输出。

为区分输出仲裁与内部桥接丢失，额外运行真实 MediaPipe provider 并记录 bridge 返回值：本次 f7 在仲裁前同时含 P2/face_only/provisional 和 **P0/tracked_only**，f6、f7、f13 均未调用 retain。另在真实 trackers 2.6.1 上运行契约的 P0/f0–f4、远离 P0 的 P1/f5、f6–f8 空输入：原修剪行为为 3 个空结果，新行为为 **3 个 P0/tracked_only**。证据为 `bridge-diagnostic.json`，没有访问上游 tracker 私有字段。

- A 级：最小条件修复；测试中使用展开布局；外部诊断区分仲裁前状态与公开输出。无范围外实现。
- B 级：请求 Claude 以契约的 P0/P1 回归和真实 A 的仲裁前桥接状态验收 GZ-30；STATE 所写“smoke A 的 tracked_only 行恢复”与原 A 逐帧输入不符。未擅自改变 selector 或研究验收标准。TASK-101 继续等待本任务审查通过。
- C 级：无。未运行本轮不要求的 B 重跑或作业视频补充 smoke。
- **已实施、已静态检查、已实际运行；上述预期差异待 Claude 独立判断，用户独立 checkout 验收未完成。**
- 提交并推送：`97ef104974da58533446a7dc5b9170fa887f3b5d` — `Preserve confirmed bridges when provisional heads win`。双语报告见 [PR #6 评论](https://github.com/Hyakuri/gazelle/pull/6#issuecomment-6235613775)。运行配置确认模型为 `gazelle_dinov2_vitb14_inout`，MediaPipe `pose_model=full`，selector=`eligible`，30 帧时间戳全部来自 container，无修复或 FPS 回退。

## 3. 审查结论（Claude 追加）

### 2026-10-17 第 3 轮审查（Claude）

- **审查目标**：`35a0a3a`（实现）与 `bc77f0f`（报告），在 HEAD `f0c4311` 上审查。
- **独立复跑结果**：
  - 完整离线门 643 tests，0 skip。
  - 一份只读代码审查（子代理）：聚焦测试 181 项通过，含真实 trackers 2.6.1 的集成测试；另用真实 ByteTrack 做了探针。
  - Claude 亲自核对了代码（`provider.py:177-181`）和 Codex 两组真实 smoke 的逐帧输出。
- **已核实**：
  - 四类行的判据与上游 2.6.1 语义一致：高低分以 `>=` 划分，spawn 返回 −1，置信度达到激活阈值才建轨迹。
  - pending 窗口 ≤ 2 帧；贪心一对一关联，排序键为（−IoU, pid, cidx）；年龄从 spawn 帧计；输出顺序与 ID 规则不变。
  - 桥接不为 provisional 创建或刷新状态；`tracking.provisional` 始终为布尔值；四份文档一致。
- **必须修复**：
  1. **单人模式下，provisional 头会删掉已确认轨迹的桥接状态。**
     - 机制：`arbitrate_perceptions` 把任何观测行（包括 provisional）排在 `tracked_only` 之前。当 `max_heads == 1` 时，`retain_person_ids` 只保留被选中的那一个 ID。一帧的新 spawn 胜出后，已确认轨迹的桥接就被丢弃。
     - 子代理用真实 ByteTrack 复现：P0 在 f0–f4 可见、f5–f8 漏检，f5 出现一帧 spawn。修改前 f5–f8 都是 P0/tracked_only；修改后 f5 是 provisional，f6–f8 变成 `no_head`。
     - Codex 的 smoke A 中，`tracked_only` 由 3 行变为 0 行，原因相同。
     - 这违背规范“provisional 不影响桥接”的本意，而且发生在作业数据最常用的单人保守模式里。
     - 要求：provisional 头胜出时，不得删除已确认轨迹的桥接状态；只有胜出者是已确认轨迹时才修剪。
     - 测试：用上面的场景，修改后 f6–f8 恢复为 P0/tracked_only。
- **应修**：
  2. **文档**：在四份文档中写明以下两点。
     - provisional 头可以被选中送入 Gazelle：诊断模式 `all` 下即使只有姿态也会被选中；保守模式下若有有效面部射线也会被选中。
     - 只出现一帧、之后未确认的 spawn 会增加不同 `person_id` 的数量。smoke A 由 2 个增至 4 个，B 由 2 个增至 3 个，新增的几乎都是未确认的一帧 spawn。下游统计身份时应先排除 `tracking.provisional` 为 true 的行。
  3. 小项：
     - 关联测试只用了相同的框，证明不了 IoU 优先于候选顺序；子代理用真实 ByteTrack 交换候选顺序，关联正确。
     - 新测试的代码风格比文件其余部分紧凑。
     - 报告中“新版未确认轨迹漏检后可能更早被清理”与 2.6.1 不符：spawn 的计数从 1 开始，能撑过一帧漏检。这不影响结果。
- **结论**：**changes-requested**（必须修复 1 项）。按“第 2 轮修复”在本文件追加报告，排入第 4 轮。TASK-101 继续等本任务通过。

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
