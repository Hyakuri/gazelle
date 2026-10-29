# Multi-Camera Attention Region Design (proposal)

Status: proposal by the coordinator (Claude), 2026-10-15. It needs user
approval of decisions D13, D14, and D15 in `docs/collab/ROADMAP.md` before any
stage-3 task contract is written. Nothing here is implemented.

Inputs: `docs/collab/PROJECT_GOALS_CN.md` (v2),
`docs/collab/analysis/2026-10-15-workdata-analysis.md`, and
`docs/superpowers/specs/2026-10-15-workdata-validation-set-design.md`.

## 中文摘要

- **问题**：逐时刻判断作业者在看哪个作业区域，并统计占比、时长、切换与离开工作。单台摄像机做不到，需要三台融合。
- **流程**：数据层（清单、重封装、时钟映射、5 Hz 同步代理）；单机证据（A、B 提供头部检测与跟踪、头部姿态、Gaze-LLE 热图与 in/out；E 提供姿态关键点与双手位置）；逐时间步特征表；可解释分类器；时序平滑；停留片段与统计；复核视频与报告。
- **评估**：用区域标注按录制日期留一交叉验证，并与只用单台摄像机、只用头部姿态、只用 Gaze-LLE 的方案比较。原 D10 的门控比较也在这里完成。
- **决策**：D13 分析时间轴为 5 Hz、1080p；D14 区域类别与连续片段标注；D15 融合方法为特征加可解释分类器加时序平滑，几何标定留作后续。
- **风险**：鱼眼畸变、遮挡、作业者与日期之间的差异、标注噪声、俯视摄像机缺少头部、类别不平衡。

## 1. Problem

For each step `t` on the common clock, estimate the attention region
`r(t)` of the worker, with class probabilities, from three fixed cameras:

- A and B: face cameras on the desks. They see the face but not the desks.
- E: corner overview camera. It sees the desks, hands, and torso but rarely
  the head.

Outputs per recording: a step timeline, attention episodes with durations, and
summary statistics: time share per region, dwell-time distribution,
transition counts, the share of `away`, and the share of `absent`.

## 2. Constraints from the data

- Gaze-LLE needs the head and the target in the same image. In A and B, desk
  targets are out of frame; in E, the head is out of frame. Per-camera
  heatmap peaks therefore cannot name a desk region.
- Out-of-frame in A or B does not mean off-task.
- All three lenses are fisheye and uncalibrated.
- Recordings span seven dates and at least two workers.
- The burned-in clocks agree within one second; container time is not
  trustworthy (TASK-133 handles this).

## 3. Architecture

### 3.1 Data layer (stage 2)

Inventory and AVI remux (TASK-132), clock time maps (TASK-133), and 5 Hz
synchronized proxies at 1920×1080 (TASK-134). Frame `k` of every proxy of a
recording shows the same clock instant.

### 3.2 Per-camera evidence (TASK-141)

- A and B: run the existing CLI on each proxy with
  `--head-source mediapipe --max-heads 1 --gazelle-head-mode all`, without
  rendering. Per step, derive: face detected; landmarks available; yaw,
  pitch, and roll from `facial_transformation_matrix` with the sign
  conventions fixed by TASK-002; head box centre and size; Gaze-LLE in/out
  score; heatmap peak; heatmap mass inside per-camera image regions (for
  example the aisle or the jig) drawn once on a reference frame.
- E: run MediaPipe Pose on the proxy and export shoulders, elbows, wrists,
  and visibility. This needs a new exporter; the head provider stays
  unchanged. Derive hands-in-region flags from region polygons drawn on an E
  reference frame, and the shoulder-line angle.
- Missing evidence stays missing: a value plus an availability flag, never a
  fabricated value.

### 3.3 Fusion and temporal model (TASK-142)

- Baselines: (b1) head-pose sectors from A and B; (b2) E hands-in-region;
  (b3) Gaze-LLE features only.
- Main model: multinomial logistic regression and gradient-boosted trees from
  scikit-learn (1.6.1, already in the `Gazelle` environment) on the step
  features with availability flags. Choose by leave-one-session-out macro-F1.
- Temporal smoothing: an HMM decoded with Viterbi, transitions estimated from
  training labels, compared with a median-filter baseline.
- Output per step: class probabilities, smoothed label, evidence availability.

### 3.4 Evaluation (TASK-143)

Metrics from the validation-set design §7, leave-one-session-out. Ablations:
each camera alone, each feature family alone, with and without smoothing.
The former D10 question becomes a feature comparison here: `eligible`,
`observed`, and `all` head selection in A and B.

### 3.5 Outputs and review (TASK-144)

Outside the repository, per recording: `attention_steps.jsonl`,
`attention_episodes.jsonl`, `attention_summary.json`, and a review video with
A, B, and E side by side and the predicted label overlaid. Outputs record the
code commit, configuration, model version, and time-map version.

## 4. Decisions

| Decision | Recommendation | Alternatives |
| --- | --- | --- |
| D13 analysis timeline | 5 Hz on the burned-in clock; 1920×1080 proxies | 10 Hz doubles the cost; native rate is 4 to 5 times the cost and needs per-file timestamp handling downstream |
| D14 labels | Region classes from Q8; continuous 60-second segments labelled at change points | Single frames cannot evaluate durations or episodes |
| D15 fusion | Per-step features, interpretable classifier, HMM smoothing, leave-one-session-out | (a) Geometric: fisheye calibration, extrinsics, 3D gaze rays intersected with desk planes; physically interpretable but needs an on-site calibration session. (b) End-to-end multi-view network; needs far more labels |

Rationale for D13: attention episodes of interest last 0.4 seconds or more,
so 0.2-second steps resolve them, and the frame count drops by about 80%.
Faces in A and B remain 150 to 300 pixels wide at 1080p.

## 5. Risks

- Camera moves between recordings would break image-space features. Check a
  reference-frame similarity score per recording before feature extraction.
- Worker differences: leave-one-session-out exposes them; the 2026-09-01/02
  recording includes another person.
- Label noise between head direction and eye gaze; the `unknown` class and the
  quality checks in the validation design bound it.
- Class imbalance: `away` may be rare; report per-class recall with intervals.
- Compute: about 6.5 hours × 3 cameras × 18,000 steps per hour, about 350,000
  frames. MediaPipe runs on CPU; Gaze-LLE runs on the shared GPU after the
  free-memory check.

## 6. Open questions

Q7 (front and right camera roles), Q8 (region classes and boundaries), and Q9
(worker identity across recordings, future recordings, stable camera
positions) in `docs/collab/PROJECT_GOALS_CN.md`.
