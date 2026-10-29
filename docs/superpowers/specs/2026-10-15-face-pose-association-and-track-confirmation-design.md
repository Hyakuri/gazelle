---
doc_id: PERCEPTION
title: 人脸与姿态关联、新轨迹确认设计（D1、D2）
version: 1.1.2
status: 已确认（协调者）
updated: 2026-10-18
owner: Claude
confirm_ref: 用户 2026-10-15（方向）；协调者 2026-10-18（§4.4）
---
# Face/Pose Association and Spawn-Frame Track Confirmation Design

Status: direction approved by the user on 2026-10-15 (decisions D1 and D2 as
recommended in `docs/collab/analysis/2026-10-14-codebase-analysis.md` §9).
The coordinator (Claude) set the detailed parameters below. Changing any listed
default requires user confirmation.

This design amends `2026-07-21-mediapipe-head-perception-design.md` §12, §13,
and §15. Everything not mentioned here keeps the 07-21 contract.

## 中文摘要

- **D2 新轨迹首帧确认**：ByteTrack 对新轨迹的第一帧固定返回 `-1`，适配层目前直接丢弃，导致每段视频第 0 帧和每个新出现的人的首帧消失。改为在首帧立即分配临时 `person_id`，下一至两帧上游给出正式 ID 时按重叠度关联回同一个 `person_id`。输出新增 `tracking.provisional` 字段，临时 ID 在确认前不进入短遮挡桥接，避免一帧误检产生 500 ms 的幽灵框。
- **D1 人脸与姿态关联**：单人模式不再“分别取最高置信的人脸和姿态再判断是否融合”。所有模式都先从 MediaPipe 取至少 3 个候选，用新增的关键点包含约束做配对，再选出 `--max-heads` 个人。视频中按空间连续性优先保留上一帧选中的主体，避免两个候选置信度接近时在两人之间来回跳。
- 两项都会改变用户可见行为，需要同步四份用户文档，并在真实视频上验收。

## 1. Problems

### 1.1 Spawn-frame drop (GZ-03)

`trackers==2.5.0.post0` returns `tracker_id == -1` for every newly spawned
tracklet (`ByteTrackTracker._spawn_new_tracks`). An ID is allocated only when
the tracklet is matched again on a later frame. With
`minimum_consecutive_frames = 1`, an unconfirmed tracklet survives at most one
missed frame, so confirmation happens one or two frames after the spawn.

`ByteTrackHeadTracker._map_tracked_candidates` drops every `-1` row. As a result:

- frame 0 of every video is `no_head`;
- every new or re-created track loses its first observed frame;
- `track_age_frames` undercounts by one;
- on the spawn frame the output often shows a stale `tracked_only` box of the
  previous identity instead of the fresh observation.

Evidence: both Gate C smoke runs and both of the user's historical real-video
runs start with a `no_head` frame 0; sample2 started 525 tracks, each losing its
spawn frame.

### 1.2 Cross-person face/pose fusion (GZ-01)

With `max_heads == 1`, `build_head_candidates` takes the globally best face and
the globally best pose and fuses them when the 07-21 §12 gate passes
(IoU ≥ 0.10 or center distance ≤ 0.75 × larger diagonal). The gate is too loose
for adjacent people. The backend also returns only one face and one pose in this
mode, so the two may belong to different people.

Evidence: in the Gate C Sunny run, 12 of 14 Gazelle inputs were head boxes
spanning two people (2.0–2.3× the correct width); the gaze peak moved by 0.25
normalized units on average and the in/out decision flipped in 5 of 12 frames.
In the user's sample1 and sample2 runs, 25 and 276 `face_pose` frames had the
pose nose outside the face-derived head box.

## 2. Scope

In scope:

1. Provisional confirmation of ByteTrack spawn rows (D2).
2. A shared perception candidate pool, a keypoint anchor test in the face/pose
   gate, unified matching for every `max_heads`, and continuity-aware selection
   (D1).
3. The additive output field `tracking.provisional`.
4. Tests, the four user documents, and `tests/test_usage_docs.py`.

Non-goals:

- No change to Gazelle model input format, in/out classification, eligibility
  thresholds, or the conservative gate (decision D10 is separate).
