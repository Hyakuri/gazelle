# Project Usage Guide

## 1. Scope and current capabilities

Gazelle performs local gaze-target inference on one supported image or an offline video file. Head input can come from the single-person fallback, repeated static boxes, JSON/JSONL records, or MediaPipe face/pose perception. The runtime writes independent head observations, Gazelle predictions, configuration metadata, and optional visual output. It is not a webcam or real-time pipeline.

PowerShell examples run from the repository root. A command containing the literal `USER_INPUT_PATH` is a template, not a ready-to-run command: replace every `USER_INPUT_PATH` with an existing local file whose suffix is supported. Do not type the placeholder literally.

## 2. Environment installation and activation

`environment.yml` is the validated environment definition:

```powershell
conda env create -f environment.yml
conda activate Gazelle
pip install -e .
```

For an existing environment, run only `conda activate Gazelle` and `pip install -e .`.

## 3. Quick start and resource preparation

```powershell
python main.py --help
python main.py --list-models
python main.py --prepare-only --model gazelle_dinov2_vitb14_inout --cache-dir models
python main.py --prepare-only --head-source mediapipe --pose-model full --cache-dir models
```

`--help` and `--list-models` do not construct models, download resources, use CUDA, or write output. `--prepare-only` does not process media or write predictions, but it constructs DINOv2 for strict checkpoint loading and may download the Gazelle checkpoint and DINOv2 repository/weights. The MediaPipe form also prepares the face detector, face landmarker, and selected pose landmarker.

## 4. End-to-end MediaPipe head perception and gaze inference

This image command is repository-root-runnable because `assets\the_office.png` is tracked. It may download model/task resources on first use and writes `outputs\the_office_gazelle`:

```powershell
python main.py --input assets\the_office.png `
  --output-dir outputs `
  --overwrite `
  --head-source mediapipe `
  --max-heads 1 `
  --pose-model full `
  --model gazelle_dinov2_vitb14_inout `
  --device auto `
  --cache-dir models `
  --save-rendered `
  --head-box `
  --face-box `
  --face-keypoints `
  --pose-head-points `
  --face-mesh
```

The video workflow below is intentionally a template because the repository has no committed video. Replace `USER_INPUT_PATH` with an existing supported video path before execution; only the input path must be supplied. Keep every other argument unchanged to retain MediaPipe, ByteTrack, the 500 ms bridge, Gazelle, cache selection, and rendering:

```powershell
python main.py --input USER_INPUT_PATH `
  --output-dir outputs `
  --overwrite `
  --head-source mediapipe `
  --max-heads 1 `
  --pose-model full `
  --head-track-max-gap-ms 500 `
  --model gazelle_dinov2_vitb14_inout `
  --device cuda `
  --cache-dir models `
  --save-rendered `
  --head-box `
  --face-box `
  --face-keypoints `
  --pose-head-points `
  --face-mesh
```

```text
MediaPipe Face Detector / Face Landmarker / Pose Landmarker
  -> fusion
  -> ByteTrack and 500 ms short-occlusion bridge for video
  -> normalized HeadObservation
  -> GazellePredictor
  -> gaze heatmap / peak / in-out score
  -> head_observations.jsonl / predictions.jsonl / rendered.mp4
```

First use may download the Gazelle checkpoint, DINOv2 repository/weights, and MediaPipe task assets; valid cache entries are reused. Image IDs start at zero, while video IDs come from ByteTrack. `GazellePredictor` accepts ordered `HeadObservation` values, but the Gazelle model consumes only `"images"` tensors and `"bboxes"` lists. `person_id` is retained by the wrapper to associate model results with output people. `confidence` remains in observation sidecars and is not model input.

## 5. Supported models and media formats

| Model | Backbone | In/out score |
| --- | --- | --- |
| `gazelle_dinov2_vitb14` | `dinov2_vitb14` | no; serialized as `inout_score: null` |
| `gazelle_dinov2_vitl14` | `dinov2_vitl14` | no; serialized as `inout_score: null` |
| `gazelle_dinov2_vitb14_inout` | `dinov2_vitb14` | yes |
| `gazelle_dinov2_vitl14_inout` | `dinov2_vitl14` | yes |

Supported images: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`. Supported videos: `.mp4`, `.avi`, `.mov`, `.mkv`, `.m4v`. Rendered images must be a leaf filename ending in `.png`, `.jpg`, or `.jpeg`; rendered video must be a leaf `.mp4` filename.

