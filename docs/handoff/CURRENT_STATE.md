# Gazelle Handoff Snapshot / Gazelle 交接快照

Snapshot date: **2026-10-14, Asia/Tokyo**. This is dated evidence, not a permanent
instruction or a guarantee about a later checkout. Recheck Git when resuming.

## 1. Git And Working Tree / Git 与工作区

| Item | Observed value |
| --- | --- |
| Repository | `Hyakuri/gazelle`, private |
| Source checkout | `C:\Users\yun\Documents\Codex\2026-06-25\hyakuri-gazelle` |
| Branch | `feature/mediapipe-head-tracking` |
| HEAD | `bbec05653c9c0d4dc8046aff26b9e159b51889d7` |
| Existing PR | [#5 Add MediaPipe head perception and tracking](https://github.com/Hyakuri/gazelle/pull/5) |
| PR base | `feature/enhanced-gaze-rendering` |
| PR status checked this task | OPEN, non-draft; head matches local HEAD |
| Latest committed change | `Add repository agent instructions` |

At task entry, `AGENTS.md` contained the completed but uncommitted September
rule optimization. `.agents-backups/AGENTS.md.20260914-6f75837a.bak` and
`.codex/config.toml` were untracked pre-existing files. Preserve both locally.
This handoff adds documentation, a thin Claude entry, and links; it is delivered
without staging, committing, pushing, creating a branch, or modifying the PR.
The transfer snapshot includes the optimized AGENTS and this handoff, although
the Git bundle ends at the HEAD above. See the package manifest for exact paths.

任务开始时，优化后的 `AGENTS.md` 尚未提交；已有备份及 `.codex/config.toml`
属于先前工作。本轮不提交或推送。只 clone GitHub 或 Git bundle 会缺少未提交文档，
接手者还必须恢复包内完整源码快照。远端 PR 状态由本轮只读查询确认。

## 2. Implemented Capabilities / 已实现能力

- Unified CLI, four registered ViT-B/ViT-L models with/without in/out prediction.
- Resource preparation, strict checkpoint loading, staged cache replacement;
  MediaPipe assets have pinned digests. Gazelle weights do not have pinned
  digest validation, and first DINOv2 construction may execute unpinned Hub code.
- `GazellePredictor`, validated normalized head boxes, ordered person output,
  empty-head handling, and single-person no-box fallback.
- `none`, `static`, `json`, and `mediapipe` providers. MediaPipe face detector,
  Face Landmarker, Pose Landmarker, fusion, ByteTrack, short-occlusion bridging,
  and post-bridge head arbitration. Defaults: one head, Pose Full, 500 ms bridge.
- Image and streaming offline-video pipelines; independent head observations,
  gaze predictions, run configuration, optional rendering, image-only raw maps.
- Independent face/pose uncalibrated 2D reference rays. These are not eye-gaze
  measurements. Only RGB images and head bboxes enter the Gazelle model.
- Diagnostic head selectors with OR semantics, including active `tracked_only`;
  separate `gaze_eligible`, `gazelle_selected`, in/out classification, and
  `valid-only` / `all-predictions` rendering.
- `mp4v` output and optional FFmpeg H.264 `avc1`, NVENC-to-libx264 fallback,
  `yuv420p`, faststart, atomic finalization. No source-audio preservation.

当前已贯通头部观测、跟踪融合、Gazelle 推理和输出渲染。重点使用场景是单人作业，
未来支持不超过 10 人，但真实多人验证有限。面部检测不是身份识别；诊断模式结果
不能当作精确眼动测量。完整 CLI 和 schema 以 [USAGE_CN](../USAGE_CN.md) 为准。

## 3. Source Environment Evidence / 源环境证据

Read on the snapshot date using the existing interpreter and
`importlib.metadata`; no Torch, MediaPipe, or CUDA model execution was performed.

| Component | Installed metadata |
| --- | --- |
| Python | 3.11.15 |
| Interpreter | `C:\Users\yun\anaconda3\envs\Gazelle\python.exe` |
| Torch / TorchAudio | 2.6.0+cu126 |
| TorchVision | 0.21.0+cu126 |
| NumPy | 2.4.6 |
| OpenCV Python / contrib | 4.11.0.86 / 4.11.0.86 |
| MediaPipe | 0.10.35 |
| trackers / supervision | 2.5.0.post0 / 0.29.1 |
| xFormers / timm | 0.0.29.post3 / 1.0.15 |
| Pillow / ultralytics | 11.1.0 / 8.4.104 |

The inspecting shell had `CONDA_DEFAULT_ENV=null`; the explicit Gazelle
interpreter was used. FFmpeg was found at `C:\Users\yun\ffmpeg\bin\ffmpeg.exe`
but was not executed; encoder/driver availability was not revalidated.
`environment.yml` is the recommended definition, not a complete platform lock.
`environment_1.0.yml` retains the NumPy 1.26.4 rollback/reference definition.

本轮只是版本元数据核验，不等于全部依赖 import、CUDA 或模型执行成功。目标电脑
必须重新验收；不能复制旧绝对路径，也不能将 CUDA wheel 版本当作驱动可用证明。

## 4. Validation Evidence / 验证证据

- Historical session evidence: 531 offline unit tests passed at the code baseline
  above; compileall, help, list-models, and whitespace checks also passed.
  This is prior evidence, not a fresh result for a destination machine.
- Previous development reported real MediaPipe/ByteTrack and Gazelle image/video
  smoke tests; the user also obtained playable rendered videos. Their artifacts
  and full logs are not included, so do not claim independent reproduction.
- This migration task uses static documentation/package checks and focused
  documentation tests. Actual command results and file hashes are recorded in
  the accompanying transfer manifest and final delivery report.
- No real checkpoint download, DINOv2 construction, CUDA/FFmpeg inference,
  environment installation, or formal accuracy experiment is part of this task.

历史通过记录与本轮结果分开。目标机器的模型、GPU、编码器、客户端规则自动加载、
ChatGPT/Claude 实际协作效果都需要当地验证，不能由文件已复制推断成功。

## 5. Open Problems And Next Work / 问题与后续方向

1. PPE, downward-facing heads, back views, motion, and small faces degrade
   perception. Earlier samples showed false people and misleading gaze targets.
   Conservative gates can suppress too much; diagnostic controls now support
   comparing raw model behavior. Do not silently relax scientific thresholds.
2. Video timestamps rounded to integer milliseconds must strictly increase for
   MediaPipe. Repeated/rounded-colliding timestamps can fail. Invalid source FPS
   uses a 30 FPS reader clock while writer/tracker fallback can differ.
3. Torso-first tracking and scene-cut reset were discussed but are not implemented.
4. Iris/head-pose/heatmap/ROI fusion, calibrated gaze, webcam mode, async inference,
   audio remuxing, raw video heatmap export, and Multi-Pose integration are pending.
5. Historical videos were referenced under
   `C:\Users\yun\Documents\GitHub\gazelle\samples\sample1_gazelle\rendered.mp4`
   and `sample2_gazelle\rendered.mp4`. They are outside this checkout and were
   not inventoried or copied. Obtain original inputs and matching JSONL/config
   before drawing new accuracy conclusions.

建议接手后先完成目标机器验收，再用同一短视频、相同模型和参数对比 conservative /
diagnostic 模式，逐帧区分 detector、tracking、selection、Gazelle 与 renderer 问题。
这些是后续候选任务，不构成自动实施、下载、训练或批量处理的授权。

## 6. Transfer Inventory / 迁移清单

| Category | Treatment |
| --- | --- |
| Tracked source, tests, docs, license, tracked assets | Included in repository snapshot and Git history |
| Optimized AGENTS and new handoff files | Included as working-tree content; not represented by HEAD alone |
| `models/checkpoints`, `models/mediapipe`, `models/torch_hub` | Present locally; excluded from source package; optional separate verified copy |
| `outputs`, `samples` in this checkout | Absent at inspection |
| `.codex`, `.aws`, credentials, machine-global agent settings | Excluded; recreate permissions/login on destination |
| `.agents-backups` | Preserved at source; excluded from normal handoff loading and source package |
| Conda installation and binary environment directory | Excluded; use approved destination setup and validation |

源电脑仍是原始资料的保留位置；交接包不是整机备份，也没有向另一台电脑自动传输。
