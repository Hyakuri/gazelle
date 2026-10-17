# Gazelle 代码库深度分析（2026-10-14）

协调者：Claude。基线：`feature/mediapipe-head-tracking` @ `bbec056`，加上交接包恢复的未提交文档 overlay。
本文是只读分析结论，不是实施记录；所有改动建议都要经任务契约（`docs/collab/tasks/`）执行。
全部问题见 [问题登记表](2026-10-14-issue-register.md)，执行计划见 [ROADMAP](../ROADMAP.md)。

## 0. 结论摘要

- **工程质量整体较高。** 运行时由冻结 dataclass 契约串联，边界校验严格，下载与 H.264 终结都走暂存加原子替换，视频全程流式，Gazelle 模型懒构建。531 个离线测试 3 秒跑完，文档契约测试锁定了 48 个 CLI 选项与 47 个配置字段。
- **AGENTS.md 的不变量在成功路径上大多成立。** 分析代理共做 228 项核对：156 项成立、10 项存疑、3 项不成立、59 项不适用。
- **未发现 P0。** 两个 P1 都出在感知前端的几何语义，且都有真实运行数据佐证：
  - **GZ-01** 默认单人模式会把一个人的脸和另一个人的姿态融合成一个头框送进 Gazelle。本次 30 帧样例的 14 次推理里有 12 次用的是横跨两人的头框。
  - **GZ-02** 面部参考射线的垂直方向与已批准规范相反，低头时射线指向上方。
- 这两项与交接文档记录的“误导性视线目标”方向一致，但只是可能来源之一，尚未在你的真实作业视频上验证。
- 其余重要问题：视频首帧丢失（GZ-03）、`--overwrite` 先删后验（GZ-04）、子格头框静默退化（GZ-05）、打包不可用（GZ-06）、时间戳时钟（GZ-07）、研究脚本在 Windows 不可用（GZ-08）。

## 1. 方法与证据等级

| 步骤 | 内容 | 结果 |
| --- | --- | --- |
| 迁移验收 | Gate A 源码身份、Gate B 离线门、Gate C 真实 smoke | 全部通过，见 [验收证据](../evidence/2026-10-14-destination-acceptance.md) |
| 子系统读取 | 10 个只读代理，各自完整阅读一个子系统及其测试 | 75 个去重问题 |
| 反证复核 | 每个问题配一个独立复核代理，默认倾向驳回 | 60 确认，15 驳回 |
| 完整性批评 | 1 个代理寻找跨模块覆盖缺口 | 6 个缺口 |
| 补充调查 | 6 个代理补读缺口并复核 | 合计 104 个问题：87 确认，17 驳回 |
| 主线程综合 | Claude 亲自复现关键结论、用实测数据核对、完成综合 | 6 条关键结论全部复现，另有 1 条新发现（GZ-01） |

本文使用以下证据词：

- **已实际运行**：来自真实 CUDA、MediaPipe、FFmpeg 运行的数据。
- **主线程复现**：Claude 在主线程用离线代码复现，不构建模型、不联网。
- **复核确认**：读取代理报告且独立复核代理未能驳回。这是同一产品内的交叉检查，不等同于独立验收。
- **推断**：基于本仓库与上游源码的推理，未经运行验证。

所有代理均为只读，未修改仓库。原定的综合代理因用量限额失败，综合由主线程完成。

## 2. 系统概览与端到端数据流

Gazelle 由两层组成。底层是上游 Gaze-LLE：冻结的 DINOv2 骨干加轻量 transformer 解码器，为每个人输出 64×64 heatmap 和可选 in/out 分数。上层是本 fork 新增的本地运行时：头部来源、感知融合与跟踪、调度、输出与渲染。

**图像路径**（`run_image_pipeline`）：