## 6. Complete CLI option reference

| Option | Accepted/validation | Default | Scope | Behavior/activity |
| --- | --- | --- | --- | --- |
| `--help` | flag | `false` | CLI inspection | Prints help and exits; no download, CUDA, inference, or writes. |
| `--list-models` | flag | `false` | CLI inspection | Lists the four registered models and exits; no model construction, download, CUDA, or writes. |
| `--prepare-only` | flag | `false` | resource preparation | Prepares/strict-loads Gazelle and DINOv2; with MediaPipe source also prepares task assets. May use network, but does not place the model on `--device`, run CUDA inference, or write media outputs. |
| `--model` | one of the four registered model names | `gazelle_dinov2_vitb14_inout` | preparation and inference | Selects model/checkpoint metadata; preparation or first usable inference may download/construct resources. |
| `--input` | existing supported image/video path when inference runs | `None` | inference | Required unless `--list-models` or `--prepare-only`; read only, while pipeline outputs go under `--output-dir`. |
| `--output-dir` | path | `outputs` | image/video inference | Output root; creates `<input-stem>_gazelle` and writes JSON/JSONL plus requested media. |
| `--overwrite` | flag | `false` | image/video inference | Reuses a same-stem output by recursively deleting its existing per-input `_gazelle` directory; containment/suffix guards apply, but deletion occurs before provider/model/resource setup and same-stem inputs can collide. |
| `--head-source` | `none`, `static`, `json`, or `mediapipe` | `none` | image/video inference | Selects provider; `static` requires `--bbox`, `json` requires `--head-data`, and `mediapipe` may download task assets. |
| `--max-heads` | integer from `1` through `10` | `1` | MediaPipe image/video | Limits fused MediaPipe heads; does not limit `static` or `json` heads. |
| `--pose-model` | `lite`, `full`, or `heavy` | `full` | MediaPipe image/video/preparation | Selects pose landmarker and therefore which pose task asset may be downloaded. |
| `--head-track-max-gap-ms` | finite float greater than `0` | `500.0` | MediaPipe video | Configures short-occlusion bridge; tracking is not used for images. |
| `--save-face-landmarks` | flag | `false` | MediaPipe observation output | Adds `face_landmarks` when available, increasing size/privacy exposure; `--face-mesh` can render in-memory landmarks without it. |
| `--bbox` | four floats `XMIN YMIN XMAX YMAX`; repeatable | `None` | `static` provider | Required at least once for `static`; values use `--bbox-format`, are clipped/normalized, and must leave a nonempty box. |
| `--bbox-format` | `normalized` or `pixel` | `normalized` | `static` provider | Interprets CLI `--bbox`; JSON records use their own record/head `bbox_format`, not this option. |
| `--person-id` | integer; repeatable | `None` | `static` provider | If supplied, count must equal repeated `--bbox` count; otherwise IDs are `0, 1, ...`. |
| `--head-data` | readable path; `.jsonl` is line-delimited, every other suffix is one JSON document | `None` | `json` provider | Required for `json`; reads only the supplied file and does not itself use network/CUDA or write output. |
| `--save-heatmaps` | flag | `false` | image inference only | Writes per-person `heatmaps/person_<id>.pt`; video rejects this option before processing. |
| `--save-rendered` | flag | `false` | image/video inference | Writes an overlay image or silent `.mp4`; rendering controls have no file effect unless enabled. |
| `--rendered-name` | nonempty leaf filename with `.png`, `.jpg`, or `.jpeg` | `rendered.png` | rendered image | Names the file inside the per-image output directory; path components are rejected. |
| `--output-video-name` | nonempty leaf filename ending `.mp4` | `rendered.mp4` | rendered video | Names the silent video inside the per-video output directory; path components are rejected. |
| `--output-fps` | finite float greater than `0` | `None` | video | Used only if source FPS is invalid; otherwise source FPS wins. The resolved FPS also feeds video tracking. |
| `--max-frames` | integer greater than or equal to `1` | `None` | video | Limits decoded/written frames, both JSONL files, and optional rendered video. |
| `--frame-step` | integer greater than or equal to `1` | `1` | video | Perception still runs every written frame; Gazelle runs when `frame_index % frame_step == 0`; otherwise prediction status is `skipped`. |
| `--heatmap-alpha` | finite float in `[0, 1]` | `0.45` | rendering | Sets heatmap opacity when `--save-rendered` is active and heatmap drawing is enabled. |
| `--no-heatmap` | flag | `false` | rendering | Disables heatmap overlay; does not suppress prediction or raw image heatmap saving. |
| `--head-box` | flag | `false` | prediction rendering | Draws the separate Gazelle prediction bbox when non-null; it does not control the MediaPipe primary perception head box. |
| `--face-box` | flag | `false` | MediaPipe rendering | Draws auxiliary MediaPipe face boxes when present; no effect on Gazelle input. |
| `--face-keypoints` | flag | `false` | MediaPipe rendering | Draws up to six detector keypoints; no effect on serialized Gazelle predictions. |
| `--pose-head-points` | flag | `false` | MediaPipe rendering | Draws pose head/shoulder points when available. |
| `--face-mesh` | flag | `false` | MediaPipe rendering | Draws current in-memory face landmarks; independent of `--save-face-landmarks`. |
| `--no-track-state` | flag | `false` | MediaPipe rendering | Track-state labels default on; this flag hides person/state/confidence labels while observation sidecars retain tracking state. |
| `--no-gaze-peak` | flag | `false` | rendering | Hides the gaze peak marker only; predictions remain unchanged. |
| `--no-gaze-arrow` | flag | `false` | rendering | Hides head-center-to-peak arrow; an arrow also requires a non-null bbox. |
| `--draw-heatmap-contour` | flag | `false` | rendering | Enables high-response contour using the quantile/width options. |
| `--heatmap-contour-quantile` | finite float in `[0, 1]` | `0.9` | contour rendering | Sets contour threshold; relevant when contour drawing is enabled. |
| `--heatmap-contour-width` | integer greater than or equal to `1`, or omitted | `None` | contour rendering | Overrides automatic contour width when contour drawing is enabled. |
| `--no-labels` | flag | `false` | rendering | Hides general person labels; does not remove IDs from JSON/JSONL. |
| `--device` | `auto`, `cpu`, `cuda`, or `cuda:<non-negative-index>` | `auto` | model construction/inference | Selects PyTorch device; explicit/auto CUDA can use GPU, while inspection-only actions do not construct a model. |
| `--cache-dir` | path | `None` | resources | Highest-priority cache root; then `GAZELLE_CACHE_DIR`, then `models`. Preparation/inference may write cache files here. |
| `--checkpoint` | existing local file path | `None` | Gazelle resources | Bypasses registered Gazelle checkpoint download; DINOv2 and selected MediaPipe assets may still require network/cache writes. |
| `--force-download` | flag | `false` | registered Gazelle and selected MediaPipe resources | Redownloads registered Gazelle checkpoint through temporary replacement without digest verification; MediaPipe assets are staged and SHA-256 verified. Ignored for Gazelle when `--checkpoint` is supplied. |

