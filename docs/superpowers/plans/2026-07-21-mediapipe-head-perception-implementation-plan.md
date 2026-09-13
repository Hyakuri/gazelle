# MediaPipe Head Perception and Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MediaPipe face/pose perception, fused Gazelle-ready head boxes, ByteTrack identity continuity, explicit short-occlusion behavior, and independent observation outputs to the existing image and offline video runtime.

**Architecture:** Keep `HeadObservation` as the predictor-facing contract and add a separate immutable perception model under `gazelle/runtime/perception/`. Existing providers gain a compatible frame-result and lifecycle layer; MediaPipe adapters, fusion, tracking, resources, serialization, and rendering remain independently testable. Video perception runs on every decoded frame, while `frame_step` gates Gazelle only.

**Tech Stack:** Python 3.11, MediaPipe Tasks 0.10.35, BlazeFace Full Range, Face Landmarker, Pose Landmarker Lite/Full/Heavy, Trackers 2.5.0.post0 ByteTrack, Pillow, NumPy 1.26.4, OpenCV 4.11.0.86, PyTorch 2.6.0+cu126, `unittest`.

## Global Constraints

- Work only on `feature/mediapipe-head-tracking` and PR #5.
- Keep PR #5 based on `feature/enhanced-gaze-rendering`.
- Do not create another branch or PR.
- Do not modify Multi-Pose.
- Do not add GitHub Actions, merge a PR, rebase pushed history, or force push.
- Do not commit model files, checkpoints, Torch Hub cache, outputs, generated media, `__pycache__`, dependency reports, or temporary test files.
- Do not modify the existing Conda environment `Gazelle` until the dependency task reaches its explicit environment-change approval gate.
- Do not create a new Conda environment or run `conda env update --prune`.
- Use `C:\Users\yun\anaconda3\envs\Gazelle\python.exe` for validation.
- Use a temporary `PYTHONPYCACHEPREFIX` for `compileall`.
- Default tests must not import real MediaPipe native tasks, access the network, download models, construct DINOv2, access PyTorch Hub, or use real CUDA.
- Preserve existing `none`, `static`, and `json` provider behavior.
- Preserve `predictions.json` and `predictions.jsonl` schemas.
- Update `README.md` and `README_CN.md` together for every CLI, dependency, download, output, or usage change.
- Keep MediaPipe and Trackers imports lazy.
- Check output-directory conflicts before provider, resource, checkpoint, or predictor construction.
- Run perception and ByteTrack on every decoded video frame; apply `frame_step` only after perception.
- Default `max_heads=1`, valid range 1 through 10.
- Default pose model is `full`.
- Default tracked-only grace period is 500 milliseconds.
- Save 478-point face landmarks only when `--save-face-landmarks` is set.
- After each milestone commit, push the branch and add a PR #5 comment containing Goal, Changes, Validation, Real model/network activity, Known limitations, and Commit.

---

## File Map

### New runtime files

- `gazelle/runtime/perception/__init__.py`: stable perception exports only.
- `gazelle/runtime/perception/contracts.py`: immutable perception dataclasses and enums.
- `gazelle/runtime/perception/resources.py`: MediaPipe model registry, cache paths, verified download, and preparation.
- `gazelle/runtime/perception/mediapipe_backend.py`: lazy MediaPipe imports, task lifecycle, crop handling, result conversion, and Euler conversion.
- `gazelle/runtime/perception/fusion.py`: face expansion, pose head geometry, face/pose association, confidence, and fusion.
- `gazelle/runtime/perception/tracking.py`: ByteTrack adapter and 500 ms short-occlusion bridge.
- `gazelle/runtime/perception/provider.py`: `MediaPipeHeadProvider` orchestration.
- `gazelle/runtime/perception/outputs.py`: image JSON and video JSONL observation serialization.

### Existing runtime files to modify

- `gazelle/runtime/heads.py:16`: compatible frame-result and lifecycle APIs.
- `gazelle/runtime/config.py:111`: MediaPipe and perception rendering configuration.
- `gazelle/runtime/cli.py:9`: CLI options, preparation output, and output-path reporting.
- `gazelle/runtime/pipeline.py:50`: provider factory, image integration, video scheduling, and lazy Gazelle construction.
- `gazelle/runtime/renderer.py:350`: optional perception overlays.
- `environment.yml`: validated dependency pins only after approval and real import validation.
- `README.md`: English setup, preparation, image/video use, output schema, and limitations.
- `README_CN.md`: synchronized Chinese documentation.

### New tests

- `tests/test_perception_contracts.py`.
- `tests/test_mediapipe_resources.py`.
- `tests/test_mediapipe_backend.py`.
- `tests/test_head_fusion.py`.
- `tests/test_head_tracking.py`.
- `tests/test_mediapipe_head_provider.py`.

### Existing tests to modify

- `tests/test_heads.py`.
- `tests/test_runtime_cli.py`.
- `tests/test_outputs.py`.
- `tests/test_image_pipeline.py`.
- `tests/test_video_pipeline.py`.
- `tests/test_renderer.py`.

---

### Task 1: Add Perception Contracts and HeadProvider Lifecycle

**Files:**
- Create: `gazelle/runtime/perception/__init__.py`
- Create: `gazelle/runtime/perception/contracts.py`
- Modify: `gazelle/runtime/heads.py:16`
- Create: `tests/test_perception_contracts.py`
- Modify: `tests/test_heads.py`

**Interfaces:**
- Consumes: existing `BBox` and `HeadObservation` from `gazelle.runtime.contracts`.
- Produces: `HeadPerceptionState`, `HeadViewState`, `NormalizedLandmark`, `HeadPoseAngles`, `FaceObservation`, `PoseObservation`, `HeadCandidate`, `HeadPerception`, and `HeadFrameResult`.
- Produces: `HeadProvider.get_frame_result(...)`, `HeadProvider.close()`, `HeadProvider.__enter__()`, and `HeadProvider.__exit__()`.

- [ ] **Step 1: Write failing contract tests**

Add tests that instantiate every frozen contract, reject mutation, and verify that the default provider wrapper preserves tuple ordering:

```python
class RecordingProvider(HeadProvider):
    def get_heads(self, frame, frame_index, timestamp_ms, image_width, image_height):
        return (
            HeadObservation(person_id=4, bbox=(0.1, 0.2, 0.3, 0.4), confidence=0.8),
            HeadObservation(person_id=7, bbox=(0.5, 0.2, 0.7, 0.4), confidence=0.6),
        )


def test_default_frame_result_wraps_existing_provider(self):
    provider = RecordingProvider()
    result = provider.get_frame_result(None, 3, 100.0, 640, 480)
    self.assertEqual([head.person_id for head in result.heads], [4, 7])
    self.assertEqual(result.perceptions, ())
    self.assertEqual(dict(result.timings_ms), {})
```

Also add `test_head_provider_context_manager_closes_once` using a provider whose `close()` increments a counter.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_perception_contracts tests.test_heads -v
```

Expected: import or attribute failures for `gazelle.runtime.perception.contracts` and `get_frame_result`.

- [ ] **Step 3: Implement the exact contracts**

Use these enum values and signatures:

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
class HeadPoseAngles:
    yaw_deg: float
    pitch_deg: float
    roll_deg: float


@dataclass(frozen=True)
class NormalizedLandmark:
    x: float
    y: float
    z: Optional[float] = None
    visibility: Optional[float] = None
    presence: Optional[float] = None


@dataclass(frozen=True)
class FaceObservation:
    bbox: BBox
    confidence: float
    keypoints: Tuple[NormalizedLandmark, ...] = ()
    landmarks: Tuple[NormalizedLandmark, ...] = ()
    transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    head_pose: Optional[HeadPoseAngles] = None


@dataclass(frozen=True)
class PoseObservation:
    pose_index: int
    landmarks: Tuple[NormalizedLandmark, ...]
    world_landmarks: Tuple[NormalizedLandmark, ...] = ()


@dataclass(frozen=True)
class HeadCandidate:
    source_index: int
    head_bbox: BBox
    face_bbox: Optional[BBox]
    confidence: float
    state: HeadPerceptionState
    view_state: HeadViewState
    observed: bool = True
    face_keypoints: Tuple[NormalizedLandmark, ...] = ()
    pose_head_landmarks: Tuple[NormalizedLandmark, ...] = ()
    facial_transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    head_pose: Optional[HeadPoseAngles] = None
    face_landmarks: Tuple[NormalizedLandmark, ...] = ()


@dataclass(frozen=True)
class HeadPerception:
    person_id: int
    head_bbox: BBox
    face_bbox: Optional[BBox]
    confidence: float
    state: HeadPerceptionState
    view_state: HeadViewState
    observed: bool
    track_age_frames: int = 0
    missed_frames: int = 0
    missed_ms: float = 0.0
    face_keypoints: Tuple[NormalizedLandmark, ...] = ()
    pose_head_landmarks: Tuple[NormalizedLandmark, ...] = ()
    facial_transformation_matrix: Optional[Tuple[Tuple[float, ...], ...]] = None
    head_pose: Optional[HeadPoseAngles] = None
    face_landmarks: Tuple[NormalizedLandmark, ...] = ()


@dataclass(frozen=True)
class HeadFrameResult:
    heads: Tuple[HeadObservation, ...]
    perceptions: Tuple[HeadPerception, ...] = ()
    timings_ms: Mapping[str, float] = field(default_factory=dict)
```

Validate finite numeric fields at adapter, fusion, tracking, and serializer
boundaries rather than adding behavior to these dataclasses. Re-export only
public contracts from `perception/__init__.py`.

Extend `HeadProvider` without changing existing subclasses:

```python
def get_frame_result(self, frame, frame_index, timestamp_ms, image_width, image_height):
    heads = tuple(self.get_heads(frame, frame_index, timestamp_ms, image_width, image_height))
    return HeadFrameResult(heads=heads)

def close(self):
    return None

def __enter__(self):
    return self

def __exit__(self, exc_type, exc_value, traceback):
    self.close()
    return False
```

- [ ] **Step 4: Run focused and existing head tests**

Run the command from Step 2.

Expected: all contract and provider tests pass without importing MediaPipe.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/__init__.py gazelle/runtime/perception/contracts.py gazelle/runtime/heads.py tests/test_perception_contracts.py tests/test_heads.py
git commit -m "Add perception frame contracts"
git push origin feature/mediapipe-head-tracking
```

---

### Task 2: Add MediaPipe Runtime Configuration

**Files:**
- Modify: `gazelle/runtime/config.py:111`
- Modify: `gazelle/runtime/cli.py:9`
- Modify: `tests/test_runtime_cli.py`

**Interfaces:**
- Consumes: `RuntimeConfig.from_args()` and current argparse construction.
- Produces: `max_heads`, `pose_model`, `head_track_max_gap_ms`, and `save_face_landmarks` configuration.
- Produces validators `validate_max_heads`, `validate_pose_model`, and `validate_positive_finite_float`.

- [ ] **Step 1: Add failing CLI and validator tests**

Cover this successful parse:

```python
config = parse_runtime_config(
    [
        "--input", "worker.mp4",
        "--head-source", "mediapipe",
        "--max-heads", "3",
        "--pose-model", "lite",
        "--head-track-max-gap-ms", "750",
        "--save-face-landmarks",
    ]
)
self.assertEqual(config.head_source, "mediapipe")
self.assertEqual(config.max_heads, 3)
self.assertEqual(config.pose_model, "lite")
self.assertEqual(config.head_track_max_gap_ms, 750.0)
self.assertTrue(config.save_face_landmarks)
```

Add failures for `max_heads` values 0, 11, and `True`; pose model `medium`; and gap values 0, negative, NaN, infinity, and boolean. Verify default values `1`, `full`, `500.0`, and `False`.

- [ ] **Step 2: Run the CLI tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_runtime_cli -v
```

Expected: argparse rejects `mediapipe` and `RuntimeConfig` lacks the new fields.

- [ ] **Step 3: Implement CLI and config fields**

Add argparse options exactly as follows:

```python
parser.add_argument("--max-heads", type=int, default=1)
parser.add_argument("--pose-model", choices=("lite", "full", "heavy"), default="full")
parser.add_argument("--head-track-max-gap-ms", type=float, default=500.0)
parser.add_argument("--save-face-landmarks", action="store_true")
```

Extend `--head-source` choices to include `mediapipe`. Add validated dataclass fields:

```python
max_heads: int = 1
pose_model: str = "full"
head_track_max_gap_ms: float = 500.0
save_face_landmarks: bool = False
```

`validate_max_heads` accepts real `int` values from 1 through 10 and rejects `bool`. `validate_positive_finite_float` accepts a non-boolean `Real` whose float conversion is finite and greater than zero. `validate_pose_model` accepts only the three CLI choices.