1. `load_image_rgb` 读 RGB 图像。
2. `create_output_dir` 做输出冲突检查；`--overwrite` 时递归删除旧目录。
3. `build_head_provider_from_config` 构造 none、static、json 或 mediapipe provider。
4. MediaPipe 时依次执行 `backend.observe`、`build_head_candidates`（融合）、按序分配 `person_id`、`arbitrate_perceptions`、`annotate_gaze_eligibility`。
5. `select_gazelle_head_indices` 按 `--gazelle-head-mode` 选出真正送入 Gazelle 的子集。
6. 写 `head_observations.json`，同时记录保守建议 `gaze_eligible` 与实际调度 `gazelle_selected`。
7. 有选中头时才懒构建 `GazellePredictor`，`predict_frame` 后由 `apply_prediction_gaze_status` 按 in/out 阈值分类。
8. 可选保存 heatmap `.pt` 与渲染图，最后写 `predictions.json` 与 `run_config.json`。

**视频路径**（`run_video_pipeline`）：

1. avc1 时先探测 FFmpeg；随后打开 `VideoFrameReader`、处理输出目录、解析 FPS、构造 provider（视频模式含 ByteTrack 与 `ShortOcclusionBridge`）。
2. 每帧由 reader 产出帧索引、毫秒时间戳与 RGB 图像。provider 每帧都运行；MediaPipe VIDEO 模式要求取整后的毫秒时间戳严格递增。tracker 分配 `person_id`，bridge 在默认 500 ms 内为短暂丢失的人发射 `tracked_only`，再仲裁到 `--max-heads`。
3. 每帧先写一行 `head_observations.jsonl`。状态优先级为 `skipped` > `no_head` > `no_gaze` > `ok`。再写一行 `predictions.jsonl`，可选渲染并写帧。
4. 循环结束写 `run_config.json`、关闭资源；avc1 时转码（NVENC 优先，libx264 回退）并原子发布。

## 3. 模块地图

| 模块 | 职责 | 关键入口 | 主要测试 |
| --- | --- | --- | --- |
| `main.py`、`runtime/cli.py` | 参数解析与路由：list-models 优先于 prepare-only，再优先于 input | `build_parser`、`parse_runtime_config`、`main` | `test_runtime_cli` |
| `runtime/config.py` | 47 字段冻结配置与字段级校验 | `RuntimeConfig.validate`、`from_args` | `test_runtime_cli` |
| `runtime/model_registry.py` | 4 个模型的静态元数据与 checkpoint 候选 | `get_model_spec`、`format_model_table` | `test_model_registry` |
| `runtime/resources.py` | 缓存目录、checkpoint 暂存下载与原子替换、strict 校验 | `resolve_runtime_checkpoint`、`prepare_runtime_resources` | `test_resources` |
| `runtime/environment.py` | DINOv2 构建期 xFormers/Triton 作用域开关与同进程冲突守卫 | `configure_dinov2_model_construction` | `test_predictor`、`test_resources` |
| `runtime/predictor.py` | 模型边界：bbox 规范化、多人 `bbox=None` 拒绝、输出形状校验 | `GazellePredictor.from_checkpoint`、`predict_frame` | `test_predictor` |
| `runtime/geometry.py` | bbox 有限性、顺序、裁剪、最小尺寸，像素与归一化互转 | `sanitize_normalized_bbox` | `test_geometry` |
| `runtime/heads.py` | none、static、json 三种 provider | `StaticHeadProvider`、`load_json_head_provider` | `test_heads` |
| `runtime/media.py` | 图像读取、OpenCV 流式读写、FPS 解析 | `VideoFrameReader`、`VideoFrameWriter` | `test_media` |
| `runtime/pipeline.py` | 图像与视频编排、输出目录、状态判定、资源清理 | `run_image_pipeline`、`run_video_pipeline` | `test_image_pipeline`、`test_video_pipeline` |
| `runtime/outputs.py` | 预测 JSON/JSONL、`run_config.json`、heatmap 保存 | `JsonlWriter`、`prediction_frame_to_json_dict` | `test_outputs` |
| `runtime/renderer.py` | PIL 叠加渲染：heatmap、箭头、峰值、感知层、射线 | `PredictionRenderer.render` | `test_renderer` |
| `runtime/ffmpeg.py` | FFmpeg 能力探测、H.264 转码、临时文件 | `detect_ffmpeg_capabilities`、`transcode_h264` | `test_ffmpeg` |
| `perception/contracts.py` | 感知数据契约与枚举 | `HeadPerception`、`HeadFrameResult` | `test_perception_contracts` |
| `perception/resources.py` | MediaPipe 资产：固定 SHA-256、锁、原子替换 | `prepare_mediapipe_resources` | `test_mediapipe_resources` |
| `perception/mediapipe_backend.py` | 三个 MediaPipe Task 封装、裁剪与 landmark 回映、矩阵转欧拉角 | `MediaPipeBackend.observe` | `test_mediapipe_backend` |
| `perception/fusion.py` | face/pose 合成头候选、一致性门控与匹配 | `build_head_candidates` | `test_head_fusion` |
| `perception/reference_rays.py` | 两条未标定的 2D 参考射线 | `estimate_face_pose_reference_ray`、`estimate_pose_head_reference_ray` | `test_reference_rays` |
| `perception/tracking.py` | ByteTrack 适配与短遮挡桥接 | `ByteTrackHeadTracker`、`ShortOcclusionBridge` | `test_head_tracking` |
| `perception/gaze_policy.py` | 保守资格判定、仲裁、诊断选择器、in/out 分类 | `annotate_gaze_eligibility`、`select_gazelle_head_indices` | `test_gaze_policy` |
| `perception/provider.py` | 串起 backend、融合、跟踪与策略 | `MediaPipeHeadProvider.create`、`get_frame_result` | `test_mediapipe_head_provider` |
| `perception/outputs.py` | `head_observations` JSON/JSONL 序列化 | `head_frame_to_json_dict` | `test_outputs` |
| `gazelle/model.py` 等上游文件与 `scripts/`、`data_prep/` | 上游模型、指标、训练与评测；本 fork 未修改 | `get_gazelle_model`、指标函数 | 无 |

