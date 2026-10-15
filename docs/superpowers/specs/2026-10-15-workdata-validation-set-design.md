# Work-Data Validation Set Design (D12, revision 2)

Status: revision 2, 2026-10-15, written by the coordinator (Claude).
Revision 1 was approved by the user on the same day "as recommended". It
sampled single frames from `sample1.mp4` and `sample2.mp4` and labelled
image-space gaze points. The coordinator replaced it after two new facts:

1. The user confirmed that the goal is the attention region over time, fused
   from three synchronized fixed cameras (`docs/collab/PROJECT_GOALS_CN.md`).
2. The work-data analysis showed that `sample2.mp4` is an edited video from a
   different workplace and that the real target data is available
   (`docs/collab/analysis/2026-10-15-workdata-analysis.md`).

The user may veto this revision. Labelling does not start before the user
answers Q7 (camera roles) and Q8 (region classes) in
`docs/collab/PROJECT_GOALS_CN.md`.

## 中文摘要

- **数据**：E 盘作业数据，只读。使用 TASK-134 生成的 5 Hz 同步代理视频，三台摄像机共用一条时间轴。
- **单位**：连续 60 秒片段。每次录制 4 段，2026-08-24 那次只有 30 分钟，取 2 段，共 26 段；另加 1 段试标片段。在三机重叠时段内分层随机抽取，种子 20261015。
- **标注**：每 0.2 秒一个时间步。标注者同时看到三个视角，按数字键在注视区域发生变化的时刻打点。类别按 Q8 确认，默认为取货台、作业台、放置区、工作区内其他、离开工作、不在岗、无法判断。另外记录他人入镜的区间。
- **工作量**：每段约 4 到 5 分钟，共约 2 小时，可分多次完成。
- **隐私**：代理视频、抽出的帧与标注只保存在本机仓库之外；证据文件只含汇总指标。
- **用途**：评估第 3 阶段的区域推断，包括逐时间步准确率、注视片段的时长误差、各区域时间占比误差，按录制日期留一交叉验证。

## 1. Purpose

1. Provide ground truth for the attention region over time at the analysis
   rate (decision D13: 5 Hz on the burned-in clock).
2. Support step-level, episode-level, and session-level (time share)
   evaluation of the stage-3 pipeline.
3. Allow leave-one-session-out evaluation across the seven recordings.

## 2. Data and privacy

