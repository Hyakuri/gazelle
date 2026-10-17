# Project Usage Guide

For machine migration and cross-agent development, see the [Handoff Guide](HANDOFF.md) and [Shared Agent Workflow](AGENT_WORKFLOW.md).

## 1. Scope and current capabilities

Gazelle performs local gaze-target inference on one supported image or an offline video file. Head input can come from the single-person fallback, repeated static boxes, JSON/JSONL records, or MediaPipe face/pose perception. The runtime writes independent head observations, Gazelle predictions, configuration metadata, and optional visual output. It is not a webcam or real-time pipeline.

PowerShell examples run from the repository root. A command containing the literal `USER_INPUT_PATH` is a template, not a ready-to-run command: replace every `USER_INPUT_PATH` with an existing local file whose suffix is supported. Do not type the placeholder literally.

## 2. Environment installation and activation

`environment.yml` describes the current `Gazelle-next` environment: Python 3.14 (validated with 3.14.8), PyTorch 2.14.1 with CUDA 13.0 wheels, MediaPipe 1.1.1, and OpenCV 5.0. The explicit package versions are `torch==2.14.1+cu130`, `torchvision==0.29.1+cu130`, `timm==1.0.30`, `numpy==2.5.4`, `scipy==1.18.1`, `pandas==2.3.3`, `matplotlib==3.11.2`, `scikit-learn==1.9.1`, `pillow==12.3.0`, `opencv-python==5.0.0.93`, `opencv-contrib-python==5.0.0.93`, `mediapipe==1.1.1`, `trackers==2.6.1`, `supervision==0.30.9`, `av==19.0.1`. pandas stays on 2.3 because the data-preparation scripts have not been validated with pandas 3.0.

`environment_py311.yml` preserves the previous Python 3.11 definition byte for byte and still declares `name: Gazelle`. Keep that existing environment unchanged for rollback. `environment_1.0.yml` is the older NumPy 1.26.4 reference, also named `Gazelle`; use a separate name if creating it alongside another environment.

The explicit dependency list has changed as follows:

- `torchaudio` is omitted: repository code does not use it, and the evaluated stack has no matching torch 2.14 audio package.
- `xformers` is omitted: the evaluated Windows builds were incompatible with this torch version or lacked CUDA operators. DINOv2 uses PyTorch `scaled_dot_product_attention`.
- `ultralytics` is omitted: repository code does not import it, and YOLO inference/export were not validated.
- `polars`, `polars-runtime-32`, and `nvidia-ml-py` are omitted with the unused Ultralytics dependency group.
- `pydeprecate` and `defusedxml` are no longer explicitly pinned. They remain installed as required transitive dependencies of trackers/supervision: `pydeprecate==0.13.0` and `defusedxml==0.7.1`. They must not be uninstalled to match an omission in this file.

For an existing installation, activate it without reinstalling packages:

```powershell
conda activate Gazelle-next
```

On a new machine, after authorizing environment creation, run:

```powershell
conda env create -f environment.yml
conda activate Gazelle-next
pip install -e .
```

Creation downloads packages and writes a new `Gazelle-next` environment; editable installation also modifies it. Neither command runs inference. From the repository root, `python main.py` can use the checkout directly. Do not recreate or prune an existing environment.

For rollback, use `conda activate Gazelle` if it is retained locally. Only if it is absent and recreation is authorized, run `conda env create -f environment_py311.yml`. Keep `wandb` as a separately installed requirement for the upstream training scripts; this change does not validate training.

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
  --face-mesh `
  --face-pose-ray `
  --pose-head-ray `
  --reference-ray-length 2.5 `
  --gaze-inout-threshold 0.5 `
  --gazelle-head-mode eligible `
  --gaze-render-mode valid-only
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
  --video-codec mp4v `
  --head-box `
  --face-box `
  --face-keypoints `
  --pose-head-points `
  --face-mesh `
  --face-pose-ray `
  --pose-head-ray `
  --reference-ray-length 2.5 `
  --gaze-inout-threshold 0.5 `
  --gazelle-head-mode eligible `
  --gaze-render-mode valid-only
```

For exploratory comparison, replace `DIAGNOSTIC_VIDEO_PATH` below with an existing video. This command sends selected conservative and diagnostic MediaPipe states/views into Gazelle and renders both in-frame and out-of-frame predictions:

```powershell
python main.py --input DIAGNOSTIC_VIDEO_PATH `
  --output-dir outputs `
  --overwrite `
  --head-source mediapipe `
  --gazelle-head-mode face_pose face_only pose_only back_or_occluded tracked_only `
  --gaze-render-mode all-predictions `
  --face-pose-ray `
  --pose-head-ray `
  --save-rendered `
  --video-codec avc1