## 4. 不变量核对

| AGENTS.md 不变量 | 状态 | 说明 |
| --- | --- | --- |
| HeadProvider 只产出有序 `HeadObservation` | 成立 | 各 provider 不运行 Gazelle、不读视频、不写预测 |
| 送入 predictor 的 bbox 规范化且与 `person_id` 对齐 | 格式成立，语义不成立 | 格式校验完整；但 GZ-01 的融合框属于两个人，GZ-05 的子格框在模型内退化，GZ-09 的视频分母未校验 |
| 无选中头不构建、不调用模型 | 成立 | 图像与视频路径均有行级证据和测试 |
| `gaze_eligible` 为保守建议，`gazelle_selected` 记录实际调度 | 成立 | 两字段分别写出 |
| 诊断选择不复活过期轨迹、不改预测状态；渲染不改输出 | 成立 | 视角选择器会命中 `tracked_only` 沿用的旧视角，符合已批准规范但文档未说明（C040） |
| `--gaze-inout-threshold` 独立于 `--gaze-render-mode` | 成立 | 分类只在 `apply_prediction_gaze_status` |
| 视频流式处理，三类计数对齐 | 成功路径成立 | 失败路径的残留状态未定义（GZ-13） |
| 输出冲突与外部能力尽量在模型构建前检查 | 部分成立 | 冲突检查成立；纯参数错误在删除之后才报（GZ-04）；trackers 依赖与设备可用性推迟到首帧（C051、C057） |
| 下载暂存加原子替换，失败刷新保留旧缓存 | 部分成立 | MediaPipe 完整成立；checkpoint 的 strict 校验在替换之后（GZ-11）；DINOv2 hub 路径是否在范围内未定义（GZ-10） |
| H.264 终结用临时文件与原子发布，不保留音频 | 成立 | 失败时删除 mp4v 中间文件是已批准设计 |
| 保护原始输入与正式结果 | 一般成立 | 输入文件位于输出目录内时，`--overwrite` 可能把它删除（C056） |
| 保持 bbox 顺序、帧索引、毫秒时间戳与角度坐标约定 | 部分不成立 | 顺序与索引成立；面部射线和 roll 的符号约定与规范相反（GZ-02）；两类退化输入下时间戳有已声明限制（GZ-07） |
| Gazelle 只接收 RGB 与头框；两条射线是未标定参考 | 成立 | 射线不进入模型 |
| 区分 `no_head`、`no_gaze`、`skipped` 与实际预测 | 两处不成立 | 视频 `no_head` 混入“已检出但未确认”（GZ-03）；图像 `predictions.json` 无法区分 `no_head` 与 `no_gaze`（GZ-14） |
| 默认测试隔离 | 成立 | Gate B 无网络、CUDA、FFmpeg；有一处 `torch.hub` 全局目录未恢复的测试卫生问题（C083） |
| 四份用户文档同步 | 部分成立 | 两份 USAGE 逐行对齐；`README_CN.md` 有省略与中文独有章节（GZ-17） |