- No torso-first tracking and no stable subject ID across tracker identity
  changes (decision D11 is separate).
- No change to `lost_track_buffer`, bridge decay, or `--head-track-max-gap-ms`
  semantics (decision D5 is separate).
- No new CLI option.
- No dependence on private attributes of the upstream tracker.

## 3. D2: spawn-frame confirmation

### 3.1 Row classification

After `tracker.update(detections)`, each output row is one of:

| Row | Condition | Handling |
| --- | --- | --- |
| Known | raw ID already mapped | existing public `person_id` |
| Newly confirmed | raw ID ≥ 0, not yet mapped | link to a pending spawn (§3.2), otherwise allocate a new public ID |
| Spawn | raw ID `-1` and candidate confidence ≥ `track_activation_threshold` (0.50) | provisional public ID (§3.3) |
| Unmatched low score | raw ID `-1` and confidence < 0.50 | dropped, unchanged |

With the fixed configuration (`track_activation_threshold == high_conf_det_threshold == 0.50`,
`minimum_consecutive_frames == 1`), a `-1` row with confidence ≥ 0.50 is exactly a
newly spawned tracklet. Record this assumption next to `_TRACKER_CONFIGURATION`.
If any of these three values changes, the classification must be re-derived.

### 3.2 Pending spawns and linking

- The adapter keeps `pending_spawns: {public_id: (pixel_xyxy, frame_index)}`.
- A pending spawn is valid while `current_frame_index - frame_index ≤ 2`, which
  covers upstream confirmation one or two frames after the spawn. Older entries
  are discarded at the start of each update.
- Linking uses IoU between the row's candidate pixel box and the pending spawn
  box. Accept IoU ≥ `minimum_iou_threshold` (0.20). Resolve conflicts with a
  deterministic greedy assignment sorted by (IoU descending, public ID
  ascending, candidate index ascending). Each pending spawn and each row is used
  at most once.
- Processing order inside one update: known rows, then newly confirmed rows
  (link or allocate), then spawn rows.
- A spawn row first tries to link to a still-valid pending spawn (re-spawn after
  an upstream tracklet died during its first missed frame). If linked, it reuses
  that public ID and refreshes the pending box and frame. Otherwise it allocates
  a new public ID and creates a pending spawn.
- A linked track keeps the first frame of its pending spawn, so
  `track_age_frames` counts from the spawn frame.
- `reset()`, `close()`, and tracker invalidation clear pending spawns.

### 3.3 Provisional identities and the bridge

- `TrackedHeadCandidate` gains `provisional: bool`. It is `True` for spawn rows
  and `False` once the public ID is linked to a raw ID.
- `HeadPerception` gains `provisional: bool = False`, copied from the tracked
  candidate. Image mode and bridged `tracked_only` perceptions are always
  `False`.
- `ShortOcclusionBridge` does not create or refresh bridge state for provisional
  candidates. A confirmed track gets bridge state from its first confirmed
  frame. Consequence: a one-frame false detection appears on exactly one frame
  and never produces `tracked_only` ghosts. A real person whose spawn tracklet
  is missed on the next frame may be absent for that one frame.

### 3.4 Output contract

- `head_observations.json` and `.jsonl` add `tracking.provisional` (boolean,
  always present) next to `track_age_frames`, `missed_frames`, and `missed_ms`.
- Video frame 0 and the first frame of each new track now report the observed
  head with `tracking.provisional = true` and `track_age_frames = 1`.
- `person_id` values remain non-negative and unique per frame. Public IDs are
  still allocated in order of first appearance.

## 4. D1: candidate pool, anchor gate, and continuity selection

### 4.1 Candidate pool

- Define one shared helper, for example `candidate_pool_size(max_heads)` in
  `gazelle/runtime/perception/contracts.py`, returning
  `max(max_heads, 3)`.
- `MediaPipeBackend` keeps the top `candidate_pool_size(max_heads)` face
  detections for Face Landmarker crops and sets
  `PoseLandmarkerOptions(num_poses=candidate_pool_size(max_heads))`.
  `FaceLandmarkerOptions(num_faces=...)` is unchanged.
- `MediaPipeHeadProvider` calls `build_head_candidates(..., max_heads=pool)` and
  passes the whole pool to the tracker in video mode.

