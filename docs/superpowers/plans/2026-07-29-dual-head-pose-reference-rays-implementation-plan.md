# Dual Head-Pose Reference Rays Implementation Plan

## Milestone 1: Contracts and Geometry

Files:

- `gazelle/runtime/contracts.py`
- `gazelle/runtime/perception/contracts.py`
- `gazelle/runtime/perception/reference_rays.py`
- `tests/test_reference_rays.py`
- `tests/test_perception_contracts.py`

Tasks:

1. Add `GazeStatus`.
2. Add named pose-head keypoints and reference-ray contracts.
3. Implement finite-value validation, normalized endpoint clipping, face-pose
   projection, and pose-keypoint projection.
4. Cover axial, clipped, invalid, independent, and missing-evidence cases.

## Milestone 2: Fusion, Tracking, and Policy

Files:

- `gazelle/runtime/perception/fusion.py`
- `gazelle/runtime/perception/tracking.py`
- `gazelle/runtime/perception/provider.py`
- `gazelle/runtime/perception/gaze_policy.py`
- `tests/test_head_fusion.py`
- `tests/test_head_tracking.py`
- `tests/test_mediapipe_head_provider.py`
- `tests/test_gaze_policy.py`

Tasks:

1. Preserve named Pose Landmarker head points during fusion.
2. Attach both rays to candidates and observed perceptions.
3. Add post-bridge max-head arbitration and stale-state pruning.
4. Mark MediaPipe gaze eligibility conservatively.
5. Select only eligible heads for Gazelle and classify prediction in/out
   status without changing other head providers.

## Milestone 3: Pipeline, Output, Renderer, and CLI

Files:

- `gazelle/runtime/config.py`
- `gazelle/runtime/cli.py`
- `gazelle/runtime/pipeline.py`
- `gazelle/runtime/outputs.py`
- `gazelle/runtime/perception/outputs.py`
- `gazelle/runtime/renderer.py`
- corresponding unit tests

Tasks:

1. Add validated ray and in/out CLI options.
2. Build Gazelle once and only when at least one eligible head exists.
3. Preserve all head observations while passing only eligible heads to
   Gazelle.
4. Serialize reference rays, eligibility, and final gaze status.
5. Render the two rays with distinct colors.
6. Suppress Gazelle heatmap/peak/arrow for non-valid predictions.
7. Render MediaPipe overlays on skipped and no-gaze video frames.

## Milestone 4: Documentation and Verification

Files:

- `README.md`
- `README_CN.md`
- `docs/USAGE.md`
- `docs/USAGE_CN.md`
- `tests/test_usage_docs.py`

Tasks:

1. Document semantics, commands, colors, statuses, and limitations in both
   languages.
2. Run compileall with a temporary pycache prefix.
3. Run all unit tests in the existing `Gazelle` Conda environment.
4. Run CLI help/list-model checks and `git diff --check`.
5. Optionally run bounded sample-video regression without committing outputs.
6. Commit, push the existing branch, and add a bilingual PR #5 comment.