```

This is a diagnostic mode. `tracked_only` remains limited to an active short-occlusion bridge and cannot revive an expired track. Predictions from stale, occluded, pose-only, or otherwise non-eligible heads are exploratory model outputs, not validated physical eye-gaze measurements.

```text
MediaPipe Face Detector / Face Landmarker / Pose Landmarker
  -> fusion + independent face/pose 2D reference rays
  -> ByteTrack and 500 ms short-occlusion bridge for video
  -> post-bridge max-head arbitration
  -> normalized HeadObservation + conservative gaze eligibility
  -> configured Gazelle head selectors -> GazellePredictor
  -> gaze heatmap / peak / in-out score + final gaze_status
  -> head_observations.jsonl / predictions.jsonl / rendered.mp4
```

First use may download the Gazelle checkpoint, DINOv2 repository/weights, and MediaPipe task assets; valid cache entries are reused. Image IDs start at zero, while video IDs come from ByteTrack. The default `--gazelle-head-mode eligible` preserves the conservative boundary: perception confidence and face-ray confidence must both be at least `0.50`, and state/quality checks are repeated before inference. `--gazelle-head-mode` may instead accept one or more selectors with OR semantics: `eligible`, `observed`, `all`, states `face_pose`/`face_only`/`pose_only`/`tracked_only`, or views `frontal`/`profile`/`back_or_occluded`/`unknown`. Duplicate selectors are removed in order, and any `all` canonicalizes the selection to `all`. Non-MediaPipe providers retain their existing behavior. The Gazelle model still consumes only `"images"` tensors and `"bboxes"` lists; `person_id` is retained by the wrapper, while confidence, state, keypoints, pose, and both reference rays remain sidecar metadata rather than model input.

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
| `--gazelle-head-mode` | one or more of `eligible`, `observed`, `all`, `face_pose`, `face_only`, `pose_only`, `tracked_only`, `frontal`, `profile`, `back_or_occluded`, `unknown` | `eligible` | MediaPipe-to-Gazelle scheduling | OR-selects ordered perceptions for inference. `eligible` is the conservative policy; `observed` excludes bridged tracks; `all` includes every active perception. Geometry validation and track expiry still apply. |
| `--bbox` | four floats `XMIN YMIN XMAX YMAX`; repeatable | `None` | `static` provider | Required at least once for `static`; values use `--bbox-format`, are clipped/normalized, and must leave a nonempty box. |
| `--bbox-format` | `normalized` or `pixel` | `normalized` | `static` provider | Interprets CLI `--bbox`; JSON records use their own record/head `bbox_format`, not this option. |
| `--person-id` | integer; repeatable | `None` | `static` provider | If supplied, count must equal repeated `--bbox` count; otherwise IDs are `0, 1, ...`. |
| `--head-data` | readable path; `.jsonl` is line-delimited, every other suffix is one JSON document | `None` | `json` provider | Required for `json`; reads only the supplied file and does not itself use network/CUDA or write output. |
| `--save-heatmaps` | flag | `false` | image inference only | Writes per-person `heatmaps/person_<id>.pt`; video rejects this option before processing. |
| `--save-rendered` | flag | `false` | image/video inference | Writes an overlay image or silent `.mp4`; rendering controls have no file effect unless enabled. |
| `--rendered-name` | nonempty leaf filename with `.png`, `.jpg`, or `.jpeg` | `rendered.png` | rendered image | Names the file inside the per-image output directory; path components are rejected. |
| `--output-video-name` | nonempty leaf filename ending `.mp4` | `rendered.mp4` | rendered video | Names the silent video inside the per-video output directory; path components are rejected. |
| `--video-codec` | `mp4v` or `avc1` | `mp4v` | rendered video | `mp4v` writes directly with OpenCV; `avc1` requires FFmpeg on `PATH` and atomically finalizes H.264/AVC. It has no effect without `--save-rendered`. |
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
| `--face-pose-ray` | flag | `false` | MediaPipe rendering | Draws the blue uncalibrated 2D reference ray derived from current face keypoints and Face Landmarker head pose; an axial pose is shown as an origin marker. |
| `--pose-head-ray` | flag | `false` | MediaPipe rendering | Draws the orange independent 2D reference ray derived from current Pose Landmarker nose/eye or nose/ear geometry. |
| `--reference-ray-length` | finite float greater than `0` | `2.5` | MediaPipe perception/rendering | Sets both ray lengths as a multiple of the normalized head-box diagonal before image-boundary clipping. |
| `--gaze-inout-threshold` | finite float in `[0, 1]` | `0.5` | Gazelle output classification | Classifies lower in/out scores as `out_of_frame` while retaining prediction metadata. Rendering suppression is controlled separately by `--gaze-render-mode`. |
| `--gaze-render-mode` | `valid-only` or `all-predictions` | `valid-only` | Gazelle rendering | `valid-only` draws Gazelle geometry only for `gaze_status=valid`; `all-predictions` also draws actual `out_of_frame` heatmap/contour/arrow/peak without changing status or JSON. |
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

Perception runs on every written frame. `frame_step` gates only Gazelle: a nonselected frame is `skipped` even if it has no head; a selected frame without heads is `no_head`. `max_frames` limits both JSONL files and rendering. Raw video heatmap export is unsupported. Rendered output has no audio.

The default `--video-codec mp4v` keeps the existing direct OpenCV `VideoWriter` path and does not require FFmpeg. For browser-friendly H.264/AVC output, install FFmpeg so `ffmpeg` is available on `PATH`, then run:

```powershell
python main.py --input USER_INPUT_PATH --output-dir outputs --overwrite `
  --head-source mediapipe `
  --save-rendered `
  --video-codec avc1
```