## 7. Head input providers: `none`, `static`, `json`, and `mediapipe`

`none` supplies one `HeadObservation(person_id=0, bbox=None, confidence=None)` for Gazelle's single-person no-box fallback. `static` uses repeated CLI boxes:

```powershell
python main.py --input assets\the_office.png --output-dir outputs --overwrite `
  --head-source static `
  --bbox 0.10 0.12 0.22 0.30 `
  --bbox 0.45 0.10 0.58 0.31 `
  --bbox-format normalized `
  --person-id 10 `
  --person-id 11
```

`json` loads records described in section 11. `mediapipe` prepares official task assets, fuses face/pose evidence, returns deterministic image IDs, and adds ByteTrack plus the short-occlusion bridge for video.

## 8. Image workflows

Runnable fallback inference:

```powershell
python main.py --input assets\the_office.png --output-dir outputs --overwrite `
  --head-source none `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models
```

Runnable raw-heatmap and image-rendering workflow:

```powershell
python main.py --input assets\the_office.png --output-dir outputs --overwrite `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --save-heatmaps `
  --save-rendered `
  --rendered-name rendered.jpg `
  --head-box
```

Image output is `head_observations.json`, `predictions.json`, `run_config.json`, optional `heatmaps/person_<id>.pt`, and an optional rendered image. No Gazelle model is constructed if a provider returns no heads.