Cost: when three or more faces are visible in single-person mode, Face
Landmarker runs on up to three crops instead of one. A single-person scene keeps
the same cost.

### 4.2 Anchor test in the face/pose gate

`associate_face_pose(face, pose)` returns `True` only when both hold:

1. The existing geometric gate (IoU ≥ 0.10 or center distance ≤ 0.75 × larger
   diagonal).
2. The pose anchor test against the face-derived head box `H` (the face
   candidate's `head_bbox`, inclusive bounds):
   - if the pose `nose` keypoint is present, it must lie inside `H`;
   - otherwise, if at least two of `left_eye`, `right_eye`, `left_ear`,
     `right_ear`, `mouth_left`, `mouth_right` are present, at least two of them
     must lie inside `H`;
   - otherwise, if both shoulders are present, the center of `H` must lie
     horizontally between the shoulders and above the shoulder midpoint;
   - otherwise the test fails.

Keypoints are the reliability-filtered `pose_head_keypoints` already stored on
pose candidates.

### 4.3 Unified matching

`build_head_candidates` removes the `max_heads == 1` special path. Every call
builds valid pairs with the strengthened gate, uses the existing cost
`0.60 × normalized_center_distance + 0.40 × (1 − IoU)`, accepts pairs greedily
by `(cost, pose source index, face index)`, keeps unpaired faces and poses as
single-source candidates, sorts by the existing key, and returns the first
`max_heads` entries. Callers that pass `max_heads=1` still receive one
candidate.

### 4.4 Selection

`arbitrate_perceptions(perceptions, *, max_heads, previous_selection=())` gains
an optional `previous_selection`: a tuple of `(person_id, head_bbox)` for the
heads selected on the previous video frame. Selection is deterministic:

1. **Spatial continuity with fresh evidence.** For each previous entry, choose
   the unselected observed perception whose head-box center is closest to the
   previous head-box center, provided the distance is at most the previous box
   diagonal. Ties break by the existing priority key.
2. **Identity continuity through short gaps.** For each previous entry not
   satisfied in step 1, choose the perception with the same `person_id` if it is
   present, including a bridged `tracked_only` perception.
3. **Fill.** Fill remaining slots by the existing priority key (observed first,
   then state, confidence, missed time, track age, ID).
4. Return the selected perceptions in their original order, at most
   `max_heads`.

Video mode stores the selected `(person_id, head_bbox)` pairs after each frame
and calls `bridge.retain_person_ids(selected ids)` for every `max_heads`, not
only for one.

Amendment, 2026-10-18 (TASK-101 contract r2, after D2 and the GZ-30 fix in
TASK-102): bridge maintenance is provisional-neutral. Each frame runs a second
selection over the confirmed (non-provisional) perceptions only, with the same
rules and the same `previous_selection`, and passes those IDs to
`retain_person_ids`. The output still uses the full selection, which may include
provisional heads. A one-frame spawn therefore never changes which bridges are
kept, and a real identity change prunes the old bridge on the frame where the
new identity is confirmed, one frame later than the original wording.

Image mode passes no previous selection. It selects from the pool by the
existing priority key and then assigns `person_id` values `0..n−1` in the
selected order.

Rationale for step 1: in the Sunny clip the two people alternate as the highest
confidence candidate on several frames. Without continuity, single-person output
would jump between them. Step 1 also handles a tracker identity change for the
same physical person, because the new identity is observed at the old location.

### 4.5 Output contract

No schema change beyond §3.4. Observable differences:

- `face_pose` perceptions never combine a face with a pose whose anchors lie
  outside the face-derived head box.
- In single-person mode the chosen person may differ from the previous release
  when several people are visible.
- In video mode the tracker may assign `person_id` values to people who are not
  output, so the output IDs are not guaranteed to start at 0.

## 5. Documentation

Update `README.md`, `README_CN.md`, `docs/usage/USAGE.md`, and `docs/usage/USAGE_CN.md`
together: the `tracking.provisional` field; first-frame behavior; the anchor
rule; the candidate pool of at least three; continuity selection; the
non-contiguous video IDs. Add tokens for these statements to
`tests/test_usage_docs.py` in both guides.

## 6. Tests

All default tests stay offline and use fakes.

D2:

- A fake tracker that reproduces upstream semantics: spawn returns `-1`, the next
  match returns a new raw ID, an unconfirmed tracklet dies after two misses, and
  low-score unmatched rows return `-1`.
- Frame 0 emits the head with `provisional = True` and `track_age_frames = 1`;
  frame 1 keeps the same `person_id` with `provisional = False` and age 2.
- Confirmation after one missed frame links to the same `person_id`.
- Two simultaneous spawns link one-to-one; a far-away new raw ID allocates a new
  ID.
- Low-score `-1` rows never consume an ID.
- A provisional head missed on the next frame produces no `tracked_only` row.
- An opt-in integration test runs the real `trackers` library only when it is
  importable and checks frames 0 and 1.

D1:

- Two adjacent people where the best face belongs to A and the best pose to B:
  no fused candidate spans both; A's face pairs with A's pose when present.
- Each anchor branch: nose, two head keypoints, shoulders only, nothing.
- Alternating confidences across frames keep the same selected person.
- A new tracker identity observed at the previous location replaces a stale
  `tracked_only` of the old identity.
- A missed subject stays selected as `tracked_only` until bridge expiry, then
  selection moves on.
- Image mode returns contiguous IDs from 0.
- The backend requests the pool size for poses and face crops.

## 7. Real validation

Run on local hardware with cached resources only, outputs outside the repository:

- Sunny two-person clip (from `assets/Sunny_1.gif`), conservative and diagnostic
  settings: zero `face_pose` perceptions with the pose nose outside the face
  head box; frame 0 is not `no_head`; report subject switches, eligible frames,
  Gazelle inference count, and in/out distribution against the 2026-10-14
  baseline.
- `assets/the_office.png`: no fused candidate spans two people.
- The user's sample1 and sample2 when the user permits their use: the same
  metrics plus the number of distinct `person_id` values.

## 8. Risks

- IoU linking approximates the upstream Kalman association. Crowded,
  overlapping spawns can link to the wrong pending entry; the effect is one
  wrong ID assignment at confirmation time.
- Continuity can keep an occluded subject for up to the bridge window instead of
  switching to a visible bystander. This is the intended single-worker behavior.
- One-frame false detections now appear for one frame instead of being dropped.
  `tracking.provisional = true` lets analyses exclude them.

## 9. Superseded statements

- 07-21 §12: “The candidates are consistent when either …” now also requires the
  §4.2 anchor test.
- 07-21 §13: “The default single-person mode selects the highest-quality face
  candidate and the highest-quality pose candidate” is replaced by §4.3–§4.4.
- 07-21 §15: tracker IDs are converted to public IDs starting on the spawn frame
  (§3), not on the first upstream-confirmed frame.

## 版本记录

<!-- portal:versions -->
| 版本 | 日期 | 状态 | 变更摘要 | 确认 | 归档 |
| --- | --- | --- | --- | --- | --- |
| 1.1.2 | 2026-10-18 | 已确认（协调者） | 文件移入 `docs/design/` 并改为稳定文件名，链接与路径随之更新；内容不变 | 用户 2026-10-15（方向）；协调者 2026-10-18（§4.4） | [v1.1.2](../../archive/PERCEPTION/PERCEPTION_v1.1.2.md) |
| 1.1.1 | 2026-10-18 | 已取代 | 加入文件头与版本记录，内容不变 | 用户 2026-10-15（方向）；协调者 2026-10-18（§4.4） | [v1.1.1](../../archive/PERCEPTION/PERCEPTION_v1.1.1.md) |
| 1.1.0 | 2026-10-18 | 已取代 | §4.4 修订：临时头中立的保留集合（TASK-101 契约 r2） | 协调者 2026-10-18（B 级） | [v1.1.0](../../archive/PERCEPTION/PERCEPTION_v1.1.0.md) |
| 1.0.0 | 2026-10-15 | 已取代 | D1、D2 设计：单人模式的人脸与姿态关联、新轨迹首帧确认 | 用户 2026-10-15（方向） | [v1.0.0](../../archive/PERCEPTION/PERCEPTION_v1.0.0.md) |