## 5. 重点问题

### GZ-01 [P1] 单人模式把不同人的脸和姿态融合成一个头框

- **证据等级**：已实际运行，主线程复现。数据来自 Gate C 的 Sunny 样例（两人同框，30 帧）。
- **机制**：`max_heads == 1` 时，`build_head_candidates` 分别取全局置信最高的人脸候选与姿态候选，再用一致性门控决定是否融合（`gazelle/runtime/perception/fusion.py:417-435`）。门控是“IoU ≥ 0.10 或中心距 ≤ 较大对角线的 0.75 倍”（`fusion.py:284-297`），对相邻两人过宽。单人模式下 backend 也只返回 1 个人脸检测和 1 个姿态（`mediapipe_backend.py:94`、`:105`、`:370-374`），二者可能来自不同的人。
- **实测**：保守运行（`--max-heads 1 --gazelle-head-mode eligible`）中，person 1 有 14 帧是 `face_pose`：人脸框在男孩（x 约 0.61 至 0.84），姿态鼻点在女孩（x 约 0.44 至 0.47），融合头框是两者并集（x 约 0.42 至 0.87），宽度为男孩正确头框的 2.0 至 2.3 倍。14 次 Gazelle 推理中 12 次使用了这种头框。`--max-heads 2` 的诊断运行走多人匹配，配对正确。
- **对预测的影响**：同一帧里，跨人头框与男孩正确头框相比，视线峰值平均偏移 0.25（归一化坐标），其中 3 帧偏移 0.6；12 帧中 5 帧 in/out 判定被翻转。JSONL 的头框和两条参考射线也被混成一个“人”。头框相同的帧，两次运行预测完全一致，说明差异完全来自头框。
- **归因**：实现与已批准规范 §12、§13 一致，是规范本身的设计缺口。修正需要你批准规范修订。
- **修复方向**：见 ROADMAP 决策 D1。推荐同时做两件事：一是融合要求姿态的鼻点和至少一个眼或耳落在人脸扩展头框内；二是单人模式也向 backend 请求少量候选（例如 3 个），走多人匹配后再仲裁到 1 人。两者都需要真实多人 smoke 验证。

### GZ-02 [P1] 面部参考射线垂直方向与规范相反

- **证据等级**：主线程复现，实测数值核对；MediaPipe 坐标系方向为推断（复核代理核对了上游 C++ 源码与 canonical 人脸模型）。
- **规范**：`2026-07-21` 设计 §14 规定，正 pitch 表示人脸在显示图像中转向下方，正 roll 表示显示图像中顺时针。
- **代码**：`reference_rays.py:162-170` 对 pitch = +30° 给出方向 (0, -1)，即指向图像上方。这等价于把旋转矩阵第三列 (r02, r12) 直接当作图像坐标，没有翻转 y。MediaPipe 的 metric 空间 Y 向上，所以垂直分量应取反。
- **实测佐证**：诊断运行第 15 帧，男孩看向左下方的女孩，Gazelle 峰值也落在女孩脸部，但序列化的面部射线方向是 (-0.90, -0.43)，指向左上并止于图像上边界。
- **连带问题**：按同一推导，`_matrix_to_head_pose`（`mediapipe_backend.py:234-252`）输出的正 roll 在显示图像中是逆时针，与规范相反。yaw 与 pitch 的符号与规范一致。
- **影响范围**：`--face-pose-ray` 的渲染、JSON/JSONL 中 `face_pose_reference_ray` 的方向与终点、`head_pose.roll_deg`。不影响 Gazelle 输入、预测、`gaze_status` 和选择逻辑。
- **修复**：按已批准规范修正代码（AGENTS.md 的来源优先级中，已批准规范高于现有代码）。补充 pitch、roll 非零的符号回归测试与面部、姿态射线同向一致性测试，四份文档明示符号约定。需要独立审查，并用本地 GPU 跑一次低头、抬头、歪头样例终验。对应 TASK-002。