## 9. Offline video workflows

Every video command is a template because the repository tracks no supported video fixture. Replace `USER_INPUT_PATH` with an existing `.mp4`, `.avi`, `.mov`, `.mkv`, or `.m4v` file.

Frame stepping/limit template:

```powershell
python main.py --input USER_INPUT_PATH --output-dir outputs --overwrite `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --max-frames 100 `
  --frame-step 2 `
  --save-rendered `
  --head-box
```

Perception runs on every written frame. `frame_step` gates only Gazelle: a nonselected frame is `skipped` even if it has no head; a selected frame without heads is `no_head`. `max_frames` limits both JSONL files and rendering. Raw video heatmap export is unsupported. Rendered `mp4v` video does not preserve source audio.

## 10. Rendering controls

Rendering writes only with `--save-rendered`. When MediaPipe perceptions are supplied, the **MediaPipe primary perception head box** renders for every person with a head box; it is solid for a current observation and dashed/translucent for `tracked_only`. The **track-state labels default on**, and `--no-track-state` disables the person/state/confidence labels without changing JSON/JSONL.

`--head-box` controls the separate **Gazelle prediction bbox**, which requires a non-null prediction bbox. `--face-box`, `--face-keypoints`, `--pose-head-points`, and `--face-mesh` are auxiliary MediaPipe opt-ins for the face box, up to six detector keypoints, pose head/shoulder points, and the current in-memory face mesh. Heatmap, gaze peak, gaze arrow, and general labels default on; their `--no-*` flags disable them. `--draw-heatmap-contour --heatmap-contour-quantile 0.90 --heatmap-contour-width 3` adds a contour. Skipped/no-head video frames are still written.

## 11. JSON/JSONL input examples

Only a `.jsonl` suffix selects line-delimited parsing. Any other suffix is parsed as one JSON document. A single JSON object may omit `frame_index`, which then defaults to `0`:

```json
{
  "bbox_format": "normalized",
  "heads": [
    {"person_id": 7, "bbox": [0.10, 0.12, 0.22, 0.30], "confidence": 0.98}
  ]
}
```

`bbox` is required but may be `null` for Gazelle's single-head no-box fallback, for example `{"heads":[{"bbox":null}]}`. Multi-head inference requires every bbox to be non-null. Each head may override the record format, for example `{"bbox_format":"pixel","bbox":[100,80,220,230]}`. `person_id` defaults to the head's list index; `confidence` is optional and finite.

JSONL has one object per nonblank line:

```json
{"frame_index":0,"timestamp_ms":0,"bbox_format":"pixel","heads":[{"person_id":7,"bbox":[100,80,220,230]}]}
{"frame_index":1,"heads":[]}
```

A JSON list is also valid for video. Every JSON-list/JSONL record requires a nonnegative integer `frame_index`; indexes must be unique or loading fails. Each record requires a `heads` list, accepts optional finite `timestamp_ms`, and defaults `bbox_format` to `normalized`. A missing frame record yields no heads.

## 12. Output directories and record schemas

