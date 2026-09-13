# MediaPipe Head Perception and Tracking Design

Status: Approved design

Date: 2026-07-21

Repository: `Hyakuri/gazelle`

Branch: `feature/mediapipe-head-tracking`

Pull request: `#5 Add MediaPipe head perception and tracking`

Base branch: `feature/enhanced-gaze-rendering`

## 1. Summary

Gazelle currently accepts head inputs from `none`, `static`, and `json`
providers. This design adds a MediaPipe-based perception layer that produces a
real head bounding box before Gazelle inference. It combines a full-range face
detector, detailed face landmarks, pose-derived head geometry, ByteTrack identity
association, and a short occlusion bridge.

The head bounding box is the primary Gazelle input. The face bounding box and
face landmarks are auxiliary observations used to improve the head box and to
support later face-aware features. The system is optimized for one worker by
default while keeping ordered, multi-person contracts suitable for up to ten
people.

The first milestone supports the existing single-image and offline streaming
video pipelines. It does not add webcam processing, biometric identification,
ROI/process logic, or Multi-Pose integration.

## 2. Goals

1. Add `mediapipe` as a fourth `HeadProvider` source.
2. Detect a visible face and retain its normalized face bounding box.
3. Expose detailed face landmarks without requiring them in every output file.
4. Derive a larger, Gazelle-ready head bounding box from face and pose evidence.
5. Degrade to pose-derived head geometry when the face is hidden, turned away,
   masked, or otherwise unavailable.
6. Use ByteTrack to keep stable person IDs and support association through weak
   observations.
7. Bridge short gaps for at most 500 milliseconds while labeling predicted
   boxes as `tracked_only`.
8. Process video incrementally without loading all frames or observations into
   memory.
9. Keep existing `none`, `static`, and `json` provider behavior compatible.
10. Keep default tests offline and independent of MediaPipe model downloads,
    Gazelle checkpoint downloads, DINOv2 construction, PyTorch Hub, and CUDA.
11. Record enough observation metadata to diagnose face, pose, fusion, and
    tracking behavior separately from gaze inference.

## 3. Non-goals

The first milestone does not implement:

- Webcam or live-stream UI support.
- Cross-camera re-identification.
- Face recognition or biometric identity matching.
- A dedicated all-angle back-of-head detector.
- Long-duration prediction through complete occlusion.
- Automatic ROI, work-step, or process-state analysis.
- Multi-Pose integration.
- ONNX or TensorRT conversion.
- Asynchronous multi-stage execution.
- Audio preservation or remuxing.
- GitHub Actions.

## 4. Approved decisions

The following decisions are fixed for the first implementation:

- The default pose model is MediaPipe Pose Landmarker Full.
- Pose Landmarker Lite is selectable for performance experiments.
- Pose Landmarker Heavy is supported as a selectable resource but is not the
  default.
- Short occlusion bridging expires after 500 milliseconds by default.
- Rich head observations are written separately from Gazelle predictions.
- All 478 face landmarks are saved only when explicitly requested.
- Facial blendshape output is disabled.
- The facial transformation matrix is enabled when Face Landmarker succeeds.
- Image processing does not create ByteTrack state.
- Video processing creates one tracker for the video and resets it between
  videos.
- Perception and tracking run on every decoded video frame.
- `frame_step` controls Gazelle inference only.
- MediaPipe Tasks use the CPU path in the validated Windows environment.
  Gazelle keeps its existing independent `auto`, `cpu`, or CUDA device behavior.
- The default maximum person count is one. Valid configuration values are one
  through ten.

## 5. Current runtime constraints

The implementation must evolve the existing runtime instead of replacing it:

- `gazelle/runtime/contracts.py` defines the predictor-facing
  `HeadObservation` contract.
- `gazelle/runtime/heads.py` defines `HeadProvider.get_heads(...)` and the three
  existing providers.
- `gazelle/runtime/pipeline.py` owns provider construction and image/video
  routing.