### GZ-03 [P2] 视频中每条轨迹的首帧被丢弃，记为 `no_head`

- **证据等级**：主线程复现上游行为，已实际运行。
- **机制**：适配器丢弃 `tracker_id == -1` 的行（`tracking.py:279-280`）。trackers 2.5.0.post0 的 `_spawn_new_tracks` 对新轨迹固定输出 -1，ID 要到下一帧匹配时才分配，`minimum_consecutive_frames=1` 也不改变这一点。规范 §15 的意图是 1 帧即确认。
- **实测**：两次视频运行的第 0 帧都是 `no_head`，而 MediaPipe 当帧已运行。
- **影响**：每个视频第 0 帧必为 `no_head`；每个新出现或断开重建的人首帧消失；`track_age_frames` 少计 1；`--frame-step` 下可能丢掉一次推理；`no_head` 混入“已检出但未确认”。现有测试的 fake tracker 首帧就给 ID，因此 531 个测试全绿也暴露不了。
- **需要你决策**：只文档化并增加可审计计数，还是修复为 spawn 行立即确认。见 D2。测试可以先补（TASK-005）。

### GZ-04 [P2] `--overwrite` 在纯参数校验之前删除旧结果

- **证据等级**：复核确认（两个读取代理独立报告），主线程读代码确认。
- **机制**：`create_output_dir` 先执行（`pipeline.py:250`、`:361`），`--overwrite` 时调用 `shutil.rmtree`（`:124-125`）；provider 在其后才构造（`:252`、`:367`）。static 缺 `--bbox`、`--bbox nan ...`、`--person-id` 数量不符、json 缺 `--head-data` 或文件不存在，都在删除之后才报错，且以 traceback 退出码 1 结束，而不是 usage error。
- **影响**：一次漏参就会不可逆地删掉上一轮的预测、观测和渲染结果。文档示例几乎都带 `--overwrite`，这种组合并不罕见。
- **修复**：把纯参数可判定的检查移入 `RuntimeConfig.validate()`，以 exit 2 拒绝。对应 TASK-001，也是 Codex 的首个协作演练。

### GZ-05 [P2] 小于约 1/32 画幅的头框在模型内等价于“无框”

- **证据等级**：主线程复现。
- **机制**：`gazelle/model.py:89-96` 用 `round(x*32)` 把头框栅格化到 32×32；宽或高小于约一格时两端取整到同一格，head map 全零，与 `bbox=None` 完全相同。运行时 `min_size=1e-6`（`geometry.py:24`）远低于这个尺度，预测仍以该框、`valid` 输出。
- **影响**：远处小头的“该人看哪里”实际是场景先验，输出无任何标记。默认 MediaPipe `eligible` 路径基本不可达；static、json、外部检测器框与诊断选择器可达，Multi-Pose 下游最可能触发。
- **处理**：上游训练与评测本身包含这种量化，不应改模型。运行时增加标记还是只写文档，见 D3。

### GZ-06 [P2] 打包只发现 `tests`

- **证据等级**：主线程复现，`setuptools.find_packages()` 只返回 `['tests']`。
- **机制**：`gazelle/` 顶层没有 `__init__.py`，`setup.py:8` 用 `find_packages()`。当前 pip 26 与 setuptools 81 的编辑安装只映射被发现的包。
- **影响**：四份文档要求的 `pip install -e .` 静默无效；在仓库根目录以外 `import gazelle.runtime` 会失败。CLI 与测试从仓库根运行，不受影响。
- **修复**：改动很小（TASK-003）；在 Gazelle 环境中重装验证需要你授权。

