---
doc_id: VALSET
title: 作业数据验证集设计
version: 4.1.1
status: 已确认
updated: 2026-10-29
owner: Claude
confirm_ref: 用户 2026-10-29（Q-017、Q-018、Q-020、Q-021、Q-022、Q-024）；待定项见 Q-023
---
# Work-Data Validation Set Design (D12)

Status: revision 3 (2026-10-18, §10): the user approved the direction (D20)
and confirmed the details on 2026-10-29 (Q-017). Formal labelling is paused
until its tool (TASK-125) passes review. On 2026-10-29 the
user approved revision 3.1 (§10.8, with Q-018) and the addendum in §11: two new
recordings join as a separate cohort, evaluation becomes leave-one-worker-out,
and the regions are registered to each recording (D26, D27). Revision 2 below,
dated 2026-10-15, was written by the coordinator (Claude).
Revision 1 was approved by the user on the same day "as recommended". It
sampled single frames from `sample1.mp4` and `sample2.mp4` and labelled
image-space gaze points. The coordinator replaced it after two new facts:

1. The user confirmed that the goal is the attention region over time, fused
   from three synchronized fixed cameras (`docs/requirements/PROJECT_GOALS_CN.md`).
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
- **单位**：连续 60 秒片段。每次录制 4 段，2026-08-24 那次只有 30 分钟，取 2 段，共 26 段；另加 1 段试标片段。在三机重叠时段内分层随机抽取，种子 20261015。2026-10-29 起，两次新录制各追加 4 段，共 8 段，规则与种子不变，放在一个格式相同的单独数据集里；原 26 段不变（§11）。
- **标注**：每 0.2 秒一个时间步。标注者同时看到前方、右侧与全局三个视角，按数字键在注视区域发生变化的时刻打点。类别由你在全局摄像机画面上画出的区域生成（TASK-123）；按默认区域，类别为取货台、作业台、放置区、工作区内其他、离开工作、不在岗、无法判断。另外记录他人入镜的区间。
- **工作量**：r2 为每段约 4 到 5 分钟。r3 为每段约 6 至 7 分钟：旧 7 次的 26 段约 3 小时，新录制的 8 段约 1 小时，可分多次完成（§10.6、§11.5）。
- **隐私**：代理视频、抽出的帧与标注只保存在本机仓库之外；证据文件只含汇总指标。
- **用途**：评估第 3 阶段的区域推断，包括逐时间步准确率、注视片段的时长误差、各区域时间占比误差。2026-10-29 起按作业者留一交叉验证，旧录制与新录制分层报告（§11）。

## 1. Purpose

1. Provide ground truth for the attention region over time at the analysis
   rate (decision D13: 5 Hz on the burned-in clock).
2. Support step-level, episode-level, and session-level (time share)
   evaluation of the stage-3 pipeline.
3. Allow leave-one-worker-out evaluation across the recordings (§11.3;
   originally leave-one-session-out across the seven recordings).

## 2. Data and privacy