The `avc1` path streams rendered frames into a temporary `mp4v` source, probes FFmpeg before video/provider/model construction, prefers `h264_nvenc`, and retries with `libx264` if NVENC is unavailable at runtime. It writes `yuv420p`, applies `-movflags +faststart`, disables audio with `-an`, and atomically replaces the formal output only after successful encoding. Temporary source/candidate files are cleaned on success or failure. Selecting `avc1` without `--save-rendered` performs no FFmpeg probe or transcode.

## 10. Rendering controls

Rendering writes only with `--save-rendered`. When MediaPipe perceptions are supplied, the **MediaPipe primary perception head box** renders for every person with a head box; it is solid for a current observation and dashed/translucent for `tracked_only`. The **track-state labels default on**, and `--no-track-state` disables the person/state/confidence labels without changing JSON/JSONL.

`--head-box` controls the separate **Gazelle prediction bbox**, which requires a non-null prediction bbox. `--face-box`, `--face-keypoints`, `--pose-head-points`, and `--face-mesh` are auxiliary MediaPipe opt-ins for the face box, up to six detector keypoints, pose head/shoulder points, and the current in-memory face mesh. `--face-pose-ray` draws the blue Face Landmarker reference and `--pose-head-ray` draws the orange, independently estimated Pose Landmarker reference. Each reference ray is an uncalibrated 2D head-direction diagnostic, not an eye-gaze measurement, and uses the final fused head bbox for its requested length. The face origin prefers the eye midpoint and falls back to the face-box center only when at least three finite current face keypoints remain. A near-camera-axis face direction is an origin ring because it has no honest image-plane line. Heatmap, gaze peak, gaze arrow, and general labels default on; their `--no-*` flags disable them. With default `--gaze-render-mode valid-only`, Gazelle heatmap, contour, arrow, and peak are drawn only for `gaze_status=valid`; an `out_of_frame` prediction can still retain its optional bbox and status label. `--gaze-render-mode all-predictions` also draws the actual geometry for `out_of_frame` predictions without changing their status, scores, or JSON. `--draw-heatmap-contour --heatmap-contour-quantile 0.90 --heatmap-contour-width 3` adds a contour. Skipped/no-head/no-gaze video frames are still written and can retain MediaPipe overlays.

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

For inference, argument-only static/json errors are rejected with usage exit code 2
before any `--overwrite` deletion. Static boxes must contain four finite real
values (not bool), be ordered/nonempty after normalized clipping, and have matching
integer IDs when provided. Pixel clipping still depends on image dimensions.
Validation preserves the original bbox values in `run_config.json`. JSON paths
must name an existing file, but their contents are checked later. JSON content,
MediaPipe resource, checkpoint, and device-availability failures may still occur
after deletion. `--list-models` and `--prepare-only` bypass these inference-only
provider prerequisites; head-source/bbox-format enum checks always apply.

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
| `gaze_eligible` | Required | boolean | Conservative recommendation from the perception policy; current face state and perception/face-ray confidence values of at least `0.50` are required. Diagnostic selectors do not mutate it. |
| `gazelle_selected` | Required | boolean | Actual per-frame decision made by `--gazelle-head-mode`. It is always `false` on `frame_step`-skipped video frames. |
| `gaze_status` | Conditional | enum string | Pre-inference rejection reason: `unavailable_occluded`, `tracked_no_gaze`, or `rejected_low_quality`. |
| `tracking` | Required | object | Contains Required boolean `provisional`, Required integer `track_age_frames`, Required integer `missed_frames`, and Required finite-number `missed_ms`. |
| `face_bbox_normalized` | Conditional | number `[4]` | Current face bbox in `(xmin, ymin, xmax, ymax)` order, clipped to `[0, 1]`. |
| `face_keypoints` | Conditional | landmark array | Face-detector keypoints when present. |
| `pose_head_landmarks` | Conditional | landmark array | Pose-derived head/shoulder landmarks when present. |
| `pose_head_keypoints` | Conditional | named landmark object | Reliable named `nose`, eye, ear, mouth, and shoulder points retained independently of filtered landmark order. |
| `facial_transformation_matrix` | Conditional | nested finite-number arrays | The serializer preserves supplied row lengths. The MediaPipe adapter requires at least three rows and at least three values in each of the first three rows; it does not enforce rectangularity. |
| `head_pose` | Conditional | object | Finite degree values `yaw_deg`, `pitch_deg`, and `roll_deg`; positive yaw right, positive pitch down, positive roll clockwise in the displayed image. |
| `face_pose_reference_ray` | Conditional | reference-ray object | Face-keypoint/Face Landmarker ray with `source`, normalized origin/direction/endpoint, confidence, and projection status. |
| `pose_head_reference_ray` | Conditional | reference-ray object | Independent Pose Landmarker keypoint ray using the same object shape. |
| `face_landmarks` | Conditional | landmark array | Full face mesh only when available and `--save-face-landmarks` is set. |

