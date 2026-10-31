# Configurable Gazelle Diagnostics Design

## 1. Goal

Add independent, user-controlled policies for selecting MediaPipe head
observations for Gazelle inference and for rendering Gazelle predictions. The
feature must make suppressed predictions observable during experiments while
keeping the current conservative behavior as the default.

## 2. Motivation

The current runtime has two separate gates:

1. `select_gazelle_heads()` only sends perceptions with conservative
   `gaze_eligible` state to Gazelle.
2. Predictions below `--gaze-inout-threshold` receive `out_of_frame` status,
   and the renderer suppresses their heatmap, gaze arrow, and gaze peak.

Lowering `--gaze-inout-threshold` only changes the second gate. It cannot show
whether Gazelle would have produced a useful result for a low-quality,
pose-only, back-facing, occluded, or temporarily tracked head. The runtime
therefore needs separate inference-selection and rendering controls.

## 3. User Interface

### 3.1 Gazelle head selection

Add a multi-value CLI option:

```text
--gazelle-head-mode SELECTOR [SELECTOR ...]
```

The default is:

```text
--gazelle-head-mode eligible
```

Supported selectors are:

| Selector | Match rule |
| --- | --- |
| `eligible` | Match the existing conservative Gazelle eligibility policy. |
| `observed` | Match every perception with `observed=true`. |
| `all` | Match every head emitted by the provider. |
| `face_pose` | Match `state=face_pose`. |
| `face_only` | Match `state=face_only`. |
| `pose_only` | Match `state=pose_only`. |
| `tracked_only` | Match `state=tracked_only`. |
| `frontal` | Match `view_state=frontal`. |
| `profile` | Match `view_state=profile`. |
| `back_or_occluded` | Match `view_state=back_or_occluded`. |
| `unknown` | Match `view_state=unknown`. |

Multiple selectors use OR semantics. For example:

```text
--gazelle-head-mode face_pose pose_only back_or_occluded
```

selects a perception when its state is `face_pose`, its state is `pose_only`,
or its view state is `back_or_occluded`.

Duplicate selectors are removed while preserving their first occurrence. If
`all` is present, the normalized configuration is exactly `("all",)` because
other selectors cannot broaden it. An empty selector list and unknown values
are rejected during configuration validation.

`eligible` can be combined with explicit selectors. For example,
`eligible pose_only` preserves all conservative selections and additionally
allows pose-only heads.

### 3.2 Gazelle prediction rendering

Add a single-value CLI option:

```text
--gaze-render-mode {valid-only,all-predictions}
```

The default is `valid-only`.

- `valid-only` preserves current rendering and draws Gazelle heatmaps, arrows,
  and peaks only for predictions with `gaze_status=valid`.
- `all-predictions` draws Gazelle heatmaps, arrows, and peaks for every actual
  Gazelle prediction, including `gaze_status=out_of_frame`.

The render mode does not change `gaze_status`, `inout_score`, prediction JSON,
or Gazelle inference selection. Labels continue to expose the original status
and score.

### 3.3 Interaction with the in/out threshold

`--gaze-inout-threshold` remains responsible only for classifying actual
Gazelle predictions as `valid` or `out_of_frame`. It does not select heads for
inference and does not override `--gaze-render-mode`.

This separation allows experiments such as:

```powershell
python main.py `
  --input samples\sample1.mp4 `
  --head-source mediapipe `
  --gazelle-head-mode face_pose face_only pose_only back_or_occluded tracked_only `
  --gaze-render-mode all-predictions `
  --face-pose-ray `
  --pose-head-ray `
  --save-rendered `
  --video-codec avc1 `
  --overwrite
