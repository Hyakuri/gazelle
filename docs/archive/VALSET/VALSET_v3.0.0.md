# Work-Data Validation Set Design (D12, revision 2)

Status: revision 3 in preparation (2026-10-18, §10): the user approved the
direction (D20) and the details await confirmation (Q-017). Formal labelling is
paused until revision 3 and its tool (TASK-125) are ready. Revision 2 below,
dated 2026-10-15, was written by the coordinator (Claude).
Revision 1 was approved by the user on the same day "as recommended". It
sampled single frames from `sample1.mp4` and `sample2.mp4` and labelled
image-space gaze points. The coordinator replaced it after two new facts:

1. The user confirmed that the goal is the attention region over time, fused
   from three synchronized fixed cameras (`docs/collab/PROJECT_GOALS_CN.md`).
2. The work-data analysis showed that `sample2.mp4` is an edited video from a
   different workplace and that the real target data is available
   (`docs/collab/analysis/2026-10-15-workdata-analysis.md`).

The user approved revision 2 on 2026-10-15. Labelling starts after TASK-121
passes review and the user has drawn the region polygons with TASK-123.

Camera roles, confirmed by the user on 2026-10-15: the front desk camera is
`cam_b` (usually named カメラ2), the right desk camera is `cam_a` (usually named
カメラ1), and the overview camera between the desks is `cam_e` (設備カメラ).
Tools select files by physical camera ID, never by file name, because the
names are swapped in folder `20260903`.

## 中文摘要

- **数据**：E 盘作业数据，只读。使用 TASK-134 生成的 5 Hz 同步代理视频，三台摄像机共用一条时间轴。
- **单位**：连续 60 秒片段。每次录制 4 段，2026-08-24 那次只有 30 分钟，取 2 段，共 26 段；另加 1 段试标片段。在三机重叠时段内分层随机抽取，种子 20261015。
- **标注**：每 0.2 秒一个时间步。标注者同时看到前方、右侧与全局三个视角，按数字键在注视区域发生变化的时刻打点。类别由你在全局摄像机画面上画出的区域生成（TASK-123）；按默认区域，类别为取货台、作业台、放置区、工作区内其他、离开工作、不在岗、无法判断。另外记录他人入镜的区间。
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

### 4.1 Classes

The labelling classes are derived from the region polygons that the user
draws on the overview camera with TASK-123: one class per target region in the
order drawn, then `cell_other`, `away`, `absent`, and `unknown`. The table
shows the result for the default regions.

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
- Shows the front, right, and overview cameras at the same step, with the
  overview largest. Shows `roi_reference.png` from the dataset root when
  present, otherwise the text definitions.
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
  segments with 1000 resamples. Each recording date has a single worker and
  workers differ across dates (user, 2026-10-15), so leave-one-session-out
  approximates leave-one-worker-out. If the user later provides anonymous
  worker IDs per date, also report leave-one-worker-out.
- Changing any definition requires user approval.

## 8. Effort and schedule

About 4 to 5 minutes per segment and about 2 hours in total, split across
sittings. Labelling starts after TASK-121 passes review and the user draws the
regions with TASK-123.

## 9. Revision history

| Revision | Date | Content |
| --- | --- | --- |
| r1 | 2026-10-15 | 100 frames from sample1 and 200 from sample2, image-space gaze points, single-camera gating evaluation (D10). Withdrawn. |
| r2 | 2026-10-15 | This document. Approved by the user the same day, together with the camera roles and the region-marking approach. |
| r3 | 2026-10-18 | §10. The user approved the direction (D20): a hands/held-object class and attention points at gaze changes. The details below await the user's confirmation (Q-017). Formal labelling is paused until then. |

## 10. Revision 3 (2026-10-18)

### 10.1 Why

On 2026-10-18 the user clarified the project goals (`docs/collab/PROJECT_GOALS_CN.md` v3):

- high-precision gaze, including eye movements;
- the attended location as a centre-graded heatmap, including hands, held objects and other moving targets;
- gaze must not be inferred from head direction alone.

Region labels alone cannot evaluate the attended location or moving targets. The user cannot add recordings for now (D19), so human annotation is the main ground truth for location. The user chose to pause formal labelling and revise the scheme first (D20).