- The current video pipeline skips the provider before calling it when a frame
  is excluded by `frame_step`. This order must change for stateful providers.
- The current provider interface has no lifecycle method. MediaPipe Tasks and
  trackers require deterministic cleanup and reset.
- `predictions.json` and `predictions.jsonl` contain gaze results. Rich head
  observations must not be embedded into these files.
- `gazelle/runtime/resources.py` already provides safe cache-directory creation,
  temporary downloads, atomic replacement, and force-download protection. The
  MediaPipe resource implementation must follow the same safety properties.
- Output-directory conflicts must continue to fail before any provider,
  checkpoint, DINOv2, or MediaPipe model construction.

## 6. Technology and model selection

### 6.1 Face Detector

Use the official MediaPipe Face Detector task with BlazeFace Full Range.

The detector supplies:

- A face bounding box.
- A detection confidence.
- Six coarse face points: both eyes, nose tip, mouth, and both tragions.

Full Range is selected because the workplace camera can place the worker farther
from the camera than a selfie-oriented model expects. Full Range describes
camera distance and framing. It does not detect a fully hidden face or the back
of a head.

Video uses the MediaPipe `VIDEO` running mode. Image input uses `IMAGE` mode.

### 6.2 Face Landmarker

Use the official MediaPipe Face Landmarker model bundle.

The Face Landmarker supplies:

- 478 normalized 3D face landmarks.
- An optional facial transformation matrix.
- Optional blendshapes, which remain disabled in this milestone.

The bundled landmarker contains a short-range face detector. To make detailed
landmarks useful for a more distant worker, each successful full-range face
detection is expanded, clipped, cropped, and passed to Face Landmarker. Returned
landmarks are remapped from crop coordinates into full-frame normalized
coordinates.

Face Landmarker runs only for accepted face detections and only for the highest
scoring `max_heads` detections. This bounds work in the multi-person case.
It uses `IMAGE` running mode for both image and video pipelines because every
invocation receives an independently cropped face ROI. Temporal identity and
continuity belong to ByteTrack rather than the crop-local landmarker.

### 6.3 Pose Landmarker

Use MediaPipe Pose Landmarker Full by default. It supplies 33 normalized image
landmarks and 33 world landmarks. This milestone uses the normalized nose, eyes,
ears, mouth, and shoulders to derive head geometry. World landmarks are retained
internally for later posture work but are not written by default.

Video uses `VIDEO` mode with monotonically increasing timestamps. Image input
uses `IMAGE` mode. Segmentation-mask output remains disabled.

### 6.4 ByteTrack

Use the detector-agnostic `ByteTrackTracker` from the maintained
`roboflow/trackers` package. Do not copy the YOLOX application stack into this
repository.

ByteTrack is responsible for:

- Stable tracker IDs.
- High-confidence association.
- A second association pass for low-confidence detections.
- Retaining lost tracks long enough to support re-association.

ByteTrack does not by itself guarantee that an unmatched lost track is emitted
as a usable observation on every frame. A separate `ShortOcclusionBridge` stores
the most recent observed box and emits an explicitly labeled `tracked_only`
observation for the approved grace period.

## 7. Architecture

The design uses a modular in-process perception chain:

```text
Decoded RGB frame
        |
        +-----------------------+
        |                       |
        v                       v
Full-range Face Detector   Pose Landmarker
        |                       |
        v                       |
Expanded face crops            |
        |                       |
        v                       |
Face Landmarker                |
        |                       |
        +-----------+-----------+
                    |
                    v
          Face/Pose Association
                    |
                    v
             Head Box Fusion
                    |
          +---------+---------+
          |                   |
      image mode          video mode
          |                   |
          |                ByteTrack
          |                   |
          |          ShortOcclusionBridge
          |                   |
          +---------+---------+
                    |
                    v
             HeadFrameResult
              /           \
             v             v
    HeadObservation   HeadPerception
             |             |
             v             v
    GazellePredictor  observation output
```

The components live under `gazelle/runtime/perception/`:

- `contracts.py`: perception-only immutable data contracts and enums.
- `mediapipe_backend.py`: lazy MediaPipe imports, task construction, frame
  conversion, result conversion, crop remapping, and lifecycle management.
- `fusion.py`: face/pose association, candidate quality, head-box geometry, and
  final normalized-box validation.
- `tracking.py`: ByteTrack adapter, ID assignment, tracker reset, and the short
  occlusion bridge.
- `provider.py`: `MediaPipeHeadProvider`, which coordinates the backend, fusion,
  tracking, and conversion to predictor-facing heads.
- `resources.py`: pinned MediaPipe model metadata and safe local preparation.

`gazelle/runtime/heads.py` remains the public home of `HeadProvider` and the
existing providers. It imports the MediaPipe provider lazily only when that
source is selected.

## 8. Data contracts

### 8.1 Existing contract

`HeadObservation` remains unchanged:

```python
@dataclass(frozen=True)
class HeadObservation:
    person_id: int
    bbox: Optional[BBox]
    confidence: Optional[float] = None
```

MediaPipe produces a real normalized head box. `bbox=None` remains reserved for
the existing single-person Gazelle fallback and is never produced by the
MediaPipe provider.

### 8.2 New perception contracts

The perception package introduces immutable contracts with JSON-safe conversion
helpers:

```python
class HeadPerceptionState(str, Enum):
    FACE_POSE = "face_pose"
    FACE_ONLY = "face_only"
    POSE_ONLY = "pose_only"
    TRACKED_ONLY = "tracked_only"

class HeadViewState(str, Enum):
    FRONTAL = "frontal"
    PROFILE = "profile"
    BACK_OR_OCCLUDED = "back_or_occluded"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class NormalizedLandmark:
    x: float
    y: float
    z: Optional[float]
    visibility: Optional[float]
    presence: Optional[float]

@dataclass(frozen=True)
class FaceObservation:
    bbox: BBox
    confidence: float
    keypoints: Tuple[NormalizedLandmark, ...]
    landmarks: Tuple[NormalizedLandmark, ...]
    transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]]

@dataclass(frozen=True)
class PoseObservation:
    pose_index: int
    landmarks: Tuple[NormalizedLandmark, ...]
    world_landmarks: Tuple[NormalizedLandmark, ...]

@dataclass(frozen=True)
class HeadPerception:
    person_id: int
    head_bbox: BBox
    face_bbox: Optional[BBox]
    confidence: float
    state: HeadPerceptionState
    view_state: HeadViewState
    observed: bool
    track_age_frames: int
    missed_frames: int
    missed_ms: float
    face_keypoints: Tuple[NormalizedLandmark, ...]
    pose_head_landmarks: Tuple[NormalizedLandmark, ...]
    facial_transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]]
    face_landmarks: Tuple[NormalizedLandmark, ...]

@dataclass(frozen=True)
class HeadFrameResult:
    heads: Tuple[HeadObservation, ...]
    perceptions: Tuple[HeadPerception, ...]
    timings_ms: Mapping[str, float]
```

The exact dataclass field order is part of the implementation plan. The semantic
contract above is fixed.

### 8.3 HeadProvider compatibility

`HeadProvider.get_heads(...)` remains available. The base class gains:

- `get_frame_result(...)`, whose default implementation wraps existing
  `get_heads(...)` output in a `HeadFrameResult` with no rich perceptions.
- `close()`, whose default implementation is a no-op.
- Context-manager support that calls `close()`.

`MediaPipeHeadProvider` overrides `get_frame_result(...)`. Its `get_heads(...)`
returns `get_frame_result(...).heads`, preserving direct provider use.

The image and video pipelines call `get_frame_result(...)` for all providers.

## 9. Frame conversion and execution order

The decoded PIL RGB image is converted to a contiguous SRGB NumPy array once per
frame and wrapped as a MediaPipe image. Face detection and pose landmarking run
sequentially in the first milestone. This provides deterministic task use and
avoids concurrent calls into native MediaPipe task instances.