### GZ-07 [P2] 时间戳时钟与碰撞

- **证据等级**：复核确认；两点都已在 USAGE 文档中声明为已知限制。
- **现象**：源 FPS 无效时，reader 的回退时钟固定 30 FPS（`media.py:155-160`），不跟随 `--output-fps`，而 writer 与 tracker 使用 `--output-fps`。取整后重复的毫秒时间戳会让 MediaPipe backend 关闭并中止整段视频（`mediapipe_backend.py:320-333`、`:438-443`）。
- **现实性**：复核认为触发需要畸形 PTS 或 1000 fps 以上，但 reader 的回退分支完全没有测试。
- **处理**：修复需要先决定 MediaPipe 时钟与 JSONL 时钟是否允许分叉，见 D4；测试先补（TASK-005）。

### GZ-08 [P2] 研究脚本在本机不可用或不严格

- **证据等级**：主线程复现第一项，其余复核确认。
- `data_prep/preprocess_vat.py:55` 用 `split("/")` 拆 Windows 路径，必然 `FileNotFoundError`。
- `scripts/eval_vat.py` 与 `eval_gazefollow.py` 走上游非严格加载，缺失 in/out 权重时只打印 WARNING 仍输出 AP（C078）。
- `gazelle/model.py` 与 `gazelle/utils.py` 的指标函数没有离线测试（C026）。
- 均为上游继承代码；修复不改变指标公式与评测协议。对应 TASK-007。

### 其余问题组（P3 为主，详见登记表）

| 组 | 摘要 | 处理 |
| --- | --- | --- |
| GZ-09 | 视频解码帧尺寸从不与容器元数据比对；不渲染时错误分母会静默进入模型与 JSONL | TASK-004 加逐帧守卫 |
| GZ-10 | DINOv2 `torch.hub` 未 pin，每次构建都探测 GitHub，截断的权重落盘后无法用任何开关恢复 | TASK-006 先写恢复步骤；pin 与哈希见 D8 |
| GZ-11 | checkpoint `--force-download` 的 strict 校验在替换之后，README 的承诺比实现强 | D8 |
| GZ-12 | bridge 有效时长受固定 500 ms 衰减与 0.15 下限限制，大于约 0.6 至 0.95 s 的 `--head-track-max-gap-ms` 静默失效；多人时可能出现旧 ID 幽灵 | 文档先说明（TASK-006），行为见 D5 |
| GZ-13 | 中途失败留下部分输出、无完成标记；`error` 状态从不写出；JSON 头级校验延迟到逐帧 | D6 |
| GZ-14 | 图像 `predictions.json` 无帧级状态，选择器拒绝与无头无法区分 | 文档先说明，字段见 D7 |
| GZ-15 | 面向 Multi-Pose 的库式契约：`predict_frame` 不做 in/out 分类、`torch.hub.set_dir` 改全局且不恢复、config 鸭子类型、`FramePacket` 死代码 | 第 3 阶段，需先确认 Multi-Pose 需求 |
| GZ-16 | MediaPipe 阈值依赖上游默认（规范 §18 承诺的冻结配置未落实）；裁剪内 landmarker 用 `num_faces=max_heads` 再取第一个；非有限 landmark 未在边界拒绝 | D9 |
| GZ-17 | 文档同步：README_CN 省略、样例路径不可运行、射线字段键名未列出、heatmap 重复 ID 命名、文档契约测试的 samples 守卫失效 | TASK-006 |
| GZ-18 | 其他鲁棒性与可维护性：CLI help 缺失、常量重复、FFmpeg 继承 stdin、`run_config.json` 可能写出 NaN、xFormers 守卫误报、渲染性能等 | 按需并入相关任务 |
| GZ-19 | 场景切换不重置 tracker 与 bridge（交接遗留路线图项） | 第 4 阶段，需要规范 |
| GZ-20 | 测试加固：0.50 边界、轴向射线仍可 eligible、全局状态卫生、管线级跟踪集成 | TASK-005 |