`assets\the_office.png` writes under `outputs\the_office_gazelle`. Without `--overwrite`, an existing per-input directory is an error. With it, cleanup has containment and `_gazelle` suffix guards but recursively deletes the existing directory before provider/model/resource setup. This is destructive, not an unconditional safety guarantee; inputs from different locations with the same-stem name share that directory and can collide.

The tables below use **Required** for an always-emitted key, **Conditional** for a key emitted only in the stated case, and **Nullable** for a Required key whose value may be JSON `null`.

### Observation frame records

An image writes one object to `head_observations.json`. A video writes one equivalent object per written frame to `head_observations.jsonl`.

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `frame_index` | Required | integer, `>= 0` | Zero-based decoded frame index; image is `0`. |
| `timestamp_ms` | Required | finite number | Media timestamp in milliseconds; image is `0.0`. |
| `status` | Required | enum string | `ok` when `people` is nonempty, otherwise `no_head`. |
| `width`, `height` | Required | positive integer | Source frame pixel dimensions. |
| `provider` | Required | string | Selected provider: `none`, `static`, `json`, or `mediapipe`. |
| `timings_ms` | Required | object of string to finite number | Provider timing values in milliseconds; may be empty. |
| `people` | Required | array | Basic observation people or rich MediaPipe perception people. |

Basic people from `none`, `static`, and `json` have this contract:

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `person_id` | Required | integer | Stable input identity for that record. |
| `head_bbox_normalized` | Required, Nullable | number `[4]` or `null` | `(xmin, ymin, xmax, ymax)`, clipped to `[0, 1]`; `null` is the single-person no-box fallback. |
| `confidence` | Required, Nullable | finite number or `null` | Provider-side observation confidence; it is not model input. |

MediaPipe rich people retain those fields and add:

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `state` | Required | enum string | `face_pose`, `face_only`, `pose_only`, or `tracked_only`. |
| `view_state` | Required | enum string | `frontal`, `profile`, `back_or_occluded`, or `unknown`. |
| `observed` | Required | boolean | `true` for current-frame evidence; `false` for a bridged track. |
| `tracking` | Required | object | Contains Required integer `track_age_frames`, Required integer `missed_frames`, and Required finite-number `missed_ms`. |
| `face_bbox_normalized` | Conditional | number `[4]` | Current face bbox in `(xmin, ymin, xmax, ymax)` order, clipped to `[0, 1]`. |
| `face_keypoints` | Conditional | landmark array | Face-detector keypoints when present. |
| `pose_head_landmarks` | Conditional | landmark array | Pose-derived head/shoulder landmarks when present. |
| `facial_transformation_matrix` | Conditional | nested finite-number arrays | The serializer preserves supplied row lengths. The MediaPipe adapter requires at least three rows and at least three values in each of the first three rows; it does not enforce rectangularity. |
| `head_pose` | Conditional | object | Finite degree values `yaw_deg`, `pitch_deg`, and `roll_deg`. |
| `face_landmarks` | Conditional | landmark array | Full face mesh only when available and `--save-face-landmarks` is set. |

Landmark, matrix, and head-pose value shapes:

| Value | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| landmark `x`, `y` | Required | finite number | Provider-normalized image coordinates; not clipped/range-validated, so do not assume `[0, 1]`. |
| landmark `z` | Conditional | finite number | Relative depth with no guaranteed range. |
| landmark `visibility`, `presence` | Conditional | finite number | Provider values emitted when present; no range is enforced. |
| `facial_transformation_matrix` rows | Conditional | nested finite-number arrays | MediaPipe commonly supplies `4 x 4`, but the serializer preserves supplied row lengths; rows after the first three may have any supplied length. |
| `head_pose.yaw_deg`, `pitch_deg`, `roll_deg` | Required inside Conditional `head_pose` | finite number | Euler-like head-pose angles in degrees. |

`track_age_frames` is the track age, while `missed_frames` and `missed_ms` count consecutive bridge reuse since the last current observation. `tracked_only` therefore represents a stale bridged box, not a fresh detection.

### Prediction records

