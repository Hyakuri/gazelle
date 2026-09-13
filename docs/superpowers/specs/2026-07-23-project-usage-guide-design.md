# Project Usage Guide Design

## Goal

Create a complete, code-backed user guide for the current Gazelle fork in both
English and Chinese. The guides must explain environment setup, every public CLI
option, supported workflows, structured inputs and outputs, resource/network
activity, and one directly executable MediaPipe head-perception-to-Gazelle gaze
inference command.

## Deliverables

- `docs/USAGE.md`: complete English usage guide.
- `docs/USAGE_CN.md`: structurally equivalent Chinese usage guide.
- `README.md`: add a prominent link to the English guide.
- `README_CN.md`: add a prominent link to the Chinese guide.
- `tests/test_usage_docs.py`: prevent undocumented long CLI options and verify
  that both guides retain the required end-to-end MediaPipe workflow.

The runtime implementation, CLI behavior, dependencies, output schemas, and
model registry remain unchanged.

## Source Of Truth

The guides are derived from the current implementation, primarily:

- `gazelle/runtime/cli.py`
- `gazelle/runtime/config.py`
- `gazelle/runtime/model_registry.py`
- `gazelle/runtime/heads.py`
- `gazelle/runtime/media.py`
- `gazelle/runtime/outputs.py`
- `gazelle/runtime/pipeline.py`
- `gazelle/runtime/resources.py`
- `gazelle/runtime/perception/`
- `environment.yml`

Existing README text can provide context, but code behavior governs whenever
wording and implementation differ.

## Guide Structure

Both guides use the same section order:

1. Scope and current capabilities.
2. Environment installation and activation.
3. Quick start and resource preparation.
4. End-to-end MediaPipe head perception and gaze inference.
5. Supported models and media formats.
6. Complete CLI option reference grouped by responsibility.
7. Head input providers: `none`, `static`, `json`, and `mediapipe`.
8. Image workflows.
9. Offline video workflows.
10. Rendering controls.
11. JSON/JSONL input examples.
12. Output directories and record schemas.
13. Cache, downloads, device selection, and xFormers notes.
14. Common errors and operational limitations.
15. Validation commands.

Examples use PowerShell syntax because the validated development environment is
Windows. Commands remain runnable from the repository root.

## End-To-End Workflow

The primary command uses:

```text
MediaPipe Face Detector / Face Landmarker / Pose Landmarker
  -> head and pose fusion
  -> ByteTrack person IDs and short-occlusion bridge for video
  -> normalized HeadObservation values
  -> GazellePredictor
  -> gaze heatmap, gaze peak, optional in/out score
  -> JSONL sidecars and optional rendered.mp4
```

The documented command uses `--head-source mediapipe`, `--pose-model full`,
`--head-track-max-gap-ms 500`, an in/out Gazelle model, the shared `models`
cache, CUDA device selection, and rendered video output. The guide must state
that first use may download Gazelle, DINOv2, and MediaPipe assets; later runs
reuse valid cache entries.

## CLI Coverage

Every long option exposed by `build_parser()` must appear in both guides.
Descriptions include:

- accepted values and validation constraints;
- default value;
- applicable action, media type, or head source;
- interactions with related options;
- whether the option can download resources, use CUDA, or write outputs.

`tests/test_usage_docs.py` obtains long option names from the parser instead of
duplicating an option list. It asserts that every option is documented in both
guides and that the direct MediaPipe workflow contains the essential routing,
model, cache, and rendering options.

## Input And Output Accuracy

The guides distinguish:

- single-image JSON from video JSONL or JSON list head records;
- normalized and pixel bboxes;
- image `predictions.json` from video `predictions.jsonl`;
- independent head observation sidecars from Gazelle prediction output;
- `ok`, `no_head`, and `skipped` video statuses;
- optional image heatmap tensor files from unsupported video heatmap export;
- rendered video without source audio.

Face landmarks are omitted by default. `--save-face-landmarks` is documented as
an opt-in output and privacy/size trade-off, while face-mesh rendering can still
use current in-memory MediaPipe landmarks.

## Error Handling And Limitations

The guides explain early output-directory conflicts, safe `--overwrite`
cleanup, unsupported suffixes, invalid provider-specific argument combinations,
missing files, cache/network failures, CPU/CUDA device behavior, and the
non-fatal xFormers-disabled warnings expected during `--prepare-only`.

They also state that the current video path is offline, not webcam/real-time,
does not preserve audio, does not provide automatic ROI/process logic, and does
not integrate Multi-Pose.

## Validation

The documentation milestone is complete when:

- both guides contain all parser options;
- the English and Chinese section structures match;
- the end-to-end MediaPipe command parses against the current CLI;
- README links resolve to the new files;
- unit tests, CLI smoke checks, and `git diff --check` pass;
- no real model download, DINOv2 construction, CUDA inference, or environment
  modification is required for validation.
