# Video Output Codec Selection Design

## Goal

Add a user-selectable video output codec while preserving the current
OpenCV `mp4v` path as the default and providing an FFmpeg-backed H.264/AVC
path for browser-compatible rendered videos.

## Scope

This milestone adds:

- `--video-codec {mp4v,avc1}`;
- strict runtime configuration validation;
- FFmpeg executable and encoder capability detection;
- automatic `h264_nvenc` preference with `libx264` fallback;
- safe temporary-file handling and atomic publication;
- offline mocked-subprocess tests;
- pipeline regression tests;
- synchronized English and Chinese documentation.

This milestone does not add audio remuxing, webcam input, asynchronous frame
processing, model changes, or environment mutation.

## Compatibility

`mp4v` remains the default. It continues to write the configured final
`.mp4` path directly through the existing OpenCV `VideoFrameWriter`.

Selecting `avc1` has an effect only when `--save-rendered` is active. A codec
selection without rendered video output does not require FFmpeg.

Image rendering and all non-video runtime behavior remain unchanged.

## Configuration and CLI

`RuntimeConfig` gains:

```python
video_codec: str = "mp4v"
```

The validator accepts only `mp4v` and `avc1`. The CLI exposes:

```text
--video-codec {mp4v,avc1}
```

The default is `mp4v`.

## Component Boundaries

The existing `gazelle.runtime.media.VideoFrameWriter` remains an OpenCV
`mp4v` writer and does not execute subprocesses.

A new focused module, `gazelle.runtime.ffmpeg`, owns:

- locating the FFmpeg executable;
- parsing available encoders;
- choosing the preferred encoder order;
- constructing FFmpeg commands;
- running H.264 transcodes;
- validating the candidate output;
- atomically replacing the final output;
- cleaning temporary files.

The video pipeline decides whether the OpenCV writer targets the final path
or an intermediate path. It explicitly finalizes `avc1` only after all
rendered frames and run metadata have been written successfully.

## FFmpeg Capability Detection

For `avc1` rendered output, capability detection runs before video input,
provider, predictor, or model construction.

Detection:

1. resolves `ffmpeg` with `shutil.which`;
2. runs `ffmpeg -hide_banner -encoders`;
3. accepts `h264_nvenc`, `libx264`, or both;
4. raises a clear `RuntimeError` when FFmpeg is missing, the probe fails, or
   neither supported H.264 encoder is available.

The error identifies that `--video-codec avc1` requires FFmpeg on `PATH`.

## Streaming and Finalization Flow

For `mp4v`:

```text
rendered PIL frames
  -> OpenCV VideoFrameWriter
  -> final rendered.mp4
```

For `avc1`:

```text
rendered PIL frames
  -> OpenCV VideoFrameWriter using mp4v
  -> hidden source temporary .mp4
  -> close OpenCV writer
  -> FFmpeg H.264 candidate in the same output directory
  -> verify candidate exists
  -> os.replace(candidate, final rendered.mp4)
  -> remove source/candidate temporary files
```

Both temporary files live beside the final output so atomic replacement does
not cross filesystems. Unique hidden names prevent collisions.

## Encoder Selection and Fallback

The preferred order is:

1. `h264_nvenc`, when advertised by FFmpeg;
2. `libx264`, when advertised by FFmpeg.

An advertised NVENC encoder can still fail at runtime because compatible
hardware, drivers, or an available encoding session are missing. If the
NVENC transcode fails and `libx264` is available, the runtime deletes any
partial candidate and retries once with `libx264`.

It does not fallback after a successful process whose candidate file is
missing; that condition is treated as a broken FFmpeg execution contract.

If every attempted encoder fails, the raised error contains each encoder,
return code, and captured stderr so the original cause remains visible.

## FFmpeg Output Contract

Each transcode command includes:

```text
-an
-c:v <encoder>
-pix_fmt yuv420p
-movflags +faststart
```

`-an` makes the existing silent-output policy explicit. The source video audio
is not copied or remuxed.

The subprocess uses an argument list without shell parsing. Standard output
and error are captured as text. Tests inject or mock the subprocess runner.

## Failure and Cleanup Behavior

- FFmpeg absence fails before provider, predictor, DINOv2, or MediaPipe model
  construction.
- Frame-processing failures close the OpenCV writer and delete intermediate
  files without starting FFmpeg.
- Transcode failure leaves no formal rendered output and removes both
  temporary paths.
- Atomic replacement happens only after a successful command and an existing
  candidate file.
- Cleanup failures do not replace the primary processing/transcode error; they
  are attached as contextual notes through the pipeline's existing cleanup
  strategy where applicable.
- The per-input output directory and completed JSON/JSONL metadata may remain
  after a finalization error, matching existing pipeline failure behavior.

## Testing

Default tests never invoke real FFmpeg, Gazelle, DINOv2, MediaPipe task
models, network access, CUDA, or external video assets.

Coverage includes:

- CLI default and explicit codec parsing;
- invalid codec rejection;
- missing FFmpeg;
- failed encoder probe;
- NVENC-only, libx264-only, and preferred-order detection;
- required H.264 command flags;
- NVENC success;
- NVENC runtime failure followed by libx264 success;
- all-encoder failure diagnostics;
- missing candidate detection;
- atomic replacement and temporary-file cleanup;
- unchanged `mp4v` pipeline behavior;
- `avc1` temporary writer routing and finalization;
- early FFmpeg failure before provider/predictor construction;
- processing/finalization cleanup paths.

## Documentation

`README.md`, `README_CN.md`, `docs/USAGE.md`, and `docs/USAGE_CN.md` explain:

- the default-compatible `mp4v` behavior;
- how to select `avc1`;
- the FFmpeg-on-`PATH` requirement;
- NVENC preference and libx264 fallback;
- `yuv420p` and fast-start output;
- the unchanged no-audio policy;
- representative PowerShell commands.