Landmark, matrix, and head-pose value shapes:

| Value | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| landmark `x`, `y` | Required | finite number | Provider-normalized image coordinates; not clipped/range-validated, so do not assume `[0, 1]`. |
| landmark `z` | Conditional | finite number | Relative depth with no guaranteed range. |
| landmark `visibility`, `presence` | Conditional | finite number | Provider values emitted when present; no range is enforced. |
| `facial_transformation_matrix` rows | Conditional | nested finite-number arrays | MediaPipe commonly supplies `4 x 4`, but the serializer preserves supplied row lengths; rows after the first three may have any supplied length. |
| `head_pose.yaw_deg`, `pitch_deg`, `roll_deg` | Required inside Conditional `head_pose` | finite number | Display-oriented angles in degrees: `yaw_right`, `pitch_down`, `roll_clockwise`. |

Video frame 0 and the first frame of each new track now emit the observed head immediately,
with `tracking.provisional=true` and age 1. Confirmation within two frame indices links by IoU
to the same `person_id`; age counts from the original spawn. Provisional observations do not
create or refresh bridge state, so a one-frame detection cannot create a stale ghost.
Image mode, confirmed observations and `tracked_only` always use `tracking.provisional=false`.

The face reference ray projects the matrix forward vector as `(r02, -r12)` into image
coordinates (x right, y down). Positive yaw points right, positive pitch down, and positive
roll rotates clockwise. Serialized roll and the face ray's vertical direction follow these
signs; consumers of earlier opposite signs must update. Both rays remain uncalibrated 2D
head-pose references, not eye-gaze measurements or calibrated 3D rays.

`track_age_frames` is the track age, while `missed_frames` and `missed_ms` count consecutive bridge reuse since the last current observation. `tracked_only` therefore represents a stale bridged box, not a fresh detection. It is excluded by the default `eligible` selector, but explicit `tracked_only` or `all` diagnostic selection may send it to Gazelle only while that bridge track is active. In single-person mode, post-bridge arbitration keeps at most one identity and prunes displaced stale bridge state.

### Prediction records

Every prediction person has:

| Field | Presence | Type/shape | Meaning |
| --- | --- | --- | --- |
| `person_id` | Required | integer | Wrapper association back to the ordered input observation. |
| `bbox_normalized` | Required, Nullable | number `[4]` or `null` | `(xmin, ymin, xmax, ymax)` in `[0, 1]`, or the no-box fallback. |
| `gaze_peak_normalized` | Required, Nullable | number `[2]` or `null` | Gaze peak `[x, y]`, normalized to `[0, 1]` when present. |
| `heatmap_peak_value` | Required, Nullable | finite number or `null` | Peak value from the predicted heatmap. |
| `inout_score` | Required, Nullable | finite number or `null` | Present for every model; non-in/out models emit `null`. |
| `gaze_status` | Required | enum string | `valid` or `out_of_frame` after applying `--gaze-inout-threshold`; a null in/out score remains `valid`. |
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
| `status` | Required | enum string | `ok`, `no_head`, `no_gaze`, `skipped`, or schema-supported `error`; `no_gaze` means heads exist but none match the configured Gazelle selectors, and `skipped` takes precedence when `frame_step` excludes a frame. |
| `width`, `height` | Required | positive integer | Frame pixel dimensions. |
| `people` | Required | array | Empty unless `status` is `ok`. |
| `inference_ms` | Conditional | finite number | Emitted when Gazelle inference ran. |
| `error` | Conditional | string | Supported by the serializer; the current pipeline raises instead of writing an error row. |

### Run configuration