- [ ] **Step 4: Run CLI and baseline tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_runtime_cli tests.test_image_pipeline tests.test_video_pipeline -v
```

Expected: all tests pass; no MediaPipe import occurs.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/config.py gazelle/runtime/cli.py tests/test_runtime_cli.py
git commit -m "Add MediaPipe runtime configuration"
git push origin feature/mediapipe-head-tracking
```

---

### Task 3: Add Safe MediaPipe Resource Preparation

**Files:**
- Create: `gazelle/runtime/perception/resources.py`
- Modify: `gazelle/runtime/resources.py:41`
- Modify: `gazelle/runtime/cli.py:156`
- Create: `tests/test_mediapipe_resources.py`
- Modify: `tests/test_resources.py`
- Modify: `tests/test_runtime_cli.py`

**Interfaces:**
- Produces: `MediaPipeAssetSpec`, `MediaPipeResourcePaths`, and `PreparedMediaPipeResources`.
- Produces: `resolve_mediapipe_resource_paths(cache_dir)`, `get_required_mediapipe_specs(pose_model)`, `ensure_mediapipe_asset(...)`, and `prepare_mediapipe_resources(config)`.
- Extends: `prepare-only` so `head_source=mediapipe` prepares both Gazelle and selected MediaPipe resources.

- [ ] **Step 1: Record exact production asset hashes outside the repository**

Use these versioned official URLs, download only to a temporary directory, and calculate SHA-256 with `Get-FileHash`:

```text
https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_full_range/float16/1/blaze_face_full_range.tflite
https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task
```

Do not write these downloads under the repository. Record each exact digest in `MEDIAPIPE_ASSET_SPECS`. If any URL fails or a file is empty, stop the task and report the failed asset instead of using a mutable `latest` URL.

- [ ] **Step 2: Write failing resource tests**

Use fake specs and fake downloaders to cover:

```python
def test_force_download_failure_preserves_cached_asset(self):
    asset_path.write_bytes(b"old")
    with self.assertRaisesRegex(RuntimeError, "preserved"):
        ensure_mediapipe_asset(spec, paths, force_download=True, downloader=failing_downloader)
    self.assertEqual(asset_path.read_bytes(), b"old")

def test_hash_mismatch_rejects_download(self):
    with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
        ensure_mediapipe_asset(spec, paths, downloader=wrong_content_downloader)
```

Also test cache reuse, missing downloaded file, atomic replacement, cleanup of `.downloads`, selected pose variant, and cache root priority `--cache-dir -> GAZELLE_CACHE_DIR -> models`.

- [ ] **Step 3: Run resource tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_mediapipe_resources tests.test_resources -v
```

Expected: import failure for `gazelle.runtime.perception.resources`.

- [ ] **Step 4: Implement registry and atomic download**

Use these signatures:

```python
@dataclass(frozen=True)
class MediaPipeAssetSpec:
    key: str
    filename: str
    url: str
    sha256: str

@dataclass(frozen=True)
class MediaPipeResourcePaths:
    root_dir: Path
    mediapipe_dir: Path
    downloads_dir: Path

@dataclass(frozen=True)
class PreparedMediaPipeResources:
    face_detector_path: Path
    face_landmarker_path: Path
    pose_landmarker_path: Path
    pose_model: str
    cache_paths: MediaPipeResourcePaths
```

Download into `.downloads/<key>/<filename>`, verify existence and SHA-256, then call `Path.replace(destination)`. Preserve a previous destination on every failure and remove the task-specific temporary directory in `finally`.

In CLI `prepare-only`, call `prepare_mediapipe_resources(config)` only when `config.head_source == "mediapipe"`. Print `face_detector`, `face_landmarker`, `pose_landmarker`, and `pose_model` paths after Gazelle resource output.

- [ ] **Step 5: Run resource and CLI tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_mediapipe_resources tests.test_resources tests.test_runtime_cli -v
```

Expected: all tests pass with fake downloaders and no network.

- [ ] **Step 6: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/resources.py gazelle/runtime/resources.py gazelle/runtime/cli.py tests/test_mediapipe_resources.py tests/test_resources.py tests/test_runtime_cli.py
git commit -m "Add MediaPipe resource preparation"
git push origin feature/mediapipe-head-tracking
```

---

### Task 4: Implement Lazy MediaPipe Task Adapters

**Files:**
- Create: `gazelle/runtime/perception/mediapipe_backend.py`
- Create: `tests/test_mediapipe_backend.py`

**Interfaces:**
- Consumes: `PreparedMediaPipeResources`, `FaceObservation`, `PoseObservation`, `NormalizedLandmark`, and `HeadPoseAngles`.
- Produces: `FaceCropConfig`, `MediaPipeTaskBundle`, `MediaPipeFrameObservations`, `MediaPipeBackend.create(...)`, `MediaPipeBackend.observe(...)`, and `MediaPipeBackend.close()`.

- [ ] **Step 1: Write fake-task adapter tests**

Create fake detector, face-landmarker, and pose-landmarker objects with `detect`, `detect_for_video`, and `close`. Cover:

- One PIL-to-SRGB conversion per frame.
- `IMAGE` calls for image detector and pose tasks.
- `VIDEO` calls with integer monotonic timestamps for video detector and pose tasks.
- Face Landmarker always using crop-local `detect` in image mode.
- Crop expansion and full-frame landmark remapping.
- Highest-confidence `max_heads` face limit.
- 478 landmarks retained in memory.
- Facial transformation matrix converted to display-oriented Euler angles.
- Positive yaw right, positive pitch down, positive roll clockwise.
- Every task closed exactly once on success and failure.
- Missing `mediapipe` raises a clear `RuntimeError` only when backend construction is requested.

Use fixed rotation matrices for 20-degree yaw, pitch, and roll and assert within `1e-5` degrees.

- [ ] **Step 2: Run backend tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_mediapipe_backend -v
```

Expected: module import failure.

- [ ] **Step 3: Implement backend boundaries**

Use a lazy helper:

```python
def import_mediapipe():
    try:
        import mediapipe as mp
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MediaPipe head detection requires the 'mediapipe' package"
        ) from exc
    return mp
```

Use these main APIs:

```python
@dataclass(frozen=True)
class FaceCropConfig:
    expand_left: float = 0.20
    expand_right: float = 0.20
    expand_top: float = 0.40
    expand_bottom: float = 0.15
    min_size_pixels: int = 2


@dataclass(frozen=True)
class MediaPipeFrameObservations:
    faces: Tuple[FaceObservation, ...]
    poses: Tuple[PoseObservation, ...]
    timings_ms: Mapping[str, float]
```

Implement `MediaPipeBackend.create(resources, *, media_type, max_heads,
task_factory=None) -> MediaPipeBackend`, `observe(frame, *, frame_index,
timestamp_ms, image_width, image_height) -> MediaPipeFrameObservations`, and
`close() -> None` with the behavior listed in this task. `task_factory` receives
the three resolved model paths, the detector/pose running mode, `max_heads`, and
the fixed face-crop image mode.

Face crop factors are left/right `0.20`, top `0.40`, and bottom `0.15`. Reject crops smaller than two pixels. Sort face detections by descending confidence before applying `max_heads`. Use `perf_counter()` to record `face_detector`, `face_landmarker`, `pose_landmarker`, and `total` timings.

For video, convert `timestamp_ms` to a rounded non-negative integer and reject values that do not strictly increase after conversion. Face Landmarker remains in `IMAGE` mode because it receives independent crops.

- [ ] **Step 4: Run backend and import-safety tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_mediapipe_backend tests.test_runtime_cli -v
```

Expected: all pass without constructing native tasks.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/mediapipe_backend.py tests/test_mediapipe_backend.py
git commit -m "Add MediaPipe task adapters"
git push origin feature/mediapipe-head-tracking
```

---

### Task 5: Implement Face/Pose Association and Head Box Fusion

**Files:**
- Create: `gazelle/runtime/perception/fusion.py`
- Create: `tests/test_head_fusion.py`

**Interfaces:**
- Consumes: frame-local `FaceObservation` and `PoseObservation` tuples.
- Produces: `HeadBoxFusionConfig`, `expand_face_to_head_bbox`, `build_pose_head_candidate`, `associate_face_pose`, `fuse_head_candidates`, and `build_head_candidates`.

- [ ] **Step 1: Write failing deterministic geometry tests**

Cover the approved constants and exact cases:

```python
def test_face_only_expansion(self):
    bbox = expand_face_to_head_bbox((0.2, 0.3, 0.4, 0.5))
    self.assertBBoxAlmostEqual(bbox, (0.16, 0.21, 0.44, 0.52))

def test_inconsistent_face_pose_selects_higher_quality(self):
    candidates = build_head_candidates(
        faces=(make_face((0.05, 0.05, 0.15, 0.15), confidence=0.9),),
        poses=(make_pose_head_at(0.8, 0.8, quality=0.6),),
        max_heads=1,
    )
    self.assertEqual(candidates[0].state, HeadPerceptionState.FACE_ONLY)
```

Also cover head landmarks, shoulder fallback, missing shoulders, non-finite points, clipping, IoU gate, center-distance gate, union fusion, confidence clipping, deterministic one-person behavior, and deterministic synthetic ten-person ordering.

- [ ] **Step 2: Run fusion tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_head_fusion -v
```

Expected: module import failure.

- [ ] **Step 3: Implement approved geometry and association**

Use frozen configs:

```python
@dataclass(frozen=True)
class HeadBoxFusionConfig:
    min_visibility: float = 0.50
    min_presence: float = 0.50
    face_expand_x: float = 0.20
    face_expand_top: float = 0.45
    face_expand_bottom: float = 0.10
    min_consistent_iou: float = 0.10
    max_center_distance_diagonal_ratio: float = 0.75
```

Implement pose geometry exactly from design section 11. Calculate pair cost as:

```python
cost = 0.60 * normalized_center_distance + 0.40 * (1.0 - iou)
```

Greedily accept sorted `(cost, pose_index, face_index)` pairs, keep unpaired candidates, then sort final candidates by descending confidence, top, left, and source index. Call `sanitize_normalized_bbox` on every output path.

Set `view_state` from face angles: frontal for absolute yaw below 35 degrees, profile otherwise, unknown for face without valid angles, and back-or-occluded for pose-only.

- [ ] **Step 4: Run fusion and geometry tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_head_fusion tests.test_geometry -v
```

Expected: all pass.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/fusion.py tests/test_head_fusion.py
git commit -m "Add head observation fusion"
git push origin feature/mediapipe-head-tracking
```

---

### Task 6: Add ByteTrack Adapter and Short Occlusion Bridge

**Files:**
- Create: `gazelle/runtime/perception/tracking.py`
- Create: `tests/test_head_tracking.py`

**Interfaces:**
- Consumes: ordered `HeadCandidate` tuples, frame index, timestamp, image size, and source FPS.
- Produces: `TrackedHeadCandidate`, `ByteTrackHeadTracker.update(...)`, `ByteTrackHeadTracker.reset()`, `ByteTrackHeadTracker.close()`, and `ShortOcclusionBridge.update(...)`.
- Supports injected tracker factories so default tests do not import Trackers or Supervision.

- [ ] **Step 1: Write failing tracker and bridge tests**

Use a fake tracker that returns stable IDs and records calls. Cover:

```python
def test_bridge_emits_tracked_only_for_500_ms(self):
    bridge = ShortOcclusionBridge(max_gap_ms=500.0)
    observed = bridge.update((tracked_candidate(3, confidence=0.8),), timestamp_ms=0.0)
    missing = bridge.update((), timestamp_ms=500.0)
    self.assertEqual(missing[0].person_id, 3)
    self.assertEqual(missing[0].state, HeadPerceptionState.TRACKED_ONLY)
    self.assertFalse(missing[0].observed)

def test_bridge_expires_after_500_ms(self):
    bridge = ShortOcclusionBridge(max_gap_ms=500.0)
    bridge.update((tracked_candidate(3),), timestamp_ms=0.0)
    self.assertEqual(bridge.update((), timestamp_ms=500.1), ())
```

Also assert confidence equals `last_confidence * exp(-missed_ms / 500.0)`, never increases, stops below `0.15`, stores no image arrays, rejects non-monotonic timestamps, updates the tracker with empty detections, resets between videos, and lazy dependency errors name `trackers` or `supervision`.

- [ ] **Step 2: Run tracking tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_head_tracking -v
```

Expected: module import failure.

- [ ] **Step 3: Implement the adapter and bridge**

Use this public adapter result:

```python
@dataclass(frozen=True)
class TrackedHeadCandidate:
    person_id: int
    candidate: HeadCandidate
    track_age_frames: int
```