| Item | Value |
| --- | --- |
| Source videos | `E:\Gazelle_Workdata\秋田大学様解析用動画\`, read-only |
| Synchronized proxies | `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\proxies\` (TASK-134) |
| Dataset root | `C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2\`, configurable |
| Run outputs | `C:\Users\yun\Documents\Claude_Code\gazelle_runs\` |

Rules:

- Never write into the source tree or into the user's acceptance checkout.
- Never commit or upload proxies, frames, labels, or run outputs.
- Evidence files in the repository contain aggregate metrics, segment
  identifiers, and file hashes only.
- The annotation server binds to `127.0.0.1` and loads no external resources.
- The dataset manifest records the SHA-256 of every proxy it uses and the
  time-map version, so labels stay tied to exact inputs.

## 3. Sampling

- Unit: one 60-second segment on the common clock, 300 steps at 5 Hz.
- Sessions: the three-camera overlap window of each recording (TASK-133).
- Count: 4 segments per session; 2 for the 30-minute recording of
  2026-08-24. Total 26.
- Stratification: split each overlap window into equal strata, one per
  segment. Draw each segment start uniformly inside its stratum with a seeded
  generator (seed 20261015), so the whole segment lies inside the stratum.
- Gaps: if a drawn segment contains more than 2 seconds of proxy steps flagged
  as gaps by TASK-134, redraw inside the same stratum, at most 10 times, and
  record the attempts. Never select by content such as worker presence.
- Pilot: 2026-09-07 22:20:00 to 22:21:00 (burned-in clock). It is labelled
  first, used for tool shakedown and guideline calibration, and excluded from
  evaluation.
- Extension: after the first pass, the coordinator may request 2 more segments
  per session if a class has too few episodes. The extension uses a new seed
  that is recorded in the manifest.

## 4. Label schema

### 4.1 Classes (default; final set after Q8)

| Key | Label | Definition |
| --- | --- | --- |
| 1 | `pick_right` | the right-side desk, where items are picked up |
| 2 | `work_front` | the front desk work area: jig, workpiece being processed, tools in use there |
| 3 | `place_left` | the left part of the front desk, where finished items are placed |
| 4 | `cell_other` | other targets inside the work cell: tools, documents, screens, or equipment outside the three areas |
| 5 | `away` | outside the work cell: aisle, other people, distant background, ceiling |
| 6 | `absent` | the worker is not at the station |
| 0 | `unknown` | the annotator cannot judge |

The class set lives in a configuration file. Tools must not hard-code it.

### 4.2 Rules

- Label what the worker looks at, judged from head orientation, the eyes when
  visible, and hand activity. When the head or eyes disagree with the hands,
  follow the head and eyes.
- During a head turn, switch the label at the first step where the new target
  is clearer than the old one.
- Use `unknown` instead of guessing.
- When a second person is in view, mark an `other_people` range. If the worker
  looks at that person, label `away`.

### 4.3 Record per segment

| Field | Content |
| --- | --- |
| `segment_id`, `session` | identifiers from the manifest |
| `start_wall_time`, `step_hz`, `step_count` | position on the common clock |
| `labels` | runs `{"start_step", "end_step_exclusive", "label"}` covering every step exactly once |
| `other_people` | runs `{"start_step", "end_step_exclusive"}` |
| `note` | optional text |
| `annotator`, `started_at`, `finished_at`, `active_seconds` | set by the tool |

A per-step array is derived from the runs; it is never stored separately.

## 5. Tool requirements (TASK-121)

- Local server on `127.0.0.1` using the standard library and packages already
  in the `Gazelle` environment; inline HTML and JavaScript.
- Shows cameras A, B, and E at the same step, with E largest. Shows
  `roi_reference.png` from the dataset root when present, otherwise the text
  definitions.
- Controls: play and pause at 1× and 0.5×; step by 0.2 s and 1 s; number keys
  set the label from the current step until the next change point; delete a
  change point; undo; a timeline bar with coloured runs; jump to the next
  unlabelled step; mark `other_people` start and end.
- Autosave after every change with an atomic write and a rolling backup;
  resume where the annotator stopped.
- `--labels-path` for trial files and `--annotator` for the annotator name.
- A validation command that checks labels against the schema and the manifest.

## 6. Quality

- Intra-annotator consistency: relabel the pilot and two random segments at
  least three days later; report step agreement and Cohen's kappa.
- If a second annotator is available, double-label four segments and report
  Cohen's kappa.

## 7. Metrics (computed in stage 3; definitions fixed here)

- Step level, over steps whose label is not `unknown`: accuracy, macro-F1 over
  the classes present, per-class precision and recall, and the confusion
  matrix. `absent` is a regular class.
- Episode level: an episode is a maximal run of one label. Predicted and
  labelled episodes match when their temporal IoU is at least 0.5. Report
  episode F1 and the median absolute duration error of matched episodes.
- Session level: per class, the absolute difference between predicted and
  labelled time share over labelled steps.
- Off-task detection: precision and recall of `away` against all work classes.
- Splits: leave-one-session-out. 95% intervals by a seeded bootstrap over
  segments with 1000 resamples.
- Changing any definition requires user approval.

## 8. Effort and schedule

About 4 to 5 minutes per segment and about 2 hours in total, split across
sittings. Labelling starts after TASK-121 passes review and the user answers
Q7 and Q8.

## 9. Revision history

| Revision | Date | Content |
| --- | --- | --- |
| r1 | 2026-10-15 | 100 frames from sample1 and 200 from sample2, image-space gaze points, single-camera gating evaluation (D10). Withdrawn. |
| r2 | 2026-10-15 | This document. |