`run_config.json` begins with `dataclasses.asdict()` over the validated `RuntimeConfig`, so Python tuples become JSON arrays. The base object always has all 47 keys below, including keys whose value is `null`.

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
| `draw_face_pose_ray` | boolean (non-null) | Effective positive face reference-ray state from `--face-pose-ray`. |
| `draw_pose_head_ray` | boolean (non-null) | Effective positive pose reference-ray state from `--pose-head-ray`. |
| `reference_ray_length` | number (non-null) | Positive finite head-box diagonal multiplier from `--reference-ray-length`. |
| `gaze_inout_threshold` | number (non-null) | Finite Gazelle in/out classification threshold from `--gaze-inout-threshold`, in `[0, 1]`. |
| `gazelle_head_mode` | string array (non-null) | Validated, de-duplicated selector sequence from `--gazelle-head-mode`; defaults to `["eligible"]`, and any `all` input canonicalizes to `["all"]`. |
| `gaze_render_mode` | string (non-null) | Validated rendering mode from `--gaze-render-mode`: `valid-only` or `all-predictions`. |
| `heatmap_contour_quantile` | number (non-null) | Finite contour threshold quantile from `--heatmap-contour-quantile`, in `[0, 1]`. |
| `heatmap_contour_width` | integer or null (nullable) | Positive contour width from `--heatmap-contour-width`, or null for automatic width. |
| `output_fps` | number or null (nullable) | Positive finite fallback from `--output-fps`, or null when not supplied; video overrides this key with the resolved writer/tracker FPS. |
| `max_frames` | integer or null (nullable) | Positive frame limit from `--max-frames`, or null for no explicit limit. |
| `frame_step` | integer (non-null) | Positive Gazelle inference stride from `--frame-step`. |
| `output_video_name` | string (non-null) | Validated rendered-video leaf `.mp4` filename from `--output-video-name`. |
| `video_codec` | string (non-null) | Validated rendered-video codec from `--video-codec`: `mp4v` or `avc1`. |
| `device` | string (non-null) | Validated device request from `--device`: `auto`, `cpu`, `cuda`, or indexed CUDA. |
| `cache_dir` | string or null (nullable) | Explicit cache root from `--cache-dir`, or null to use environment/default precedence. |
| `checkpoint` | string or null (nullable) | Local Gazelle checkpoint path from `--checkpoint`, or null for the registered resource. |
| `force_download` | boolean (non-null) | Whether `--force-download` requests eligible registered-resource refresh. |

Most CLI names become config names by replacing hyphens with underscores. The explicit CLI-to-config renames are `--input` -> `input_path`, `--bbox` -> `bboxes`, and `--person-id` -> `person_ids`. The positive `draw_*` booleans store effective behavior, not the spelling of a negative flag: `--no-heatmap` -> `draw_heatmap`, `--head-box` -> `draw_head_box`, `--no-gaze-peak` -> `draw_gaze_peak`, `--no-gaze-arrow` -> `draw_gaze_arrow`, `--draw-heatmap-contour` -> `draw_heatmap_contour`, `--no-labels` -> `draw_labels`, `--face-box` -> `draw_face_box`, `--face-keypoints` -> `draw_face_keypoints`, `--pose-head-points` -> `draw_pose_head_points`, `--face-mesh` -> `draw_face_mesh`, `--no-track-state` -> `draw_track_state`, `--face-pose-ray` -> `draw_face_pose_ray`, and `--pose-head-ray` -> `draw_pose_head_ray`. A `--no-*` mapping is inverted, so the config value is `true` when drawing remains enabled.

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
| video | `container_frame_count` | integer or null (nullable) | Positive container estimate; null when unknown. |
| video | `frames_required` | integer or null (nullable) | Minimum required decoded count; null when unknown. |
| video | `decode_complete` | boolean or null (nullable) | Whether the required count was met; null when not checked. |
| video | `timestamp_sources` | object (non-null) | Integer counts for `container`, `repaired`, and `fps_fallback`. |

There are 49 unique image keys and 56 unique video keys. For container count N,
T = max(2, ceil(0.005 * N)). `--max-frames` at or before N - T requires exactly
the requested count; otherwise `frames_required` is max(0, N - T). Unknown
counts disable the check. Truncation exits nonzero after preserving partial
JSONL and `run_config.json` with `decode_complete: false`. With rendering enabled,
`avc1` skips H.264 finalization and leaves only these files; `mp4v` also leaves an
incomplete `rendered.mp4`.

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

The current `Gazelle-next` environment does not install xFormers; DINOv2 uses PyTorch `scaled_dot_product_attention`. The runtime retains its compatibility policy for environments that do install xFormers: CPU construction and `--prepare-only` disable it; CUDA may request it unless `XFORMERS_DISABLED` is set. When optional Triton is absent and no override is set, `XFORMERS_FORCE_DISABLE_TRITON=1` skips that probe without disabling other xFormers operators or modifying the environment. Nonfatal xFormers-disabled/not-available messages may still appear during strict loading. DINOv2 caches its backend selection, so switching incompatible CPU/prepare-only and xFormers-enabled CUDA modes in a long-lived process requires a fresh process.

## 14. Common errors and operational limitations

Unsupported suffixes, missing input/head-data/checkpoint files, malformed/duplicate JSON records, invalid boxes/devices, and provider prerequisites fail clearly. Static ID count must equal bbox count. Normalized/pixel boxes must be finite and remain nonempty after normalization/clipping. Output conflicts require another root or `--overwrite`; cache/network failures stop preparation or inference.

The reader preserves finite nonnegative container timestamps that strictly increase after rounding. Repeated, backward, or sub-millisecond collisions receive the smallest integer-millisecond repair. Missing timestamps are nonfinite, negative, or zero from frame index 2 onward. They use `max(prev_out + 1000 / fps, p + 1)`: the larger of the previous unrounded output plus one nominal frame interval and the previous rounded output plus 1 ms. An invalid first timestamp becomes zero; a zero at index 1 becomes 1 ms instead of a frame-index estimate. An unrepresentable finite increasing time fails explicitly. These repairs do not synchronize cameras.