Every prediction person has:

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `person_id` | Required | integer | Wrapper association back to the ordered input observation. |
| `bbox_normalized` | Required, Nullable | number `[4]` or `null` | `(xmin, ymin, xmax, ymax)` in `[0, 1]`, or the no-box fallback. |
| `gaze_peak_normalized` | Required, Nullable | number `[2]` or `null` | Gaze peak `[x, y]`, normalized to `[0, 1]` when present. |
| `heatmap_peak_value` | Required, Nullable | finite number or `null` | Peak value from the predicted heatmap. |
| `inout_score` | Required, Nullable | finite number or `null` | Present for every model; non-in/out models emit `null`. |
| `heatmap_path` | Conditional | string | Image only, and only when `--save-heatmaps` writes that person's tensor. |

Image `predictions.json` is one object:

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `input` | Required | string | Source image path. |
| `width`, `height` | Required | positive integer | Source image pixel dimensions. |
| `model` | Required | string | Selected registered Gazelle model name. |
| `people` | Required | prediction-person array | Empty when the provider returned no heads. |

Video `predictions.jsonl` has one record per written frame:

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `frame_index`, `timestamp_ms` | Required | integer; finite number | Matches the written observation frame. |
| `status` | Required | enum string | `ok`, `no_head`, `skipped`, or schema-supported `error`; `skipped` takes precedence when `frame_step` excludes a frame. |
| `width`, `height` | Required | positive integer | Frame pixel dimensions. |
| `people` | Required | array | Empty unless `status` is `ok`. |
| `inference_ms` | Conditional | finite number | Emitted when Gazelle inference ran. |
| `error` | Conditional | string | Supported by the serializer; the current pipeline raises instead of writing an error row. |

### Run configuration

`run_config.json` begins with `dataclasses.asdict()` over the validated `RuntimeConfig`, so Python tuples become JSON arrays. The base object always has all 40 keys below, including keys whose value is `null`.

#### Base RuntimeConfig fields