Implement `ByteTrackHeadTracker.update(candidates, *, frame_index,
timestamp_ms, image_width, image_height) -> Tuple[TrackedHeadCandidate, ...]`
with the conversion below.

Create Supervision detections with a stable candidate index:

```python
detections = sv.Detections(
    xyxy=np.asarray(pixel_boxes, dtype=np.float32),
    confidence=np.asarray(confidences, dtype=np.float32),
    class_id=np.zeros(len(candidates), dtype=np.int32),
    data={"candidate_index": np.arange(len(candidates), dtype=np.int32)},
)
tracked = self._tracker.update(detections)
```

Use `sv.Detections.empty()` when no candidates exist. Construct `ByteTrackTracker` with the exact approved values: activation `0.50`, high-confidence threshold `0.50`, minimum IoU `0.20`, one consecutive frame, lost buffer `15`, and resolved source FPS.

The bridge reuses only the last observed normalized box. It does not access private Kalman state and does not extrapolate motion. Delete state after the time or confidence cutoff.

- [ ] **Step 4: Run tracking tests**

Run the command from Step 2.

Expected: all pass with fake tracker modules.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/tracking.py tests/test_head_tracking.py
git commit -m "Add ByteTrack head tracking"
git push origin feature/mediapipe-head-tracking
```

---

### Task 7: Compose MediaPipeHeadProvider and Provider Factory

**Files:**
- Create: `gazelle/runtime/perception/provider.py`
- Modify: `gazelle/runtime/perception/__init__.py`
- Modify: `gazelle/runtime/pipeline.py:50`
- Create: `tests/test_mediapipe_head_provider.py`
- Modify: `tests/test_image_pipeline.py`
- Modify: `tests/test_video_pipeline.py`

**Interfaces:**
- Consumes: prepared resources, `MediaPipeBackend`, fusion functions, `ByteTrackHeadTracker`, and `ShortOcclusionBridge`.
- Produces: `MediaPipeHeadProvider.create(config, media_type, source_fps, ...)`, `get_frame_result(...)`, `get_heads(...)`, and `close()`.
- Extends: `build_head_provider_from_config(config, media_type="image", source_fps=30.0, backend_factory=None, tracker_factory=None)`.

- [ ] **Step 1: Write failing provider composition tests**

Use fake backend/fusion/tracker objects. Cover image mode without tracker, video mode with tracker, ordered IDs, normalized non-null head boxes, rich perception copying, timings aggregation, all-empty result, full landmark retention, `get_heads` compatibility, and idempotent close.

Add factory tests:

```python
provider = build_head_provider_from_config(
    make_config(head_source="mediapipe"),
    media_type="video",
    source_fps=25.0,
    backend_factory=fake_backend_factory,
    tracker_factory=fake_tracker_factory,
)
self.assertIsInstance(provider, MediaPipeHeadProvider)
self.assertEqual(fake_tracker_factory.source_fps, 25.0)
```

- [ ] **Step 2: Run provider tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_mediapipe_head_provider tests.test_image_pipeline tests.test_video_pipeline -v
```

Expected: provider import/factory failures.

- [ ] **Step 3: Implement provider orchestration**

Use this main method shape:

```python
def get_frame_result(self, frame, frame_index, timestamp_ms, image_width, image_height):
    observed = self._backend.observe(
        frame,
        frame_index=frame_index,
        timestamp_ms=timestamp_ms,
        image_width=image_width,
        image_height=image_height,
    )
    candidates = build_head_candidates(
        observed.faces,
        observed.poses,
        max_heads=self._max_heads,
    )
    perceptions = self._assign_people(candidates, frame_index, timestamp_ms)
    heads = tuple(
        HeadObservation(item.person_id, item.head_bbox, item.confidence)
        for item in perceptions
    )
    return HeadFrameResult(heads=heads, perceptions=perceptions, timings_ms=timings)
```

Image IDs are deterministic zero-based order. Video IDs come from ByteTrack. Do not emit MediaPipe `bbox=None`. `close()` closes backend and tracker even if one close call raises; retain and re-raise the first exception after attempting all cleanup.

Factory code must import `MediaPipeHeadProvider` inside the mediapipe branch only.

- [ ] **Step 4: Run provider and existing factory tests**

Run the command from Step 2.

Expected: all pass without real MediaPipe or Trackers.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/provider.py gazelle/runtime/perception/__init__.py gazelle/runtime/pipeline.py tests/test_mediapipe_head_provider.py tests/test_image_pipeline.py tests/test_video_pipeline.py
git commit -m "Add MediaPipe head provider"
git push origin feature/mediapipe-head-tracking
```

---

### Task 8: Add Independent Head Observation Serialization

**Files:**
- Create: `gazelle/runtime/perception/outputs.py`
- Modify: `gazelle/runtime/outputs.py:82`
- Create or modify: `tests/test_outputs.py`

**Interfaces:**
- Produces: `head_frame_to_json_dict(...)`, `write_head_observations_json(...)`, and reusable `JsonlWriter` output for observation rows.
- Consumes: `HeadFrameResult`, provider name, frame metadata, and `save_face_landmarks`.

- [ ] **Step 1: Write failing serialization tests**

Cover minimal provider output, rich MediaPipe output, no-head output, timings, angles, matrices, keypoints, pose points, and optional face-landmark omission/inclusion.

Use this assertion for the privacy/size default:

```python
record = head_frame_to_json_dict(
    frame_index=2,
    timestamp_ms=66.6,
    image_width=640,
    image_height=480,
    provider="mediapipe",
    result=rich_result,
    save_face_landmarks=False,
)
self.assertNotIn("face_landmarks", record["people"][0])
```

For `save_face_landmarks=True`, assert exactly 478 serialized points. For existing providers with empty `perceptions`, serialize `person_id`, `head_bbox_normalized`, and `confidence` directly from `result.heads` without inventing a perception state.

- [ ] **Step 2: Run output tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_outputs -v
```

Expected: missing observation serializer functions.

- [ ] **Step 3: Implement stable JSON-safe conversion**

Top-level observation records contain:

```python
record = {
    "frame_index": int(frame_index),
    "timestamp_ms": float(timestamp_ms),
    "status": "ok" if result.heads else "no_head",
    "width": int(image_width),
    "height": int(image_height),
    "provider": provider,
    "timings_ms": {key: float(value) for key, value in result.timings_ms.items()},
    "people": people,
}
```