**known runtime limitation:** If source FPS is invalid, the reader's timestamp fallback remains 30 FPS even when `--output-fps` controls a different writer/tracker FPS; the two clocks can diverge and affect bridge timing.

For AVI empty packets, run this lossless remux from the repository root, replacing paths:

```powershell
ffmpeg -n -fflags +genpts -i "C:\path\to\read-only-source\input.avi" -map 0:v:0 -c:v copy -bsf:v "noise=drop=lt(size\,64)" "C:\path\outside-repository\remuxed.mp4"
```

This runs local FFmpeg and writes a new video-only MP4 without audio, retaining the original input. `-n` protects existing output. No inference, CUDA, network access, or downloads occur.

Perception quality depends on visible-face evidence. The `pose_only` path uses approximate pose-only geometry, and a stale bridge box can lag rapid motion for as long as `--head-track-max-gap-ms`. Detection/pose quality degrades with extreme profile views, occlusion, PPE such as masks/glasses/helmets, motion blur, and low resolution. Although `--max-heads` supports up to 10, the current system has limited real multi-person validation.

There is no webcam/real-time mode, automatic ROI/process logic, Multi-Pose integration, audio remuxing, raw video heatmap export, or high-performance asynchronous inference. MediaPipe/tracking runs locally after assets are cached, and rendered video has no audio.

## 15. Research data tools

Run from the repository root in the existing Gazelle-next environment. Keep the source
read-only and choose a data root outside both the repository and source root.
These tools use CPU/disk only: no models, CUDA, network access, or downloads.
Use low process priority for long runs. See the [Chinese guide](../tools/workdata/README_CN.md).
Remux validation requires 30 decoded frames at the start and middle, then a tail
window ending at EOF (30 or more consecutive frames, at most 120 reads). The last
decoded timestamp must be within one `r_frame_rate` interval of the last packet PTS.
The report includes `last_pts`, actual decoded counts and `tail_eof`.

| Entry module | Reads | Writes | External tools |
| --- | --- | --- | --- |
| `tools.workdata.inventory` | Source AVI/MP4; prior inventory hash cache | Atomic inventory JSON, camera roles and packet statistics | ffprobe |
| `tools.workdata.remux` | Inventory and source AVI | Video-only MP4 and `remux_report.json` | ffprobe, FFmpeg, OpenCV decode checks |
| `tools.workdata.osd_clock` | One complete local video-frame image | Recognized clock or null on stdout | CPU/OpenCV; no FFmpeg executable |
| `tools.workdata.timemap` | Inventory, original MP4 and validated remuxes | Anchor caches and per-session time maps | CPU/PyAV (FFmpeg libraries), no FFmpeg executable |
| `tools.workdata.sync_check` | Time maps and mapped videos | Motion-energy caches and correlation reports | CPU/PyAV; no FFmpeg executable |
| `tools.workdata.sync_calibrate` | v2 base maps and source videos | 96×54 gray samples, provenance, calibrated maps | CPU/PyAV; no models, network or FFmpeg executable |
| `tools.workdata.sync_validate` | Calibrated proxies and saved clock sample indices | Residual reports, clock checks, event strips | CPU/OpenCV/Pillow; no models, network or FFmpeg executable |
| `tools.workdata.proxies` | Valid time maps and mapped videos | Three H.264 proxies/session, frame sidecars, full source decode counts and `session.json` | CPU/PyAV, FFmpeg/libx264, ffprobe |
| `tools.validation.extract_roi_candidates` | Inventory, validated overview remuxes | 12 JPEGs/session and `roi/candidates.json` | CPU OpenCV/Pillow; no FFmpeg executable |
| `tools.validation.roi_server` | Candidates and optional saved regions | Atomic region/draft files, backups; reference/class export on request | Local browser at 127.0.0.1 only |
| `tools.validation.roi_regions` | Region definitions | Validation or derived classes JSON | CPU only |
| `tools.validation.sample_segments` | Proxy sessions/sidecars, proxy hashes, optional completed regions | Seeded segment manifest, classes and optional ROI reference | CPU; no video decode or FFmpeg executable |
| `tools.validation.extract_frames` | Manifest and exact proxy videos | Hashed 1920×720 three-view JPEGs, or dataset validation | CPU/OpenCV; no FFmpeg executable |
| `tools.validation.annotate_server` | Extracted dataset and optional existing labels | Atomic labels and previous-version backup after edits | Browser at 127.0.0.1 only |
| `tools.validation.labels validate` | Dataset and labels JSON | Strict coverage/schema validation | CPU; no media decode or FFmpeg executable |
| `tools.validation.render_roi_reference` | Regions and candidate images | Reference PNG, session overlays, classes JSON | Pillow and an existing CJK font |

```powershell
$raw = 'E:\Gazelle_Workdata\秋田大学様解析用動画'
$data = 'C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata'
python -m tools.workdata.inventory --root $raw --out "$data\inventory\inventory.json"
python -m tools.workdata.remux --inventory "$data\inventory\inventory.json" --out-root "$data\remux"
```