The image pipeline order is:

1. Load RGB image.
2. Reject or create the output directory.
3. Prepare and construct the selected head provider.
4. Produce `HeadFrameResult` for frame zero.
5. Write head observations.
6. Construct Gazelle only when at least one head is available.
7. Run Gazelle, write predictions, and render requested output.
8. Close the provider in `finally` or through a context manager.

The video pipeline order for each decoded frame is:

1. Produce a perception result on every frame.
2. Write one head-observation JSONL row.
3. If the frame is excluded by `frame_step`, write gaze status `skipped` and do
   not run Gazelle.
4. If no valid head remains, write gaze status `no_head` and do not run Gazelle.
5. Lazily construct Gazelle on the first frame that requires gaze inference.
6. Run Gazelle and write gaze status `ok`.
7. Render the original frame for `skipped` or `no_head`; render gaze and
   perception overlays for `ok` when rendered output is enabled.
8. Write exactly one gaze JSONL row and one observation JSONL row per processed
   frame.

Lazy Gazelle construction avoids checkpoint download and DINOv2 construction
when a complete image or video has no usable head observations.

## 10. Face crop and landmark remapping

For each accepted full-range face detection, build a crop using the face width
`w` and height `h`:

- Left edge: `x1 - 0.20 * w`.
- Right edge: `x2 + 0.20 * w`.
- Top edge: `y1 - 0.40 * h`.
- Bottom edge: `y2 + 0.15 * h`.

Clip the crop to image bounds and reject it if its pixel width or height is less
than two. Face Landmarker output coordinates are remapped to the full image by
applying the crop origin and crop dimensions before normalization.

The crop factors live in a frozen `FaceCropConfig` so later calibration changes
do not alter unrelated code.

## 11. Pose-derived head geometry

Reliable pose landmarks satisfy both available score checks:

- `visibility >= 0.50` when visibility is present.
- `presence >= 0.50` when presence is present.

The head landmark set is indices 0 through 10. Shoulder indices are 11 and 12.

When at least two reliable head landmarks exist:

1. Compute the median head center.
2. Compute the observed head-point horizontal and vertical spans.
3. If both shoulders are reliable, compute shoulder width.
4. Set the provisional width to the greater of `1.40 * horizontal_span` and
   `0.30 * shoulder_width`.
5. Set the provisional height to the greater of `1.50 * vertical_span` and
   `0.40 * shoulder_width`.
6. Shift the center upward by `0.10 * provisional_height` to include hair or a
   helmet.

When fewer than two reliable head landmarks exist but both shoulders are
reliable:

1. Set center X to the shoulder midpoint.
2. Set head width to `0.42 * shoulder_width`.
3. Set head height to `0.55 * shoulder_width`.
4. Set the lower head edge to `shoulder_midpoint_y - 0.08 * shoulder_width`.
5. Derive the upper edge from the head height.

If neither rule can produce a positive finite box, no pose head candidate is
created. Every provisional result is sanitized and clipped through the existing
geometry API.

The geometry constants live in a frozen `HeadBoxFusionConfig` and are covered by
deterministic geometry tests. Real workplace-video calibration can revise the
configuration defaults in a later reviewed commit without changing contracts.

## 12. Face-derived and fused head boxes

A face-only head box expands the detector box using:

- Left and right: `0.20 * face_width` each.
- Top: `0.45 * face_height`.
- Bottom: `0.10 * face_height`.

When both face and pose candidates exist, first apply a consistency gate. The
candidates are consistent when either:

- Their intersection-over-union is at least `0.10`; or
- The distance between their centers is no greater than `0.75` times the larger
  candidate diagonal.

For consistent candidates, the fused box is their clipped union. For
inconsistent candidates, choose the candidate with the higher quality score and
label the result `face_only` or `pose_only`; do not create an oversized union.

Candidate confidence is defined as:

- Face quality: detector confidence.
- Pose quality: the arithmetic mean of available visibility and presence scores
  for the landmarks used to construct the box.
