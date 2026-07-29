# Dual Head-Pose Reference Rays and Conservative Gaze Policy

## Goal

Add two independent, uncalibrated 2D head-pose reference rays so MediaPipe
orientation estimates can be compared with Gazelle scene-gaze predictions,
while suppressing Gazelle inference and rendering when the current head
observation is stale, occluded, or too weak to support a precise gaze claim.

The rays are directional references, not calibrated eye-gaze measurements.

## Scope

This milestone adds:

- a face-based reference ray using MediaPipe Face Landmarker head pose and
  face detector keypoints;
- a pose-based reference ray using named MediaPipe Pose Landmarker head
  keypoints;
- post-bridge single-person arbitration;
- conservative Gazelle input eligibility;
- per-person gaze status;
- an in/out rendering threshold;
- JSON/JSONL serialization, CLI controls, tests, and bilingual documentation.

Torso-first tracking, scene-cut detection, camera calibration, ROI fusion, and
3D gaze reconstruction remain separate follow-up milestones.

## Data Flow

```text
frame
  +-- MediaPipe Face Detector / Face Landmarker
  |     +-- face keypoints + transformation matrix
  |     +-- face head-pose reference ray
  |
  +-- MediaPipe Pose Landmarker
        +-- named nose/eye/ear/mouth/shoulder keypoints
        +-- pose head-pose reference ray
                    |
              head candidate
                    |
          tracker + occlusion bridge
                    |
       post-bridge max-head arbitration
                    |
          conservative gaze policy
             /                \
     Gazelle eligible       continuity only
             |                   |
        in/out gate          no Gazelle call
             \                   /
       renderer + JSON/JSONL outputs
```

## Contracts

`PoseHeadKeypoints` preserves the semantic MediaPipe Pose landmark names that
are currently lost when unreliable points are filtered.

`ReferenceRay2D` contains:

- `source`;
- normalized `origin`;
- optional normalized unit `direction`;
- optional normalized `endpoint`;
- `confidence`;
- `projection_status`.

The two independent optional fields on a candidate/perception are:

- `face_pose_reference_ray`;
- `pose_head_reference_ray`.

An axial face direction has no honest 2D line projection. It is represented by
an origin with `projection_status=axial_projection` and no direction/endpoint,
allowing the renderer to draw an origin marker instead of inventing a line.

## Face Reference Ray

The face ray requires current face detector keypoints and a finite Face
Landmarker head pose. The eye midpoint is preferred as the origin, with the
face-box center as a validated fallback only when enough current face
keypoints remain available.

Yaw and pitch are projected into the image plane. The vector is normalized and
extended by a configurable multiple of the normalized head-box diagonal, then
clipped to the image boundary. Near-zero image-plane magnitude is classified
as an axial projection.

## Pose Reference Ray

The pose ray is computed independently from named Pose Landmarker points. It
requires the nose plus a reliable bilateral eye pair or ear pair. The
horizontal component comes from nose displacement relative to the pair
midpoint. The vertical component removes a documented neutral anatomical
offset before normalization.

Shoulders may support the head box but never create a precise pose reference
ray by themselves. Missing or unreliable geometry produces no pose ray.

## Gaze Policy

MediaPipe perceptions are eligible for Gazelle only when they are current,
face-observed, not classified as back/occluded, and contain a valid face
reference observation. Other head providers retain their existing behavior.

Pre-inference perception output uses:

- `gaze_eligible=true` with no final gaze status; or
- `gaze_eligible=false` with one of:
  - `unavailable_occluded`;
  - `tracked_no_gaze`;
  - `rejected_low_quality`.

After Gazelle inference, each prediction receives:

- `valid`; or
- `out_of_frame`.

The renderer draws Gazelle heatmaps, peaks, and arrows only for `valid`
predictions. Both reference rays remain independently renderable even when
Gazelle is suppressed.

## Single-Person Arbitration

For `max_heads=1`, arbitration runs after the occlusion bridge:

1. a current observed perception outranks every stale tracked-only perception;
2. otherwise the strongest tracked-only perception is retained;
3. discarded bridge identities are pruned so they cannot reappear on the next
   missing frame.

This closes the path where one pre-tracking candidate becomes multiple
post-bridge Gazelle inputs.

## CLI

New options:

- `--face-pose-ray`;
- `--pose-head-ray`;
- `--reference-ray-length`;
- `--gaze-inout-threshold`.

Ray drawing is opt-in to preserve existing rendered output defaults.
Observation JSON/JSONL stores available ray data regardless of render flags.

## Compatibility

- Static, JSON, and none head providers keep their current Gazelle behavior.
- Existing `render_predictions(...)` callers remain compatible.
- Default tests remain offline and do not construct Gazelle, DINOv2, MediaPipe
  task models, or CUDA workloads.