Validate all serialized numerics as finite. Preserve tuple ordering. Never include raw tensors. Keep existing gaze serializer functions unchanged.

- [ ] **Step 4: Run output tests**

Run the command from Step 2.

Expected: all existing gaze and new observation output tests pass.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/perception/outputs.py gazelle/runtime/outputs.py tests/test_outputs.py
git commit -m "Add head observation outputs"
git push origin feature/mediapipe-head-tracking
```

---

### Task 9: Integrate Perception into the Image Pipeline

**Files:**
- Modify: `gazelle/runtime/pipeline.py:188`
- Modify: `gazelle/runtime/cli.py:185`
- Modify: `tests/test_image_pipeline.py`
- Modify: `tests/test_runtime_cli.py`

**Interfaces:**
- Extends: `ImagePipelineResult` with `head_observations_path: Path` and `head_result: HeadFrameResult`.
- Writes: `head_observations.json` for every head source.
- Keeps: existing prediction, heatmap, rendering, and run-config paths.

- [ ] **Step 1: Write failing image-pipeline tests**

Cover:

- Existing output directory rejected before provider construction.
- Provider used as a context manager and closed on success/failure.
- `get_frame_result` called once.
- `head_observations.json` exists for none/static/json/mediapipe fakes.
- Empty heads write no-head observations and do not call `predictor_factory`.
- Non-empty heads construct predictor once and preserve person order.
- CLI prints `head_observations: <path>`.

Use this guard:

```python
def predictor_factory(_config):
    raise AssertionError("predictor should not be constructed without heads")

result = run_image_pipeline(config, predictor_factory=predictor_factory)
self.assertEqual(result.predictions, ())
```

- [ ] **Step 2: Run image tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_image_pipeline tests.test_runtime_cli -v
```

Expected: missing result fields and observation file.

- [ ] **Step 3: Implement image scheduling**

Use this order:

```python
image, width, height = load_image_rgb(config.input_path)
output_dir = create_output_dir(
    config.input_path,
    config.output_dir,
    overwrite=config.overwrite,
)
with build_head_provider_from_config(config, media_type="image") as provider:
    head_result = provider.get_frame_result(image, 0, 0.0, width, height)
    head_observations_path = output_dir / "head_observations.json"
    write_head_observations_json(
        head_observations_path,
        frame_index=0,
        timestamp_ms=0.0,
        image_width=width,
        image_height=height,
        provider=config.head_source,
        result=head_result,
        save_face_landmarks=config.save_face_landmarks,
    )
    if head_result.heads:
        predictor = predictor_factory(config) if predictor_factory else _build_real_predictor(config)
        predictions = tuple(predictor.predict_frame(image, head_result.heads))
    else:
        predictions = ()
```

Continue writing existing outputs. Pass `head_result.heads` to existing prediction serialization. Add output path and result fields without removing current fields.

- [ ] **Step 4: Run image and predictor tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_image_pipeline tests.test_predictor tests.test_runtime_cli -v
```

Expected: all pass.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/pipeline.py gazelle/runtime/cli.py tests/test_image_pipeline.py tests/test_runtime_cli.py
git commit -m "Integrate MediaPipe image inference"
git push origin feature/mediapipe-head-tracking
```

---

### Task 10: Integrate Per-Frame Perception and Tracking into Video

**Files:**
- Modify: `gazelle/runtime/pipeline.py:250`
- Modify: `gazelle/runtime/cli.py:195`
- Modify: `tests/test_video_pipeline.py`
- Modify: `tests/test_runtime_cli.py`

**Interfaces:**
- Extends: `VideoPipelineResult` with `head_observations_jsonl_path: Path`.
- Writes: one observation JSONL row and one gaze JSONL row per `frames_written`.
- Lazily constructs Gazelle on the first non-skipped frame with at least one head.

- [ ] **Step 1: Write failing video scheduling tests**

Required tests:

- `test_perception_runs_on_every_frame_when_frame_step_is_two`.
- `test_frame_step_skips_gazelle_after_perception`.
- `test_missing_head_writes_no_head_without_predictor`.
- `test_predictor_is_built_once_on_first_usable_frame`.
- `test_head_observation_rows_match_frames_written`.
- `test_gaze_rows_match_frames_written`.
- `test_provider_receives_source_fps`.
- `test_provider_closes_on_reader_or_predictor_failure`.
- `test_existing_output_dir_rejects_before_provider`.
- `test_max_frames_limits_both_output_files`.
- `test_tracked_only_head_can_run_gazelle`.
- `test_cli_prints_head_observations_jsonl`.

For a four-frame video with `frame_step=2`, assert provider calls `[0, 1, 2, 3]`, predictor calls `[0, 2]`, and gaze statuses `ok, skipped, ok, skipped`.

- [ ] **Step 2: Run video tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_video_pipeline tests.test_runtime_cli -v
```

Expected: provider is currently skipped on odd frames and output path is absent.

- [ ] **Step 3: Implement the streaming order**

Build provider after output-directory creation with `media_type="video"` and `source_fps=resolve_video_fps(metadata.fps, config.output_fps)`. Initialize `predictor = None`.

Inside the loop:

```python
head_result = provider.get_frame_result(
    frame.image,
    frame.index,
    frame.timestamp_ms,
    metadata.width,
    metadata.height,
)
head_jsonl_writer.write(
    head_frame_to_json_dict(
        frame_index=frame.index,
        timestamp_ms=frame.timestamp_ms,
        image_width=metadata.width,
        image_height=metadata.height,
        provider=config.head_source,
        result=head_result,
        save_face_landmarks=config.save_face_landmarks,
    )
)

if frame.index % config.frame_step != 0:
    status = "skipped"
    predictions = ()
elif not head_result.heads:
    status = "no_head"
    predictions = ()
else:
    if predictor is None:
        predictor = predictor_factory(config) if predictor_factory else _build_real_predictor(config)
    predictions = tuple(predictor.predict_frame(frame.image, head_result.heads))
    status = "ok"
```

Write both JSONL rows before incrementing `frames_written`. Close observation writer, gaze writer, provider, renderer writer, and reader on every exit path. Keep video streaming and do not retain old frames.

- [ ] **Step 4: Run video, media, and output tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_video_pipeline tests.test_media tests.test_outputs tests.test_runtime_cli -v
```