- Fused quality: `0.50 * face_quality + 0.50 * pose_quality`.

All confidence values are finite and clipped to `[0.0, 1.0]`.

## 13. Face/Pose association

The default single-person mode selects the highest-quality face candidate and
the highest-quality pose candidate, then applies the consistency gate.

For two through ten people, build valid face/pose pairs using the same gate. The
pair cost is:

```text
0.60 * normalized_center_distance + 0.40 * (1.0 - IoU)
```

Sort pairs by `(cost, pose_index, face_index)` and greedily accept pairs while
neither candidate has been used. Remaining face and pose candidates become
single-source head candidates. Sort final candidates by descending confidence,
then by top edge, left edge, and source index. This produces deterministic input
for tracking and image-mode person ID assignment.

The first milestone is optimized and smoke-tested for one person. Multi-person
contract and deterministic tests cover up to ten synthetic candidates, but a
real multi-person quality benchmark is deferred.

## 14. View state and head pose

When Face Landmarker returns a transformation matrix, convert its rotation to
Euler angles using `R = Rz(roll) * Ry(yaw) * Rx(pitch)`. Serialized values use
degrees and these display-oriented signs:

- Positive yaw means the face turns toward the right side of the displayed
  image.
- Positive pitch means the face turns downward in the displayed image.
- Positive roll means clockwise rotation in the displayed image.

Adapter tests use fixed rotation matrices to lock these signs and the singular
case behavior. Classify view state as:

- `frontal` when absolute yaw is less than 35 degrees.
- `profile` when absolute yaw is at least 35 degrees.
- `unknown` when the matrix is invalid or unavailable while a face exists.

When no face exists but pose produces a head box, use `back_or_occluded`. This
name is deliberate: Pose landmarks alone cannot reliably distinguish a fully
back-facing head from severe face occlusion. Numeric yaw, pitch, and roll remain
absent in this state.

Tracked-only frames retain the last observed view state and mark it as stale in
the serialized record through `observed=false` and positive `missed_ms`.

## 15. Tracking and short occlusion behavior

The ByteTrack adapter receives pixel-space XYXY head detections, confidence
scores, frame index, and source FPS. It converts returned tracker IDs into
non-negative `person_id` values.

Initial tracker configuration is:

- `track_activation_threshold = 0.50`.
- `high_conf_det_threshold = 0.50`.
- `minimum_iou_threshold = 0.20`.
- `minimum_consecutive_frames = 1`.
- `lost_track_buffer = 15` in the tracker's 30 FPS units.
- Actual `frame_rate` is the resolved source FPS.

The 15-frame buffer corresponds to approximately 500 milliseconds after the
tracker applies its documented FPS scaling.

`ShortOcclusionBridge` stores the most recent observed normalized box and
confidence for each confirmed tracker ID. On an unmatched frame it:

1. Updates ByteTrack with an empty detection collection.
2. Reuses the last observed box without inventing new image evidence.
3. Sets state to `tracked_only` and `observed=false`.
4. Sets confidence to `last_confidence * exp(-missed_ms / 500.0)`.
5. Emits the box only while `missed_ms <= 500.0` and confidence is at least
   `0.15`.
6. Removes bridge state after expiry.

This conservative last-box bridge avoids depending on private ByteTrack Kalman
state and makes the distinction between observed and predicted boxes explicit.

The tracker updates on every decoded frame, including frames on which Gazelle is
skipped. It resets at the beginning of each video and closes at the end.

## 16. Output contracts

The existing gaze files remain backward compatible:

- Image: `predictions.json`.
- Video: `predictions.jsonl`.

Add one independent observation file for every provider:

- Image: `head_observations.json`.
- Video: `head_observations.jsonl`.

Existing providers write minimal observation records. MediaPipe writes rich
records. Each video row has this stable top-level structure:

```json
{
  "frame_index": 12,
  "timestamp_ms": 400.0,
  "status": "ok",
  "width": 1920,
  "height": 1080,
  "provider": "mediapipe",
  "timings_ms": {
    "face_detector": 3.2,
    "face_landmarker": 7.4,
    "pose_landmarker": 11.8,
    "fusion_tracking": 0.5,
    "total": 22.9
  },
  "people": []
}
```

Each MediaPipe person record contains:

- `person_id`.
- `head_bbox_normalized`.
- `face_bbox_normalized`, or null.
- `confidence`.
- `state`.
- `view_state`.
- `observed`.
- `track_age_frames`.
- `missed_frames`.
- `missed_ms`.
- Six full-frame normalized face keypoints when available.
- Pose head and shoulder landmarks used by fusion.
- Facial transformation matrix and yaw/pitch/roll when available.
- `face_landmarks` only when `--save-face-landmarks` is enabled.

Observation status values are `ok` and `no_head`. A Gazelle-skipped frame can
still have observation status `ok`, because `frame_step` does not skip
perception.

The gaze JSONL status remains `ok`, `no_head`, `skipped`, or `error`. Raw
MediaPipe landmarks are never embedded in the gaze prediction schema.

`run_config.json` records provider configuration, selected MediaPipe model
variants, thresholds, resolved resource paths, runtime package versions, and
whether full landmarks were saved.

## 17. Rendering behavior

`PredictionRenderer` remains compatible with callers that pass only gaze
predictions. Its frame method gains an optional perception collection.

Perception overlays use separate, configurable layers:

- Head box: primary Gazelle input box.
- Face box: thinner auxiliary box.
- Face detector keypoints.
- Pose head and shoulder points.
- Optional full face mesh.
- Person ID, perception state, and confidence label.

`tracked_only` boxes use a visually distinct dashed or reduced-opacity style.
Rendering never changes the boxes sent to Gazelle. Full face-mesh drawing is off
by default because it is visually dense and adds per-frame drawing cost.

The implementation plan separates core perception from optional overlay work so
fusion and tracking can be tested before rendering is added.

## 18. CLI and configuration

Add these user-facing options:

- `--head-source mediapipe`.
- `--max-heads N`, integer from 1 through 10, default 1.
- `--pose-model lite|full|heavy`, default `full`.
- `--head-track-max-gap-ms FLOAT`, finite and positive, default 500.
- `--save-face-landmarks`.

The first milestone keeps detector and landmark thresholds at the documented
MediaPipe default of 0.50. They are represented in a frozen internal config so a
later calibration milestone can expose them without changing provider logic.

`--prepare-only --head-source mediapipe` prepares the selected Gazelle checkpoint
and all selected MediaPipe assets. `--force-download` applies safe replacement
semantics to both resource groups.

Image mode ignores tracking duration because it creates no tracker. Invalid
MediaPipe-only options with a different head source are accepted and recorded
but have no effect, matching the existing pattern for media-specific options.

## 19. Resource preparation

MediaPipe assets live below the existing cache root:

```text
models/
  checkpoints/
  torch_hub/
  mediapipe/
    face_detector/
    face_landmarker/
    pose_landmarker/
    .downloads/
```

Resource rules are:

1. Use versioned official model URLs rather than mutable `latest` aliases.
2. Record filename, source URL, expected size when available, and SHA-256 in a
   registry.
3. Download into `.downloads` below the MediaPipe cache directory.
4. Verify that the downloader created the expected file.
5. Verify SHA-256 before replacing a cached asset.
6. Replace the destination atomically only after verification.
7. Preserve the previous cached model when forced replacement fails.
8. Remove temporary download directories in `finally`.
9. Never commit model assets or cache directories.

All official assets and their hashes must be verified through a real preparation
run before the resource commit is merged. Unit tests use fake URLs, fake hashes,
and fake downloaders.

## 20. Dependency and environment policy

The feature requires the MediaPipe Python package and the maintained Trackers
package. Imports remain lazy so users of `none`, `static`, and `json` can import
and test the runtime without those optional packages being initialized.

Before changing the validated `Gazelle` Conda environment:

1. Inspect installed package versions.
2. Run dependency resolution in a cloned or disposable environment.
3. Check NumPy, OpenCV, Pillow, protobuf, MediaPipe, and Trackers compatibility.
4. Run a MediaPipe import and minimal task-construction smoke test.
5. Obtain explicit user permission before installing into the existing
   `Gazelle` environment.

Do not replace, downgrade, or prune the working environment to satisfy an old
environment file. After real validation, update `environment.yml`, `README.md`,
and `README_CN.md` together with the versions that were actually tested.

If the MediaPipe source is selected without its dependencies, fail with a clear
runtime error that names the missing package and does not affect other providers.

## 21. Error handling and cleanup

- Reject an existing output directory before model or provider construction
  unless overwrite is enabled.
- Treat malformed model resources and checksum mismatches as fatal preparation
  errors.
- Reject non-monotonic video timestamps before calling MediaPipe video methods.
- Reject non-finite landmarks, confidences, matrices, and boxes at adapter
  boundaries.
- Clip valid boxes through the existing geometry API.
- Do not call Gazelle when the active head tuple is empty.
- Abort the run on a MediaPipe task exception in the first milestone. Do not
  silently turn task failures into `no_head`.
- Close Face Detector, Face Landmarker, Pose Landmarker, ByteTrack state, output
  writers, and video readers through context managers or `finally` blocks.
- Preserve already written JSONL rows if a later frame fails; propagate the
  original exception after cleanup.
- Do not emit a tracked-only head after the configured grace period.

## 22. Testing strategy

### 22.1 Default unit tests

Default tests use fake MediaPipe task results and a fake tracker adapter. They do
not import native MediaPipe tasks unless an adapter import-safety test explicitly
uses a stub module.

Add focused test modules:

- `tests/test_perception_contracts.py`.
- `tests/test_mediapipe_resources.py`.
- `tests/test_mediapipe_backend.py`.
- `tests/test_head_fusion.py`.
- `tests/test_head_tracking.py`.
- `tests/test_mediapipe_head_provider.py`.

Update existing tests:

- `tests/test_runtime_cli.py` for parsing, validation, routing, and import safety.
- `tests/test_image_pipeline.py` for observation output, no-head lazy Gazelle
  construction, provider cleanup, and MediaPipe factory injection.
- `tests/test_video_pipeline.py` for per-frame provider calls, frame-step
  behavior, stable IDs, short gaps, long gaps, row counts, and cleanup.
- `tests/test_outputs.py` for minimal and rich observation serialization.
- Renderer tests for optional perception layers and tracked-only styling.

Required behavior tests include:

- Face-only expansion produces a valid normalized head box.
- Pose landmarks produce a valid head box.
- Shoulder fallback produces a valid head box.
- Consistent face and pose boxes fuse.
- Inconsistent candidates select the higher-quality source.
- Invalid or degenerate candidates are rejected.
- Person ordering is deterministic.
- ByteTrack receives every decoded frame.
- The same track ID remains stable across observed frames.
- A gap of 500 milliseconds or less emits `tracked_only`.
- A gap over 500 milliseconds emits no head.
- Tracked-only confidence decays and never increases.
- `frame_step` skips Gazelle but not perception.
- Gaze and observation JSONL row counts equal `frames_written`.
- Existing providers continue to work without MediaPipe installed.
- No-head input avoids Gazelle model construction.
- Provider and task close methods run on success and failure.

### 22.2 Optional real validation

Real smoke tests run only in the existing local Conda environment `Gazelle`
after dependency changes are explicitly approved. They use temporary image,
video, output, and model-cache locations or ignored cache paths.

The real scenario matrix includes:

- Frontal face.
- Left and right profile.
- Looking downward while wearing a safety helmet.
- Protective glasses.
- Face mask.
- Partial face occlusion.
- Full turn away from the camera.
- Motion blur.
- Occlusion shorter than 500 milliseconds.
- Occlusion longer than 500 milliseconds.