```

## 4. Selection Architecture

`gazelle.runtime.perception.gaze_policy` remains the single owner of Gazelle
head-selection rules. The selection API receives a `HeadFrameResult` and the
normalized selector tuple.

For providers without `HeadPerception` metadata (`none`, `static`, and `json`),
selection remains unchanged and all provider heads are returned. Selector
matching only changes MediaPipe perception behavior.

For MediaPipe results, `result.heads` and `result.perceptions` continue to be
validated for equal length and matching `person_id`. Each perception is
selected when any configured selector matches. Head order remains identical to
provider order.

`tracked_only` selection does not bypass tracking lifetime rules. It can only
select a bridge result already emitted by the provider within the configured
gap and confidence limits. Expired tracks remain absent. Geometry and predictor
bbox validation also remain active.

## 5. Eligibility and Selection Traceability

`HeadPerception.gaze_eligible` retains its existing meaning: whether the
perception satisfies the conservative recommended policy. Diagnostic selection
must not mutate it.

Each serialized perception record adds:

```json
"gazelle_selected": true
```

This field records whether that person was actually selected for Gazelle on
the current frame under `--gazelle-head-mode`. It is independent from
`gaze_eligible`.

Examples:

- Conservative accepted face: `gaze_eligible=true`, `gazelle_selected=true`.
- Pose-only under the default: `gaze_eligible=false`,
  `gazelle_selected=false`.
- Pose-only under `--gazelle-head-mode pose_only`: `gaze_eligible=false`,
  `gazelle_selected=true`.
- Tracked-only under `--gazelle-head-mode all`: `gaze_eligible=false`,
  `gazelle_selected=true`.

Selection must occur before writing image or video head-observation output so
`gazelle_selected` reflects the exact heads used for that frame. Selection is
matched by the ordered head/perception pair rather than by `person_id` alone.

The normalized `gazelle_head_mode` tuple and `gaze_render_mode` string are
stored in `run_config.json` through `RuntimeConfig` serialization.

## 6. Pipeline Behavior

Image and video pipelines pass `config.gazelle_head_mode` to the policy
selector. Existing result statuses keep their meanings:

- `no_head`: the provider emitted no head.
- `no_gaze`: the provider emitted one or more heads, but the configured
  selectors matched none.
- `ok`: Gazelle ran, including runs requested through diagnostic selectors.
- `skipped`: `frame_step` excluded video inference before selection was used.

For skipped video frames, `gazelle_selected` is `false` because no head is sent
to Gazelle on that frame. This avoids claiming selection when inference did not
run. Perception still runs and is serialized as before.

The predictor remains lazily constructed once. Choosing `tracked_only` or
`all` does not cause construction when no provider head is available.

## 7. Renderer Behavior

Add `gaze_render_mode` to `RenderOptions`. A small predicate determines whether
Gazelle geometry is drawable:

- `valid-only`: prediction status must be `valid`.
- `all-predictions`: any actual prediction is drawable.

The predicate applies consistently to heatmap overlays, heatmap contours, gaze
arrows, and gaze peaks in both renderer branches, with and without perception
overlays. Head boxes and labels retain their existing controls. Reference rays
remain independent from Gazelle render mode.

No synthetic heatmap, peak, or arrow is created for `no_head`, `no_gaze`, or
`skipped` frames.

## 8. Validation and Error Handling

Configuration validation must:

- accept a string or iterable representation from direct `RuntimeConfig`
  construction and normalize it to a tuple;
- reject booleans, non-string selector members, empty selector lists, and
  unknown selectors with a message naming `gazelle_head_mode`;
- canonicalize any list containing `all` to `("all",)`;
- reject unknown `gaze_render_mode` values with a message naming that field.

CLI parsing uses the same canonical validation through `RuntimeConfig`, so
programmatic and CLI behavior cannot diverge.

## 9. Test Strategy

Unit and pipeline tests must cover:

- default `eligible` compatibility;
- individual state selectors;
- individual view selectors;
- OR combinations across states and views;
- `eligible` combined with an explicit selector;
- `observed` excluding tracked-only perceptions;
- `all` and explicit `tracked_only` selection;
- selector de-duplication and `all` canonicalization;
- invalid selector and render mode validation;
- selection order and person alignment validation;
- `gazelle_selected` output for selected, rejected, and skipped heads;
- image and video predictor calls under conservative and diagnostic modes;
- `valid-only` suppression of `out_of_frame` geometry;
- `all-predictions` rendering of heatmap, contour, arrow, and peak;
- unchanged status and JSON values under render-only changes;
- CLI parsing and help output for both options.

Tests use fake providers/predictors and synthetic images or temporary videos.
They must not access the network, download models, construct DINOv2, invoke
real CUDA, or run real FFmpeg.

## 10. Documentation

Update all user-facing documentation in sync:

- `README.md`
- `README_CN.md`
- `docs/USAGE.md`
- `docs/USAGE_CN.md`

Documentation must identify `eligible` and `valid-only` as compatible defaults,
explain OR selector semantics, distinguish `gaze_eligible` from
`gazelle_selected`, and warn that diagnostic predictions from occluded or stale
heads are exploratory evidence rather than reliable eye gaze.

## 11. Compatibility and Non-Goals

This milestone does not change model weights, MediaPipe thresholds, bridge
duration, tracker association, bbox validation, in/out score calculation,
reference-ray estimation, audio behavior, FFmpeg encoder selection, or model
resource preparation.

The feature does not claim that Gazelle results from `pose_only`,
`back_or_occluded`, or `tracked_only` inputs are physically accurate. It only
makes those experiments explicit, reproducible, and traceable.