Expected: all pass; test videos exist only in temporary directories.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/pipeline.py gazelle/runtime/cli.py tests/test_video_pipeline.py tests/test_runtime_cli.py
git commit -m "Integrate MediaPipe video tracking"
git push origin feature/mediapipe-head-tracking
```

---

### Task 11: Add Optional Perception Rendering Layers

**Files:**
- Modify: `gazelle/runtime/renderer.py:350`
- Modify: `gazelle/runtime/config.py:111`
- Modify: `gazelle/runtime/cli.py:9`
- Modify: `gazelle/runtime/pipeline.py:142`
- Modify: `tests/test_renderer.py`
- Modify: `tests/test_runtime_cli.py`
- Modify: `tests/test_image_pipeline.py`
- Modify: `tests/test_video_pipeline.py`

**Interfaces:**
- Extends: `RenderOptions` with `draw_face_box`, `draw_face_keypoints`, `draw_pose_head_points`, `draw_face_mesh`, and `draw_track_state`.
- Extends: `PredictionRenderer.render(image, predictions, perceptions=())`.
- Adds CLI: `--face-box`, `--face-keypoints`, `--pose-head-points`, `--face-mesh`, and `--no-track-state`.

- [ ] **Step 1: Write failing renderer and CLI tests**

Cover defaults, parsing, unchanged output when perceptions are absent, visible face box, face keypoints, pose points, mesh toggle, state labels, and tracked-only distinct styling. Use pixel-difference assertions on small images and keep dimensions fixed.

Assert compatibility:

```python
legacy = renderer.render(image, predictions)
explicit = renderer.render(image, predictions, perceptions=())
self.assertEqual(legacy.tobytes(), explicit.tobytes())
```

- [ ] **Step 2: Run renderer tests and confirm failure**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_renderer tests.test_runtime_cli -v
```

Expected: missing options and render parameter.

- [ ] **Step 3: Implement optional overlays**

Keep gaze rendering order unchanged. Draw perception after heatmap but before labels:

1. Primary head box from perception.
2. Auxiliary face box.
3. Six detector keypoints.
4. Pose head/shoulder points.
5. Optional face-mesh points.
6. State/ID/confidence label.

Use reduced alpha and a dashed outline for `tracked_only`. Do not mutate `HeadPerception`. Do not recompute or replace the Gazelle bbox. Pass perceptions to renderer only on `ok` inference frames, matching the approved design behavior for skipped/no-head frames.

- [ ] **Step 4: Run renderer and pipeline tests**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest tests.test_renderer tests.test_image_pipeline tests.test_video_pipeline tests.test_runtime_cli -v
```

Expected: all pass.

- [ ] **Step 5: Commit, push, and comment**

```powershell
git add gazelle/runtime/renderer.py gazelle/runtime/config.py gazelle/runtime/cli.py gazelle/runtime/pipeline.py tests/test_renderer.py tests/test_runtime_cli.py tests/test_image_pipeline.py tests/test_video_pipeline.py
git commit -m "Render MediaPipe head observations"
git push origin feature/mediapipe-head-tracking
```

---

### Task 12: Validate Dependencies and Synchronize Environment and Documentation

**Files:**
- Modify: `environment.yml`
- Modify: `README.md`
- Modify: `README_CN.md`

**Interfaces:**
- Declares: `mediapipe==0.10.35` and `trackers==2.5.0.post0` after validation.
- Documents: preparation, image/video commands, outputs, state semantics, rendering, performance controls, and limitations.

- [ ] **Step 1: Confirm the existing environment without modification**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -c "import os,sys; print(os.environ.get('CONDA_DEFAULT_ENV')); print(sys.executable); print(sys.version)"
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -c "import torch,cv2,numpy,PIL; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(cv2.__version__); print(numpy.__version__); print(PIL.__version__)"
```

Expected baseline: Python 3.11, Torch 2.6.0+cu126, CUDA build 12.6, OpenCV 4.11.0, and NumPy 1.26.4. Record actual output if patch-level versions differ.

- [ ] **Step 2: Resolve dependencies without modifying Gazelle**

Use a temporary report outside the repository:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m pip install --dry-run --report "$env:TEMP\gazelle-mediapipe-pip-report.json" mediapipe==0.10.35 trackers==2.5.0.post0
```

Expected: resolution succeeds without proposing removal or downgrade of Torch, TorchVision, TorchAudio, CUDA packages, NumPy 1.26.4, Pillow 11.1.0, or OpenCV 4.11.0.86. If it proposes a conflicting replacement, stop this task and report the exact dependency conflict; do not install a different version silently.

- [ ] **Step 3: Request the one required environment-change approval**

Present the exact dry-run additions and replacements. Proceed only after explicit approval to install into the existing `Gazelle` Conda environment. This is the plan's required major-change confirmation gate.

- [ ] **Step 4: Install only the approved packages and run import smoke tests**

After approval:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m pip install mediapipe==0.10.35 trackers==2.5.0.post0
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -c "import mediapipe,trackers,supervision; print(mediapipe.__version__); print(trackers.__version__); print(supervision.__version__)"
```

Expected: all imports succeed. Record the resolved Supervision version and add it to environment documentation if the package exposes a stable version string.

- [ ] **Step 5: Update environment.yml and both README files**

Add these direct pins under the existing pip list:

```yaml
      - mediapipe==0.10.35
      - trackers==2.5.0.post0
```

README sections in both languages must include:

- Activate `Gazelle`; do not recreate or prune a working environment by default.
- `--head-source mediapipe` purpose.
- `--max-heads`, `--pose-model`, `--head-track-max-gap-ms`, and `--save-face-landmarks`.
- Perception rendering switches.
- `--prepare-only --head-source mediapipe --cache-dir models`.
- MediaPipe cache layout and normal network activity.
- `head_observations.json` and `head_observations.jsonl` schema summary.
- `face_pose`, `face_only`, `pose_only`, and `tracked_only` meanings.
- `frame_step` skips Gazelle but not perception.
- CPU MediaPipe behavior on the validated Windows runtime.
- Face visibility, back-or-occluded ambiguity, 500 ms stale-box behavior, multi-person validation status, and no webcam support.

- [ ] **Step 6: Run the complete offline suite**