| Field | JSON type/shape and nullability | Meaning/source |
| --- | --- | --- |
| `model` | string (non-null) | Registered Gazelle model selected by `--model`. |
| `list_models` | boolean (non-null) | Action flag from `--list-models`; because only inference writes `run_config.json`, an emitted file records `false`. |
| `prepare_only` | boolean (non-null) | Action flag from `--prepare-only`; because only inference writes `run_config.json`, an emitted file records `false`. |
| `input_path` | string or null (nullable) | Base config value from `--input`; it is nullable before action validation, then image/video output overrides it with a non-null path. |
| `output_dir` | string (non-null) | Output root from `--output-dir`. |
| `overwrite` | boolean (non-null) | Whether `--overwrite` permits guarded recursive replacement of the per-input directory. |
| `head_source` | string (non-null) | Provider name from `--head-source`: `none`, `static`, `json`, or `mediapipe`. |
| `max_heads` | integer (non-null) | Validated MediaPipe limit from `--max-heads`, from `1` through `10`. |
| `pose_model` | string (non-null) | MediaPipe pose asset choice from `--pose-model`: `lite`, `full`, or `heavy`. |
| `head_track_max_gap_ms` | number (non-null) | Positive finite bridge gap in milliseconds from `--head-track-max-gap-ms`. |
| `save_face_landmarks` | boolean (non-null) | Whether `--save-face-landmarks` enables full face-landmark sidecar fields. |
| `bboxes` | array of number `[4]` arrays (non-null; may be empty) | Repeated `--bbox` values in the coordinate system named by `bbox_format`. |
| `bbox_format` | string (non-null) | CLI static-box format from `--bbox-format`: `normalized` or `pixel`. |
| `person_ids` | array of integers or null (nullable) | Repeated `--person-id` values, or null when IDs are generated. |
| `head_data` | string or null (nullable) | JSON/JSONL provider path from `--head-data`. |
| `save_heatmaps` | boolean (non-null) | Whether `--save-heatmaps` requests raw image heatmap tensor writes. |
| `save_rendered` | boolean (non-null) | Whether `--save-rendered` requests rendered image/video output. |
| `rendered_name` | string (non-null) | Validated rendered-image leaf filename from `--rendered-name`. |
| `heatmap_alpha` | number (non-null) | Finite heatmap opacity from `--heatmap-alpha`, in `[0, 1]`. |
| `draw_heatmap` | boolean (non-null) | Effective positive heatmap-overlay state; false only with `--no-heatmap`. |
| `draw_head_box` | boolean (non-null) | Effective positive Gazelle prediction-bbox state from `--head-box`. |
| `draw_gaze_peak` | boolean (non-null) | Effective positive gaze-peak state; false only with `--no-gaze-peak`. |
| `draw_gaze_arrow` | boolean (non-null) | Effective positive gaze-arrow state; false only with `--no-gaze-arrow`. |
| `draw_heatmap_contour` | boolean (non-null) | Effective positive contour state from `--draw-heatmap-contour`. |
| `draw_labels` | boolean (non-null) | Effective positive general-label state; false only with `--no-labels`. |
| `draw_face_box` | boolean (non-null) | Effective positive auxiliary face-box state from `--face-box`. |
| `draw_face_keypoints` | boolean (non-null) | Effective positive detector-keypoint state from `--face-keypoints`. |
| `draw_pose_head_points` | boolean (non-null) | Effective positive pose-point state from `--pose-head-points`. |
| `draw_face_mesh` | boolean (non-null) | Effective positive face-mesh state from `--face-mesh`. |
| `draw_track_state` | boolean (non-null) | Effective positive track-label state; false only with `--no-track-state`. |
| `heatmap_contour_quantile` | number (non-null) | Finite contour threshold quantile from `--heatmap-contour-quantile`, in `[0, 1]`. |
| `heatmap_contour_width` | integer or null (nullable) | Positive contour width from `--heatmap-contour-width`, or null for automatic width. |
| `output_fps` | number or null (nullable) | Positive finite fallback from `--output-fps`, or null when not supplied; video overrides this key with the resolved writer/tracker FPS. |
| `max_frames` | integer or null (nullable) | Positive frame limit from `--max-frames`, or null for no explicit limit. |
| `frame_step` | integer (non-null) | Positive Gazelle inference stride from `--frame-step`. |
| `output_video_name` | string (non-null) | Validated rendered-video leaf `.mp4` filename from `--output-video-name`. |
| `device` | string (non-null) | Validated device request from `--device`: `auto`, `cpu`, `cuda`, or indexed CUDA. |
| `cache_dir` | string or null (nullable) | Explicit cache root from `--cache-dir`, or null to use environment/default precedence. |
| `checkpoint` | string or null (nullable) | Local Gazelle checkpoint path from `--checkpoint`, or null for the registered resource. |
| `force_download` | boolean (non-null) | Whether `--force-download` requests eligible registered-resource refresh. |

Most CLI names become config names by replacing hyphens with underscores. The explicit CLI-to-config renames are `--input` -> `input_path`, `--bbox` -> `bboxes`, and `--person-id` -> `person_ids`. The positive `draw_*` booleans store effective behavior, not the spelling of a negative flag: `--no-heatmap` -> `draw_heatmap`, `--head-box` -> `draw_head_box`, `--no-gaze-peak` -> `draw_gaze_peak`, `--no-gaze-arrow` -> `draw_gaze_arrow`, `--draw-heatmap-contour` -> `draw_heatmap_contour`, `--no-labels` -> `draw_labels`, `--face-box` -> `draw_face_box`, `--face-keypoints` -> `draw_face_keypoints`, `--pose-head-points` -> `draw_pose_head_points`, `--face-mesh` -> `draw_face_mesh`, and `--no-track-state` -> `draw_track_state`. A `--no-*` mapping is inverted, so the config value is `true` when drawing remains enabled.

#### Image/video additions and overrides