| Item | Value |
| --- | --- |
| Source videos | `E:\Gazelle_Workdata\秋田大学様解析用動画\`, read-only |
| Synchronized proxies | `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\proxies\` (TASK-134) |
| Dataset root | `C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2\`, configurable; the 2026-10 cohort uses the sibling `roi_r2_2026_10\` (§11.2) |
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
- New recordings (2026-10-29): sampled by the same rules and seed into a
  sibling dataset, without changing the 26 segments above (§11.2).

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
- Splits: leave-one-worker-out (§11.3, approved by the user on 2026-10-29).
  95% intervals by a seeded bootstrap over segments with 1000 resamples.
  Revision 2 used leave-one-session-out, on the basis that each recording date
  had a single worker and that workers differ across dates (user, 2026-10-15).
  The user's identity check of 2026-10-29 found four workers. One of them works
  on four of the seven original dates, and the recordings 20260903 and
  20261016 each contain a handover, so that basis does not hold.
- Changing any definition requires user approval.

## 8. Effort and schedule

Revision 2: about 4 to 5 minutes per segment and about 2 hours in total, split
across sittings. Revision 3 takes 6 to 7 minutes per segment (§10.6, §11.5).
Labelling starts after TASK-121 passes review and the user draws the
regions with TASK-123.

## 9. Revision history

| Revision | Date | Content |
| --- | --- | --- |
| r1 | 2026-10-15 | 100 frames from sample1 and 200 from sample2, image-space gaze points, single-camera gating evaluation (D10). Withdrawn. |
| r2 | 2026-10-15 | This document. Approved by the user the same day, together with the camera roles and the region-marking approach. |
| r3 | 2026-10-18 | §10. The user approved the direction (D20): a hands/held-object class and attention points at gaze changes. The user confirmed the details on 2026-10-29 (Q-017). |
| r3.1 | 2026-10-18 | §10.8, the out-of-view mark. Approved by the user on 2026-10-29 (Q-018). |
| Addendum | 2026-10-29 | §11: the two new recordings as a separate cohort, leave-one-worker-out, per-recording regions. Approved by the user on 2026-10-29 (D26, D27). |

## 10. Revision 3 (2026-10-18)

### 10.1 Why

On 2026-10-18 the user clarified the project goals (`docs/requirements/PROJECT_GOALS_CN.md` v3):

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
- **Class file**: the list is regenerated through the official export path of the region tool. The region polygons stay unchanged, the old export is kept as a backup, and the completion marker is rewritten with the new hashes. The user confirmed this with Q-017 on 2026-10-29.

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
The 8 segments of the new recordings add about 1 hour (§11.5).

### 10.8 Revision 3.1 (proposed 2026-10-18, approved 2026-10-29)

Proposed with the stage-3 system design v2 (`STAGE3_GAZE_ATTENTION_CN.md` §12, item 3) and approved by the user on 2026-10-29 with Q-018. It takes effect together with revision 3, whose details the user confirmed on 2026-10-29 (Q-017):

- **Out-of-view mark**: the worker sometimes looks at targets outside the overview view, such as the machine on the left or the shelves. For a `cell_other` or `hands_object` run whose target lies outside the overview view, the annotator presses one key to mark it out of view instead of clicking a point.
- **Skip** keeps one meaning only: unsure.
- **Schema**: each `point_skips` entry becomes `{step, reason}`, with `reason` either `unsure` or `out_of_view`, where `step` is the run start step. The schema version stays 3 because no formal labels exist yet.
- **Strict validation**: `out_of_view` is allowed only in `cell_other` and `hands_object` runs. A run marked out of view needs no point, and it counts as handled for completion.
- **Evaluation**: these marks evaluate the predicted out-of-view probability (§10.5).

### 10.7 中文摘要

- **类别**：在你画的 4 个目标区域之后，增加“手部/手中物体”（`hands_object`）。看自己的手，或手中、正被手移动的工件与工具时，用这一类，并且它优先于区域。按键依次为 1–4 区域、5 手部/手中物体、6 工作区内其他、7 离开工作、8 不在岗、0 无法判断。
- **注视点**：凡标为目标区域、手部/手中物体或工作区内其他的片段，在全局画面上点一下注视位置，至少一个；拿不准可以标“跳过”。注视位置明显移动时可以多点，最多每秒一个。离开、不在岗、无法判断不点。
- **判断依据**：眼睛可见时以眼睛为准，其次是头部朝向，最后是手部动作。
- **工作量**：每段约 6 至 7 分钟，共约 3 小时，可分多次。
- **用途**：评估注意力热力图的位置误差（先按画面像素，近似标定后按厘米）、手部与物体的识别率，以及区域统计。重复标注的点距可作为人工真值本身的精度参考。
- **r3.1（2026-10-29 你已同意，与 r3 一起生效）**：注视目标在全局画面之外时（例如左侧设备、货架），“工作区内其他”或“手部/手中物体”的片段可以按一个键标为“画面外”，不必点；“跳过”只表示拿不准。见 §10.8。

## 11. Addendum (2026-10-29): new recordings, worker-level splits, per-recording regions

### 11.1 Why

The data provider added two recordings: source folders `20261016` and `20261023`, with burned-in clock dates 2026-10-14 and 2026-10-19. The read-only analysis in `docs/collab/analysis/2026-10-29-workdata-analysis-r2.md` found:

- each adds about 60 minutes of three-camera overlap, plus a webcam (W) that shows the head, hands and desk in one view;
- the workers wear masks, so eye evidence is much scarcer than in the first seven recordings;
- the recording 20261016 contains two workers within its overlap, with about 3 minutes of empty station between them;
- the same day the user identified four workers (P1 to P4) from face crops; one works on several dates, and 20260903 also contains a handover (`docs/collab/analysis/2026-10-29-worker-identity-analysis.md`);
- the cameras are re-placed between recordings, and movable crates and trays change position.

The user approved the recommendations on 2026-10-29 (D26, D27).

### 11.2 Sampling for the new recordings

- **Cohorts**: the first seven recordings form cohort `original`; the two new recordings form cohort `2026-10`. Results are reported per cohort; pooled numbers are given for reference only (coordinator refinement). The `roi_r2` manifest has no `cohort` field, and a missing field means `original`.
- **Count and rules**: 4 segments per new recording, 8 in total, with the stratification and gap rules of §3 and the `sync_uncertain` exclusion of TASK-140.
- **Seed**: the protocol seed 20261015. Each recording has its own generator (the seed plus the session number), so the new draws neither depend on nor change the 26 existing segments.
- **Separate dataset** (implementation detail, coordinator): a label file is bound to the manifest of its dataset. The 8 segments therefore form a sibling dataset in the same format, with its own manifest and labels. The 26-segment dataset, its pilot, frames and labels stay byte-identical.
- **No pilot** (coordinator): the new cohort has no pilot segment; the pilot of §3 remains the shared tool shakedown.
- **Gaps**: the simultaneous gap of about 6 s in A and B in 20261023 counts as a proxy gap.
- **Views**: the annotator sees A, B and E as before. For cohort `2026-10` the tool may also show W as a reference view. Labels and points are still placed on E.

### 11.3 Worker-level splits

- **Worker spans**: a span is the part of one recording in which one worker is at the station. Spans are cut only where the worker changes; a worker who leaves and returns stays in the same span. At a change, the handover period runs from the earlier worker's last confirmed face to the later worker's first confirmed face (A or B, at least 200 px wide at 4K and a detection score of at least 0.5); it belongs to no span. The worker-identity analysis of 2026-10-29 gives 11 spans over the nine recordings, with handovers inside 20260903 and 20261016 (`docs/collab/analysis/2026-10-29-worker-identity-analysis.md` §3). TASK-150 writes the span file, and later tasks use it as is (coordinator refinement).
- **Anonymous worker IDs**: the user gave them on 2026-10-29 after viewing face crops: four workers, P1 to P4. Spans of the same person share an ID. IDs carry no names or personal attributes.
- **Assignment**: a segment belongs to the span with which it overlaps most in time. A segment that lies entirely in an empty period belongs to the nearest span in time. Segments are never redrawn because of their span. With the gap observed in 20261016 (about 3 minutes), no 60-second segment can contain both workers.
- **Evaluation**: leave-one-worker-out over the IDs, with the bootstrap of §7. Each report gives the number of distinct IDs and, per fold, the train and test segment counts and their cohorts. If a fold's training set holds less than half of all segments, or only one cohort, the evaluation stops and the user decides; there is no silent fallback to another split (coordinator refinement, pending the user's confirmation, Q-023). With four workers the folds are unbalanced: of the 34 segments P1 holds about 15 and P4 4 (estimated from the strata). Results are given per worker, and conclusions extend only to these four people.
- **Leave-one-session-out**: not used for formal results, because one person appears in several recordings (P1 in five).

### 11.4 Regions per recording

- The formal regions were drawn on the 20260821 overview frame. The overview camera moved by 10–28 px (1080p) from 2026-09-22, and movable objects change position.
- The regions are registered automatically to each recording's overview view and then reviewed by the user, who may adjust a polygon where an object moved (D27, TASK-151). The per-recording regions are new files; the original files stay unchanged.
- Labels use class names, not polygons, so labelling does not wait for this step. Region-based metrics and the stage-3 heatmaps use the per-recording regions.

### 11.5 Effort

About 6 to 7 minutes per segment, so about 1 hour for the 8 new segments.

### 11.6 中文摘要

- **新录制**：两次新录制作为单独分层（`2026-10`）纳入，各抽 4 段，共 8 段，规则与种子 20261015 不变。每次录制有自己的随机数生成器，所以原 26 段不受影响。
  - 标注文件绑定数据集的清单，所以这 8 段放在一个格式相同的单独数据集里；原数据集、试标段与标注都不变。新分层没有试标段。
  - 20261023 的 A、B 同时中断约 6 秒，按代理缺口处理。
  - 新录制的片段可以另外显示 webcam 作参考，标签与注视点仍标在全局画面上。
- **按作业者留一**：
  - 作业者片段是同一录制中一名作业者在岗的时段，只在换人处切分。交接时段从前一人最后一次确认的人脸，到后一人第一次确认的人脸，不属于任何片段。
  - 你 2026-10-29 判定共 4 名作业者（P1 至 P4）。0903 与 1016 各有一次换班，9 次录制共 11 个片段（见作业者分析）。
  - 片段按时间重叠最多的作业者片段归属，不因归属重抽。
  - 同一人用同一编号。4 折很不均衡（34 段中 P1 约 15 段，P4 4 段），结果按作业者分别报告。
  - 每次评估报告编号个数，以及每折的训练、测试片段数；某一折的训练集不到全部片段的一半或只剩一个分层时，停下来请你决定（待你确认，Q-023）。
  - 按录制留一会让同一人同时出现在训练与测试中，不作为正式结果。
- **区域按录制**：你在 0821 画面上画的区域，先自动配准到每次录制的全局画面，再由你复核，另存为新文件，原文件不改。标注用类别名称，不必等这一步。
- **工作量**：新增 8 段约 1 小时。

## 版本记录

<!-- portal:versions -->
| 版本 | 日期 | 状态 | 变更摘要 | 确认 | 归档 |
| --- | --- | --- | --- | --- | --- |
| 4.1.1 | 2026-10-29 | 已确认 | 录制的称呼统一为源文件夹名（例如 20261016），画面时钟日期只在括号中注明；你确认作业者片段表（Q-024）；内容不变 | 用户 2026-10-29（Q-017、Q-018、Q-020、Q-021、Q-022、Q-024）；待定项见 Q-023 | [v4.1.1](../../archive/VALSET/VALSET_v4.1.1.md) |
| 4.1.0 | 2026-10-29 | 已取代 | 按你 2026-10-29 的身份判定更新 §11：共 4 名作业者、11 个作业者片段，交接时段按确认的人脸界定，4 折不均衡、按作业者分别报告；§7 的依据随之更正；中文摘要同步 | 用户 2026-10-29（Q-017、Q-018、Q-020、Q-021、Q-022）；待定项见 Q-023 | [v4.1.0](../../archive/VALSET/VALSET_v4.1.0.md) |
| 4.0.0 | 2026-10-29 | 已取代 | 按 §5.1 改为主版本：3.2.0 写入的按作业者留一属于评估协议的变化，版本级别在此更正；你确认 r3 的细则（Q-017），状态改为已确认；按独立审查修正 §11：作业者片段只在换人处切分，片段按时间归属、不因归属重抽，留一的预先登记与停止规则（待你确认，Q-023），cohort 缺省为 original；§7、§8 与中文摘要的旧说法更正 | 用户 2026-10-29（Q-017、Q-018、Q-020、Q-021）；待定项见 Q-023 | [v4.0.0](../../archive/VALSET/VALSET_v4.0.0.md) |
| 3.2.0 | 2026-10-29 | 已取代 | r3.1 经你同意（Q-018）；新增 §11：两次新录制作为单独分层，另成一个 8 段的同格式数据集，规则与种子不变；按作业者留一；按录制的区域（D26、D27）；§1、§2、§3、§7、§10 相应修改；r3 的细则仍待确认（Q-017） | Q-017（r3 细则）；r3.1 与 §11 已确认（用户 2026-10-29） | [v3.2.0](../../archive/VALSET/VALSET_v3.2.0.md) |
| 3.1.2 | 2026-10-18 | 已取代 | 文件移入 `docs/design/` 并改为稳定文件名，链接与路径随之更新；内容不变 | Q-017 | [v3.1.2](../../archive/VALSET/VALSET_v3.1.2.md) |
| 3.1.1 | 2026-10-18 | 已取代 | 加入文件头与版本记录；标题去掉 revision 编号；内容不变 | Q-017 | [v3.1.1](../../archive/VALSET/VALSET_v3.1.1.md) |
| 3.1.0 | 2026-10-18 | 已取代 | r3.1 提议：“画面外”标记（§10.8） | Q-017、Q-018 | [v3.1.0](../../archive/VALSET/VALSET_v3.1.0.md) |
| 3.0.0 | 2026-10-18 | 已取代 | r3：“手部/手中物体”类别、注视点、schema v3、新增指标（§10）。快照由 3.1.0 去掉 r3.1 的增补重建 | Q-017 | [v3.0.0](../../archive/VALSET/VALSET_v3.0.0.md) |
| 2.0.1 | 2026-10-15 | 已取代 | 你批准 r2（D12 r2） | 用户 2026-10-15 | [v2.0.1](../../archive/VALSET/VALSET_v2.0.1.md) |
| 2.0.0 | 2026-10-15 | 已取代 | r2：作业数据连续片段的区域标注。r1 未进入 Git，没有留档 | — | [v2.0.0](../../archive/VALSET/VALSET_v2.0.0.md) |