Use `--ffprobe` on either entry and `--ffmpeg` on remux to override PATH lookup.
Valid existing remuxes are skipped unless `--force` is supplied; failed refreshes
preserve existing files. Outputs are published only after packet count, duration,
PTS and head/middle/tail decode checks pass. Derived data must never enter Git.

Region tools do not call models, GPU, an FFmpeg executable, or external network
services. The editor uses only loopback HTTP and inline page resources. See the
[region guide](../tools/validation/ROI_GUIDE_CN.md); run from the repository root:

```powershell
python -m tools.validation.extract_roi_candidates --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\roi"
python -m tools.validation.roi_server --candidates "$data\roi\candidates.json" --annotator local
python -m tools.validation.roi_regions validate "$data\roi\roi_regions.json"
python -m tools.validation.render_roi_reference --regions-path "$data\roi\roi_regions.json" --candidates "$data\roi\candidates.json" --out-root "$data\roi"
```

Use `--regions-path "$data\roi\review_trial.json"` for a trial: it has separate
backups/drafts and exports to `review_trial_export`. Simply loading the page does
not create formal regions. Choose a reference, draw polygons, check every session,
then export references/classes. Invalid or self-intersecting polygons cannot be
saved; keep the original candidate manifest when resuming. Stop the server with Ctrl+C.
Exported classes retain target colors and use configured colors for fixed labels.
Draw targets first and the work cell last. In an overlap, clicking selects the
smallest region; its vertex handles stay above every polygon. A double-click
closes the polygon without adding a duplicate vertex. Custom targets get distinct
colors. Export requires 1–6 targets and exactly one cell, with no unfinished draft.
Digit keys follow target drawing order, then `cell_other`, `away`, `absent` (at
most 1–9); `unknown` is 0. Deleting and redrawing a target changes that order.
Autosave alone does not complete annotation: successful export writes
`roi_regions.complete.json` (version 2, `completed_at`, `regions_sha256`, `export_root`,
and `exports` hashes for `roi_reference.png` and `classes.json`). Later
edits invalidate completion until re-export. Downstream tools use
`roi_regions.completed_document()` to check the marker and all file hashes.
The page shows completion status and asks for confirmation of regions below 0.5%
of image area. CLI rendering accepts `--confirm-small` and optional `--out-root`;
without `--out-root`, `roi_regions.json` exports beside itself and other filenames
export to `<stem>_export/`. The completion marker always stays beside the region JSON.

Clock commands, from the repository root using the same external `$data`:

```powershell
python -m tools.workdata.osd_clock --image C:\path\outside-repository\clock.png
python -m tools.workdata.timemap --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\timemaps_v2_base"
python -m tools.workdata.sync_calibrate --timemaps "$data\timemaps_v2_base" --out-root "$data\timemaps_v2" --samples-root "$data\sync_samples_v2" --session 20260828
python -m tools.workdata.sync_check --timemaps "$data\timemaps_v2" --out-root "$data\sync_checks" --session 20260828
```

These commands use no GPU, model, network or downloads. Video commands set below-normal
priority and stream native PTS through PyAV. v2 base maps fit one robust line per file,
splitting only at actual decoded PTS discontinuities, not OSD jumps; coverage begins
at the first decoded frame. All anchor residuals remain in the report; validity requires
median absolute residual ≤0.5 s and ≥90% within ±1.5 s. Unreadable clocks stay missing.

Synchronization r2 uses front camera B as the reference. A/E use 5 Hz, 96×54 gray
motion, six cells selected across all lags, 60 s windows and ±10 s correlation search.
Valid windows require r ≥0.5, prominence ≥0.1 and a peak away from the boundary.
Theil–Sen fits need ≥10 windows spanning ≥30% of the session and MAD ≤0.08 s;
supported steps are refined with 20 s windows. Final time solves `t = base_X(pts) - L(t)`.
It is B's displayed-clock axis, not calibrated UTC. Calibration needs visible worker
motion; empty or stationary periods cannot calibrate themselves. Uncalibratable cameras
remain explicit failures and cannot generate v2 proxies. The optional legacy `sync_check`
keeps three 120 s, 10 Hz diagnostic windows, reports boundary/non-prominent peaks separately,
and requires a valid peak with |lag| ≤0.5 s. It is not the r2 residual acceptance gate.
Caches bind mapping and sampling implementation hashes. See the [Chinese guide](../tools/workdata/README_CN.md).
`timemap --sample-cache <previous-v2-root>` refits previously decoded/OCR evidence into a
different `--out-root`. Source/media signatures, camera identity and sampling settings must match;
the old sample hash and implementation fingerprint are retained. It performs no video decoding
or OCR and never labels older samples as newly measured. Equal consecutive PTS are not regressions.

Proxy generation, using the same external `$data`:

```powershell
python -m tools.workdata.proxies --timemaps "$data\timemaps_v2" --out-root "$data\proxies" --session 20260828 --allow-internal-gaps
python -m tools.workdata.sync_validate --proxies "$data\proxies" --out-root "$data\sync_validation" --session 20260828 --clock-samples C:\path\outside-repository\check_proxy_clocks.json
```

Defaults are `--step-hz 5 --size 1920 1080`, CRF 20, yuv420p, constant frame rate,
and no audio. The command uses below-normal CPU priority, real FFmpeg/ffprobe,
and no model, GPU, network or downloads. It streams all source frames to EOF,
records container versus decoded counts (differences above 0.5% need review),
and validates temporary videos before publication. Valid matching outputs resume;
`--force` rebuilds them. Existing outputs that fail validation or have a different
fingerprint are preserved and require explicit `--force` to replace. Sidecars record the nearest source frame, native PTS,
time difference and a gap flag when the difference exceeds half a grid step.

Multiple common-coverage intervals are rejected by default. The explicit
`--allow-internal-gaps` option retains one continuous clock grid
across the entire range and records every coverage gap and nearest-frame gap flag;
it does not compress time. Preserve old proxies and trial datasets as dated backups before
regeneration. `sync_validate` reuses the saved fixed k indices, tries k−1/k+1/k−2/k+2
only for missing clock reads, and records unevaluable samples (≥90% must be evaluable).
Clock tolerances are A/B ±1 s and E ±2 s. Residual checks cover A–B, E–B and A–E:
≥90% of valid windows within ±0.2 s, median |lag| ≤0.1 s, midpoint |offset| ≤0.1 s,
and |drift| ≤0.1 s/hour. All failures remain in reports; no window is removed to pass.
Three ±1 s event strips per session support independent visual review. Regenerate trial
and completed-ROI datasets only after calibrated proxies exist; formal annotation waits
for independent synchronization acceptance. See the
[Chinese tool guide](../tools/workdata/README_CN.md).

Three-view annotation, from the repository root in Gazelle-next:

```powershell
$dataset = 'C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial'
python -m tools.validation.sample_segments --proxies-root "$data\proxies" --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset --validate-only
python -m tools.validation.annotate_server --dataset-root $dataset --labels-path "$dataset\review_trial.json" --annotator reviewer
# After annotation and stopping the local server:
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json"
# Strict pilot check; other segments receive structural checks:
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json" --segment 20260911_pilot
```

These tools use no model, GPU, downloads, external network or FFmpeg executable.
Extraction streams CPU OpenCV frames at below-normal priority. Defaults use seed
20261015, four strata per session (two below 45 minutes), 60-second segments and
5 Hz steps. Segments with more than two seconds of gap steps are redrawn up to
ten times; pilot overlaps also trigger a recorded redraw. The fixed pilot is listed
first and excluded from evaluation. Each session uses `seed + int(session)`;
`--sessions` defaults to 20260821 20260828 20260903 20260911 20260925 20261002 20261009.
Other sessions are ignored with a message; the manifest records selected sessions.
Every proxy and extracted frame is bound by SHA-256.

Explicit `--regions-path` requires completed regions and valid export hashes;
otherwise sampling fails. Classes and reference bytes come only from the marker's
export directory, with hashes checked before copying. Omit `--regions-path` to use
the `roi_r2_trial` dataset with default classes;
when regions are ready, create a fresh `roi_r2` dataset for formal annotation.
Existing datasets are refused unless `--overwrite` is explicit; this preserves
the entire previous directory under a timestamped backup name. Formal labels
default to `labels.json`; use `--labels-path` for reviews. Displaying a loaded image
records a viewed step and creates/saves labels. Changes autosave atomically with a
rolling `.bak` and reject stale or externally changed labels. Resume chooses the
first unfinished segment, then its first unseen step, first null step, or step 0.

The editor provides playback, step controls, number-key change points, deletion,
undo, a colour timeline and other-person intervals. It waits for the current
image before accepting a judgment. Version 2 labels record merged, monotonically
growing `viewed_ranges`. Unseen steps keep a stripe texture even when labelled.
Only **本段完成** explicitly writes `finished_at`, after all steps have been viewed
and labelled; changing a label or other-person range clears it. Version 1 labels
are rejected with instructions to reannotate. Strict validation requires all three
conditions; repeat `--segment ID` to restrict strict checks to selected segments.
Unlabelled draft steps are distinct from intentional `unknown`; `--allow-incomplete` only validates drafts and does not
certify completion. See the [Chinese annotation guide](../tools/validation/ANNOTATION_GUIDE_CN.md).
All videos, frames and labels remain outside Git and must not be uploaded.

## 16. Validation commands

These checks are offline and do not construct a model. Default tests mock FFmpeg capability probes/transcodes and do not run a real FFmpeg process:

```powershell
conda activate Gazelle-next
python main.py --help
python main.py --list-models
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-docs-pycache"
python -m unittest tests.test_usage_docs -v
Remove-Item Env:PYTHONPYCACHEPREFIX
```