### 10.2 Classes

- The fixed classes after the drawn target regions become `hands_object`, `cell_other`, `away`, `absent`, then `unknown`.
- With the formal regions the keys are:

  | Key | Class |
  | --- | --- |
  | 1–4 | The four drawn target regions, in the order drawn |
  | 5 | `hands_object` |
  | 6 | `cell_other` |
  | 7 | `away` |
  | 8 | `absent` |
  | 0 | `unknown` |

- **`hands_object`**: the worker looks at their own hands, or at an object held in or being moved by the hands (workpiece, tool), wherever it is. It takes precedence over the regions. A drawn target region applies when the gaze rests on a surface or object lying in that region.
- **Class file**: the list is regenerated through the official export path of the region tool. The region polygons stay unchanged, the old export is kept as a backup, and the completion marker is rewritten with the new hashes. The user confirms this together with Q-017.

### 10.3 Attention points

- **Required point**: every run labelled with a drawn target region, `hands_object` or `cell_other` needs at least one point, or an explicit "point skipped (unsure)" mark.
  - The annotator clicks once on the overview view at the location the worker attends to, by default at the run's first step, otherwise at the step where the target is clearest.
- **Extra points**: optional, at most one per second, when the attended location visibly moves within a run, for example when following a moving hand.
- **No points**: runs labelled `away`, `absent` or `unknown`.
- **Format**: a point is `{step, x, y}` in normalised coordinates of the overview proxy frame (1920×1080, x to the right, y down). It belongs to the run that contains its step.
- **Judgement**: decide from the eyes when they are visible, then head orientation, then hand activity. The eyes take precedence over the head, which takes precedence over the hands. This replaces the r2 rule "follow the head and eyes".

### 10.4 Schema version 3

- **Segment fields**: each segment adds `points` (a list of `{step, x, y}`) and `point_skips` (a list of run start steps).
- **Strict validation** additionally requires:
  - every point lies in the segment, with 0 ≤ x, y ≤ 1;
  - no point lies in an `away`, `absent` or `unknown` run;
  - every eligible run has a point or a skip mark;
  - the per-second limit on extra points is respected.
- **Older versions**: version 2 files are rejected with a message to reannotate. No formal labels exist yet.
- **Completion**: the explicit-completion rules of TASK-138 and TASK-124 stay. Completion also requires the point rule.

### 10.5 Metrics added to §7

- **Attention-point error**: the distance in pixels of the 1920×1080 overview frame between the predicted location and the annotated point. The predicted location is the heatmap peak and the heatmap mean. Also report the heatmap mass within radii of 25, 50 and 100 pixels of the point, as median and 90th percentile.
  - After the approximate calibration (D21, second step), report the same distances in centimetres on the desk plane.
- **Target type**: accuracy and per-class recall of `hands_object` against the static regions and `cell_other`.
- **Region metrics**: unchanged from §7, with `hands_object` as an additional class.
- **Human baseline**: the repeat annotation of §6 also reports the median distance between the two point sets. This is the reference precision of the ground truth itself, which matters because there is no instrumented ground truth (D19).

### 10.6 Effort

About 6 to 7 minutes per segment, about 3 hours in total, in several sittings.

### 10.7 中文摘要

- **类别**：在你画的 4 个目标区域之后，增加“手部/手中物体”（`hands_object`）。看自己的手，或手中、正被手移动的工件与工具时，用这一类，并且它优先于区域。按键依次为 1–4 区域、5 手部/手中物体、6 工作区内其他、7 离开工作、8 不在岗、0 无法判断。
- **注视点**：凡标为目标区域、手部/手中物体或工作区内其他的片段，在全局画面上点一下注视位置，至少一个；拿不准可以标“跳过”。注视位置明显移动时可以多点，最多每秒一个。离开、不在岗、无法判断不点。
- **判断依据**：眼睛可见时以眼睛为准，其次是头部朝向，最后是手部动作。
- **工作量**：每段约 6 至 7 分钟，共约 3 小时，可分多次。
- **用途**：评估注意力热力图的位置误差（先按画面像素，近似标定后按厘米）、手部与物体的识别率，以及区域统计。重复标注的点距可作为人工真值本身的精度参考。