Record per-stage timings, end-to-end FPS, valid head-box rate, person-ID changes,
tracked-only duration, and whether Gazelle inference was run. Do not claim
real-time performance until measurements are reported.

## 23. Performance rules

- Construct each MediaPipe task once per image run or video run.
- Construct ByteTrack once per video.
- Construct Gazelle lazily and at most once per run.
- Convert each decoded frame to a MediaPipe image once.
- Limit face-landmarker crops to `max_heads`.
- Keep all video processing streaming.
- Avoid retaining image arrays in track history.
- Keep full 478-point serialization disabled by default.
- Measure face detector, face landmarker, pose landmarker, fusion/tracking,
  Gazelle, rendering, and total frame time independently.

Pose Full is the quality baseline. If the perception front end is too slow for
the deployment target, benchmark Pose Lite with the same scenario matrix before
introducing frame skipping or concurrency. Gazelle `frame_step` remains an
independent gaze-throughput control.

## 24. Delivery sequence

Implementation is divided into reviewable milestones:

1. Dependency compatibility spike with no changes to the validated environment.
2. Perception contracts, provider lifecycle, and fake backend seams.
3. Safe MediaPipe resource registry and preparation.
4. MediaPipe backend adapters and crop remapping.
5. Head-box fusion and image-pipeline integration.
6. ByteTrack adapter, short occlusion bridge, and video-pipeline scheduling.
7. Observation JSON/JSONL output and lazy Gazelle construction.
8. Optional perception rendering controls.
9. Synchronized English and Chinese documentation.
10. Approved environment update and real image/video smoke validation.

Each milestone keeps default tests offline. Each user-facing CLI, dependency,
download, output, or usage change updates both README files in the same commit or
milestone.

## 25. Completion criteria

The first feature milestone is complete when:

1. `--head-source mediapipe` works for image and offline video input.
2. A visible face produces face metadata and a normalized head box.
3. Pose can produce a head box without a visible face.
4. Face and pose candidates fuse deterministically.
5. Video person IDs are stable through ordinary motion.
6. Short missing observations produce explicit `tracked_only` heads for no more
   than the configured grace period.
7. Expired tracks stop producing Gazelle inputs.
8. Perception updates on every decoded video frame regardless of `frame_step`.
9. Gazelle receives ordered, valid `HeadObservation` values.
10. Empty heads avoid Gazelle inference and model construction.
11. Image and video observation sidecars are written with stable schemas.
12. Optional full face landmarks can be saved without changing gaze schemas.
13. Existing providers and prediction outputs remain compatible.
14. Default tests require no network, model download, DINOv2, PyTorch Hub, CUDA,
    native MediaPipe models, or external media files.
15. README.md and README_CN.md remain synchronized for all user-facing changes.
16. Real validation results accurately report environment, resources, timings,
    limitations, and any failures.

## 26. Known limitations

- BlazeFace Full Range still requires visible facial evidence and is not a
  back-of-head detector.
- Pose-only head geometry is an estimate and is less precise than a visible face.
- `back_or_occluded` intentionally combines two cases that Pose alone cannot
  distinguish reliably.
- ByteTrack associates detections but does not create new visual evidence during
  complete occlusion.
- The 500-millisecond bridge reuses the last observed box and can lag rapid head
  movement.
- Face mesh quality can degrade under extreme profile, masks, glasses, helmets,
  blur, and low resolution.
- Multi-person contracts support up to ten people, but the first real validation
  target is a single worker.
- End-to-end real-time performance depends on camera resolution, CPU, selected
  Pose model, Gazelle model, GPU, rendering, and output settings.

## 27. References

- MediaPipe Face Detector:
  https://developers.google.com/edge/mediapipe/solutions/vision/face_detector
- MediaPipe Face Landmarker:
  https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- MediaPipe Pose Landmarker:
  https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- Roboflow Trackers ByteTrack documentation:
  https://trackers.roboflow.com/develop/trackers/bytetrack/
- Roboflow Trackers repository:
  https://github.com/roboflow/trackers