| Run | Key | JSON type/shape and nullability | Meaning/source |
| --- | --- | --- | --- |
| image | `input_path` | string (non-null) | Overrides the nullable base value with the stringified source image path. |
| image | `image_width` | integer (non-null) | Added source image width in pixels. |
| image | `image_height` | integer (non-null) | Added source image height in pixels. |
| video | `input_path` | string (non-null) | Overrides the nullable base value with the stringified source video path. |
| video | `width` | integer (non-null) | Added decoded video width in pixels. |
| video | `height` | integer (non-null) | Added decoded video height in pixels. |
| video | `source_fps` | number (non-null) | Added raw OpenCV source FPS; it may be invalid for FPS use. |
| video | `output_fps` | number (non-null) | Overrides the nullable base value with the resolved positive finite writer/tracker FPS. |
| video | `frames_read` | integer (non-null) | Added nonnegative count of decoded frames read. |
| video | `frames_written` | integer (non-null) | Added nonnegative count of observation/prediction records and output frames written. |

## 13. Cache, downloads, device selection, and xFormers notes

Cache priority is `--cache-dir`, `GAZELLE_CACHE_DIR`, then `models`:

```text
models/
  checkpoints/
  mediapipe/
  torch_hub/
```

Missing entries may trigger network access for a registered Gazelle checkpoint, the DINOv2 repository/weights, and selected MediaPipe assets. Gazelle checkpoint downloads use a temporary directory before replacement but have no pinned digest check; `--prepare-only` subsequently validates checkpoint structure/keys/shapes by strict loading. MediaPipe cached/downloaded assets are checked against pinned SHA-256 values and staged before atomic replacement. `--checkpoint` bypasses only the registered Gazelle download.

Supply-chain boundary: the first uncached DINOv2 construction calls `torch.hub.load` on unpinned `facebookresearch/dinov2` repository code. It may fetch and execute remote Python, not just weights. Use a trusted network/environment and, for controlled deployments, a pre-reviewed cache. The runtime does not claim an immutable repository pin or Gazelle checkpoint weight-integrity verification.

CPU construction temporarily disables xFormers. CUDA construction requests xFormers only when the resolved device is CUDA and `XFORMERS_DISABLED` is absent; availability still depends on the installed DINOv2/xFormers environment. When optional Triton is absent and the user has not set an override, the runtime temporarily sets `XFORMERS_FORCE_DISABLE_TRITON=1` without disabling other xFormers operators. `--prepare-only` forces xFormers off for strict loading, so nonfatal disabled/not-available messages may appear. A long-lived process cannot switch between incompatible already-initialized DINOv2 xFormers states; start a fresh process.

## 14. Common errors and operational limitations

Unsupported suffixes, missing input/head-data/checkpoint files, malformed/duplicate JSON records, invalid boxes/devices, and provider prerequisites fail clearly. Static ID count must equal bbox count. Normalized/pixel boxes must be finite and remain nonempty after normalization/clipping. Output conflicts require another root or `--overwrite`; cache/network failures stop preparation or inference.

**known runtime limitation:** OpenCV video timestamps are rounded to integer milliseconds for MediaPipe and must strictly increase after rounding. Repeated timestamps or a sub-millisecond collision may abort the run. If source FPS is invalid, the reader's timestamp fallback remains 30 FPS even when `--output-fps` controls a different writer/tracker FPS; the two clocks can diverge and affect bridge timing. This describes current behavior, not desired behavior.

Perception quality depends on visible-face evidence. The `pose_only` path uses approximate pose-only geometry, and a stale bridge box can lag rapid motion for as long as `--head-track-max-gap-ms`. Detection/pose quality degrades with extreme profile views, occlusion, PPE such as masks/glasses/helmets, motion blur, and low resolution. Although `--max-heads` supports up to 10, the current system has limited real multi-person validation.

There is no webcam/real-time mode, automatic ROI/process logic, Multi-Pose integration, audio remuxing, raw video heatmap export, or high-performance asynchronous inference. MediaPipe/tracking runs locally after assets are cached, and rendered video has no audio.

## 15. Validation commands

These checks are offline and do not construct a model:

```powershell
conda activate Gazelle
python main.py --help
python main.py --list-models
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-docs-pycache"
python -m unittest tests.test_usage_docs -v
Remove-Item Env:PYTHONPYCACHEPREFIX
```