## 6. 观察（尚未确认为缺陷）

- **OBS-1 保守模式在 `the_office.png` 上全部拒绝。** Face Landmarker 对两个人脸裁剪都返回空，于是没有 `head_pose`、没有面部射线，资格判定为 `rejected_low_quality`。BlazeFace 还把一只手检为人脸（置信 0.76），左侧与中间人物的正脸未被检出。这与交接开放问题 1 一致。在你的真实作业视频上对比保守与诊断模式时，应逐帧区分检测器、landmarker、融合、选择各环节。
- **OBS-2 推理确定性良好。** 两次运行中头框相同的帧，峰值与 in/out 分数完全一致。
- **OBS-3 粗略性能。** 视频首次推理约 645 ms（含 CUDA 初始化与懒构建），之后约 23 至 30 ms/帧（ViT-B、RTX 4080 SUPER、1 至 2 人）；MediaPipe 前端在 770×433 图像上约 34 ms。这不是系统性基准。

## 7. 被驳回的 17 条报告

多数驳回理由属于三类：已批准规范明文要求的既定行为；用户文档已声明的已知限制；触发前提在受支持输入下不存在。例如 avc1 奇数分辨率（OpenCV 中间文件不会出现奇数尺寸）、`--force-download` 刷新时机（规范与测试固定）、渲染选项未校验（无受支持入口可达）。完整理由见登记表第 3 节。

## 8. 应当保留的优点

- 冻结 dataclass 契约与集中化的几何校验，错误在边界尽早暴露。
- 下载、缓存与 H.264 发布的暂存加原子替换，失败时保留有效缓存。
- 资源清理统一走 `finally` 与 `add_note` 聚合，失败不会掩盖原始异常。
- 保守建议与实际调度分开记录，诊断模式不改写预测状态。
- 离线测试与真实依赖彻底隔离，3 秒跑完 531 个测试。
- 文档契约测试把 CLI、schema 与文档绑定在一起。

## 9. 需要你决定的事项

| 编号 | 决策 | Claude 的建议 |
| --- | --- | --- |
| D1 | GZ-01 单人模式 face/pose 关联是否按建议修订规范 §12、§13 | 2026-10-15 已批准，见 TASK-101 与 2026-10-15 规范 |
| D2 | GZ-03 spawn 帧策略 | 2026-10-15 已批准，见 TASK-102 与 2026-10-15 规范 |
| D3 | GZ-05 子格头框 | 预测记录增加 `head_map_empty` 布尔字段（加法式 schema），不改框、不改 `gaze_status` |
| D4 | GZ-07 时间戳 | reader 用解析后的 FPS 做回退时钟并保证单调，`run_config.json` 记录时间戳来源与修正帧数 |
| D5 | GZ-12 bridge 与 ByteTrack 窗口 | 由 `--head-track-max-gap-ms` 统一推导两侧窗口；多人时做桥接后空间去重 |
| D6 | GZ-13 失败路径 | 维持致命失败；JSON 头数据加载期全量校验；冲突检查前置、删除后置；写 `run_status.json` 完成标记 |
| D7 | GZ-14 图像预测状态 | `predictions.json` 增加帧级 `status`（加法式） |
| D8 | GZ-10、GZ-11 DINOv2 与 checkpoint | 先文档化；后续固定 commit 并校验骨干权重 SHA-256；strict 校验移到替换之前 |
| D9 | GZ-16 MediaPipe 阈值与裁剪 | 显式冻结当前默认阈值（行为中性）；裁剪内 `num_faces=1` |
| P | 发布方式 | 2026-10-15 已确定：Codex 提交并推送到阶段分支，见 `COLLABORATION_PLAN_CN.md` §4、§7 |

2026-10-15 补充：基于你的真实视频历史输出，新增决策 D10（保守门控重新设计）、D11（主体身份稳定）、D12（验证集），见 `PROJECT_GOALS_CN.md` 与 `ROADMAP.md`。