Run:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-pycache"
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m compileall main.py gazelle tests
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -v
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --help
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --list-models
Remove-Item Env:PYTHONPYCACHEPREFIX
git diff --check
git status --short
```

Expected: compileall, all unit tests, help, model listing, and diff check pass; status contains only the three intended files before commit. Default tests report no real resource/model activity.

- [ ] **Step 7: Commit, push, and comment**

```powershell
git add environment.yml README.md README_CN.md
git commit -m "Document MediaPipe head tracking runtime"
git push origin feature/mediapipe-head-tracking
```

---

### Task 13: Run Real Resource, Image, Video, and Performance Validation

**Files:**
- No repository files unless validation exposes a bug or documentation mismatch.
- Never add temporary inputs, model assets, outputs, or benchmark reports from outside the repository.

**Interfaces:**
- Exercises: production resource registry, real MediaPipe tasks, real ByteTrack, real Gazelle predictor, JSON/JSONL outputs, rendering, and cleanup.
- Produces: an accurate PR #5 validation comment.

- [ ] **Step 1: Prepare real resources**

Run inside `Gazelle`:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --prepare-only --head-source mediapipe --pose-model full --model gazelle_dinov2_vitb14_inout --cache-dir models
```

Run it a second time to verify cache reuse. Record each downloaded or reused asset, checksum verification, Gazelle checkpoint activity, DINOv2 construction, and PyTorch Hub activity. The expected second run performs no MediaPipe asset download.

- [ ] **Step 2: Run a real single-image smoke test**

Use the local, non-repository image path supplied through
`GAZELLE_SMOKE_IMAGE`. Fail clearly if the variable is absent:

```powershell
if (-not $env:GAZELLE_SMOKE_IMAGE) { throw "GAZELLE_SMOKE_IMAGE must contain an absolute local image path" }
$smokeRoot = Join-Path $env:TEMP "gazelle-mediapipe-smoke"
New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --input $env:GAZELLE_SMOKE_IMAGE --output-dir (Join-Path $smokeRoot "image") --head-source mediapipe --pose-model full --max-heads 1 --save-rendered --face-box --face-keypoints --pose-head-points --model gazelle_dinov2_vitb14_inout --cache-dir models --overwrite
```

Expected: `predictions.json`, `head_observations.json`, `run_config.json`, and
rendered image exist. Validate one normalized head bbox, provider `mediapipe`, a
valid state, and Gazelle prediction when a head is available.

- [ ] **Step 3: Run a real short-video smoke test**

Use the local, non-repository workplace clip supplied through
`GAZELLE_SMOKE_VIDEO`. Fail clearly if the variable is absent:

```powershell
if (-not $env:GAZELLE_SMOKE_VIDEO) { throw "GAZELLE_SMOKE_VIDEO must contain an absolute local video path" }
$smokeRoot = Join-Path $env:TEMP "gazelle-mediapipe-smoke"
New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --input $env:GAZELLE_SMOKE_VIDEO --output-dir (Join-Path $smokeRoot "video") --head-source mediapipe --pose-model full --max-heads 1 --head-track-max-gap-ms 500 --max-frames 100 --save-rendered --face-box --pose-head-points --model gazelle_dinov2_vitb14_inout --cache-dir models --overwrite
```

Expected: one gaze row and one observation row per written frame, stable person ID through ordinary motion, explicit `tracked_only` rows only within 500 ms, no head after expiry, readable rendered MP4, and no audio preservation claim.

- [ ] **Step 4: Record performance and quality observations**

Report:

- Input resolution, source FPS, frames processed, and selected pose model.
- Mean and percentile timings for face detector, face landmarker, pose landmarker, fusion/tracking, Gazelle, rendering, and total frame time.
- Valid head-box frame rate.
- Number of person-ID changes.
- Number and maximum duration of tracked-only intervals.
- States observed across frontal, profile, mask/glasses/helmet, back-or-occluded, short gap, and long gap segments.
- Whether Pose Lite was benchmarked because Pose Full perception fell below the deployment target.

Do not label the pipeline real-time unless measured throughput supports that statement on the tested hardware.

- [ ] **Step 5: Run final repository validation and audit ignored artifacts**

Run the complete validation commands from Task 12, then:

```powershell
git status --short
git status --short --ignored
git log --oneline --decorate -15
gh pr view 5 --repo Hyakuri/gazelle --json title,baseRefName,headRefName,state,isDraft,mergeable,url
```

Confirm no model, output, cache, media, pycache, or temporary file is tracked. Ignored `models/` content is allowed locally but must not be staged.

- [ ] **Step 6: Add the final PR #5 validation comment**

The comment must contain:

- Goal.
- All implementation milestones and user-facing changes.
- Exact validation commands and pass/fail counts.
- `CONDA_DEFAULT_ENV`, Python executable/version, Torch version/CUDA build, CUDA availability, MediaPipe version, Trackers version, Supervision version, and OpenCV version.
- Exact real image/video commands with private paths normalized to the literal
  environment-variable names `GAZELLE_SMOKE_IMAGE` and `GAZELLE_SMOKE_VIDEO`.
- Download, cache reuse, DINOv2, PyTorch Hub, CUDA, and inference activity.
- Output checks and frame/row counts.
- Measured timing and quality summary.
- Known limitations and any untested scenario.
- Final commit SHA.

Keep PR #5 Draft until implementation, default tests, documentation, dependency validation, and at least one real MediaPipe smoke test are complete. Do not merge it.

---

## Final Acceptance Checklist

- [ ] All 13 tasks are complete in order.
- [ ] Each code milestone used a failing test before implementation.
- [ ] Each milestone was committed, pushed, and recorded in PR #5.
- [ ] Existing head providers remain compatible.
- [ ] `HeadObservation` remains unchanged.
- [ ] MediaPipe imports remain lazy.
- [ ] MediaPipe resources use pinned versioned URLs and verified SHA-256 values.
- [ ] Failed forced downloads preserve old assets.
- [ ] Image mode uses no tracker.
- [ ] Video mode updates perception and ByteTrack every decoded frame.
- [ ] `frame_step` gates Gazelle only.
- [ ] Short occlusion behavior is explicit, decaying, and bounded to 500 ms by default.
- [ ] `head_observations.json` and `.jsonl` are independent of gaze schemas.
- [ ] Full 478-point output is opt-in.
- [ ] Gazelle construction is lazy when no usable head exists.
- [ ] Rendering remains backward compatible.
- [ ] README.md and README_CN.md are synchronized.
- [ ] Default tests perform no network/model/CUDA activity.
- [ ] Real tests run only in the existing approved `Gazelle` environment.
- [ ] No generated or cached artifact is committed.
- [ ] PR #5 remains unmerged.
