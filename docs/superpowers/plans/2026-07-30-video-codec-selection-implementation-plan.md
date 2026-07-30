# Video Output Codec Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backward-compatible `mp4v`/`avc1` rendered-video selection with safe FFmpeg H.264 finalization.

**Architecture:** Keep `VideoFrameWriter` as the existing OpenCV `mp4v` streaming writer. Add a focused FFmpeg module for capability detection, temporary candidate management, encoder fallback, and atomic publication; the video pipeline writes `avc1` frames to a temporary `mp4v` source and explicitly finalizes it only after successful frame processing.

**Tech Stack:** Python 3.11, OpenCV, PIL, `subprocess`, FFmpeg CLI, `unittest`, `unittest.mock`.

## Global Constraints

- Continue on `feature/mediapipe-head-tracking` and PR #5.
- Do not create another branch or PR.
- Do not modify Multi-Pose, add GitHub Actions, merge, rebase pushed history, or force push.
- Default `video_codec` is exactly `mp4v`.
- `avc1` output is silent H.264 with `yuv420p` and `+faststart`.
- Prefer `h264_nvenc`; retry once with `libx264` when NVENC execution fails and libx264 is available.
- Default tests must not run real FFmpeg, models, network, CUDA, or external videos.
- Do not modify the existing Conda environment.
- Keep README.md, README_CN.md, docs/USAGE.md, and docs/USAGE_CN.md synchronized.

---

### Task 1: Runtime Configuration and CLI

**Files:**
- Modify: `gazelle/runtime/config.py`
- Modify: `gazelle/runtime/cli.py`
- Modify: `tests/test_runtime_cli.py`

**Interfaces:**
- Produces: `SUPPORTED_VIDEO_CODECS = ("mp4v", "avc1")`
- Produces: `validate_video_codec(value: str) -> str`
- Produces: `RuntimeConfig.video_codec: str`
- Consumes later: `config.video_codec`

- [ ] **Step 1: Write failing CLI/config tests**

Add tests that assert:

```python
def test_video_codec_defaults_to_mp4v(self):
    config = parse_config(["--input", "clip.mp4"])
    self.assertEqual(config.video_codec, "mp4v")

def test_parse_avc1_video_codec(self):
    config = parse_config(
        ["--input", "clip.mp4", "--video-codec", "avc1"]
    )
    self.assertEqual(config.video_codec, "avc1")

def test_invalid_video_codec_rejected(self):
    with self.assertRaises(SystemExit):
        parse_config(["--input", "clip.mp4", "--video-codec", "h264"])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B -m unittest tests.test_runtime_cli -v
```

Expected: failures because `--video-codec` and `RuntimeConfig.video_codec` do not exist.

- [ ] **Step 3: Implement the validated option**

In `config.py`:

```python
SUPPORTED_VIDEO_CODECS = ("mp4v", "avc1")


def validate_video_codec(value: str) -> str:
    codec = str(value).strip().lower()
    if codec not in SUPPORTED_VIDEO_CODECS:
        raise ValueError(
            "video_codec must be one of: {}".format(
                ", ".join(SUPPORTED_VIDEO_CODECS)
            )
        )
    return codec
```

Add `video_codec: str = "mp4v"`, validate it in `RuntimeConfig.validate()`,
and map `args.video_codec` in `RuntimeConfig.from_args()`.

In `cli.py`:

```python
parser.add_argument(
    "--video-codec",
    choices=("mp4v", "avc1"),
    default="mp4v",
    help=(
        "Rendered video codec. mp4v uses OpenCV directly; avc1 "
        "finalizes H.264 through FFmpeg."
    ),
)
```

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 1 test command. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add gazelle/runtime/config.py gazelle/runtime/cli.py tests/test_runtime_cli.py
git commit -m "Add video codec runtime option"
```

---

### Task 2: FFmpeg Capability and Transcode Layer

**Files:**
- Create: `gazelle/runtime/ffmpeg.py`
- Create: `tests/test_ffmpeg.py`

**Interfaces:**
- Produces: `FFmpegCapabilities(executable: str, encoders: Tuple[str, ...])`
- Produces: `detect_ffmpeg_capabilities(...) -> FFmpegCapabilities`
- Produces: `TemporaryVideoPath.beside(final_path, role, token=None)`
- Produces: `transcode_h264(source_path, final_path, capabilities, runner=None) -> str`
- Consumes later: video pipeline setup and finalization

- [ ] **Step 1: Write failing capability tests**

Cover:

```python
def test_missing_ffmpeg_reports_path_requirement(self):
    with self.assertRaisesRegex(RuntimeError, "FFmpeg.*PATH"):
        detect_ffmpeg_capabilities(which=lambda _: None)

def test_encoder_probe_prefers_nvenc_then_libx264(self):
    completed = SimpleNamespace(
        returncode=0,
        stdout=" V..... h264_nvenc\n V..... libx264\n",
        stderr="",
    )
    capabilities = detect_ffmpeg_capabilities(
        which=lambda _: "C:/ffmpeg/bin/ffmpeg.exe",
        runner=lambda *args, **kwargs: completed,
    )
    self.assertEqual(
        capabilities.encoder_order,
        ("h264_nvenc", "libx264"),
    )
```

Also cover failed probe and no supported encoder.

- [ ] **Step 2: Run capability tests and verify RED**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B -m unittest tests.test_ffmpeg -v
```

Expected: import failure because `gazelle.runtime.ffmpeg` does not exist.

- [ ] **Step 3: Implement capability detection and temporary paths**

Create:

```python
@dataclass(frozen=True)
class FFmpegCapabilities:
    executable: str
    encoders: Tuple[str, ...]

    @property
    def encoder_order(self) -> Tuple[str, ...]:
        return tuple(
            encoder
            for encoder in ("h264_nvenc", "libx264")
            if encoder in self.encoders
        )


@dataclass(frozen=True)
class TemporaryVideoPath:
    path: Path

    @classmethod
    def beside(cls, final_path, role: str, token=None):
        ...

    def close(self) -> None:
        self.path.unlink(missing_ok=True)
```

`detect_ffmpeg_capabilities()` resolves dependencies inside the function so
tests can inject `which` and `runner`. Probe with:

```python
[executable, "-hide_banner", "-encoders"]
```

Parse both stdout and stderr for exact encoder names.

- [ ] **Step 4: Run capability tests and verify GREEN**

Run the Task 2 test command. Expected: capability tests PASS.

- [ ] **Step 5: Write failing transcode tests**

Use a mocked runner that inspects the command and writes `Path(command[-1])`
only when simulating success.

Cover:

- command contains `-an`, `-pix_fmt yuv420p`, and `-movflags +faststart`;
- NVENC success uses one command;
- NVENC nonzero result retries libx264;
- all encoder failures include both diagnostics;
- successful process without candidate raises a clear error;
- success atomically publishes the candidate;
- candidate temporary files are removed after success and failure.

- [ ] **Step 6: Run transcode tests and verify RED**

Run the Task 2 command. Expected: failures because `transcode_h264()` is
missing.

- [ ] **Step 7: Implement safe H.264 finalization**

Build each command as an argument list:

```python
[
    capabilities.executable,
    "-hide_banner",
    "-loglevel",
    "error",
    "-y",
    "-i",
    str(source_path),
    "-an",
    "-c:v",
    encoder,
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    str(candidate.path),
]
```

Run with captured text output and `check=False`. On NVENC nonzero status,
delete the partial candidate and retry libx264. After a zero status, require
the candidate to exist, then call:

```python
os.replace(candidate.path, final_path)
```

Always close the candidate cleanup object in `finally`. Return the encoder
that published the file.

- [ ] **Step 8: Run FFmpeg tests and verify GREEN**

Run the Task 2 command. Expected: PASS with no real FFmpeg execution.

- [ ] **Step 9: Commit**

```powershell
git add gazelle/runtime/ffmpeg.py tests/test_ffmpeg.py
git commit -m "Add safe FFmpeg H264 finalization"
```

---

### Task 3: Video Pipeline Integration

**Files:**
- Modify: `gazelle/runtime/pipeline.py`
- Modify: `tests/test_video_pipeline.py`

**Interfaces:**
- Consumes: `config.video_codec`
- Consumes: `detect_ffmpeg_capabilities()`
- Consumes: `TemporaryVideoPath.beside(...)`
- Consumes: `transcode_h264(...)`
- Preserves: `VideoPipelineResult.rendered_video_path` as the formal final path

- [ ] **Step 1: Write failing pipeline routing tests**

Add tests proving:

1. default `mp4v` passes the final path directly to `VideoFrameWriter` and
   never calls FFmpeg detection/finalization;
2. `avc1` detects FFmpeg before reader/provider/predictor construction;
3. `avc1` passes a hidden temporary source path to `VideoFrameWriter`;
4. writer closes before `transcode_h264`;
5. the result reports the formal configured output path;
6. FFmpeg absence prevents reader/provider/predictor construction;
7. processing failure closes the writer and deletes the source temporary;
8. transcode failure deletes source/candidate temporary files.

Patch FFmpeg helpers and use existing fake reader/provider/predictor objects.
Do not execute real FFmpeg.

- [ ] **Step 2: Run pipeline tests and verify RED**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B -m unittest tests.test_video_pipeline -v
```

Expected: failures because codec routing is absent.

- [ ] **Step 3: Implement early detection and path routing**

At the start of `run_video_pipeline()`:

```python
ffmpeg_capabilities = None
if config.save_rendered and config.video_codec == "avc1":
    ffmpeg_capabilities = detect_ffmpeg_capabilities()
```

This must precede `VideoFrameReader`, output directory creation, provider
construction, and predictor construction.

When rendering:

```python
if config.video_codec == "avc1":
    rendered_source = TemporaryVideoPath.beside(
        rendered_video_path,
        "source",
    )
    writer_path = rendered_source.path
else:
    writer_path = rendered_video_path
```

Create the existing `VideoFrameWriter` with `writer_path`.

- [ ] **Step 4: Implement explicit finalization**

After frame processing and `run_config.json` writing:

```python
if writer is not None:
    writer.close()
    writer = None
if rendered_source is not None:
    transcode_h264(
        rendered_source.path,
        rendered_video_path,
        ffmpeg_capabilities,
    )
```

Add the source temporary cleanup object after the video writer in
`_close_video_resources()` so processing errors close OpenCV before unlinking
the source.

- [ ] **Step 5: Run pipeline tests and verify GREEN**

Run the Task 3 command. Expected: PASS.

- [ ] **Step 6: Run media and CLI regressions**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B -m unittest tests.test_media tests.test_runtime_cli -v
```

Expected: PASS; existing OpenCV `mp4v` behavior remains unchanged.

- [ ] **Step 7: Commit**

```powershell
git add gazelle/runtime/pipeline.py tests/test_video_pipeline.py
git commit -m "Integrate AVC video finalization"
```

---

### Task 4: Bilingual User Documentation

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/USAGE.md`
- Modify: `docs/USAGE_CN.md`
- Modify: `tests/test_usage_docs.py`

**Interfaces:**
- Documents: `--video-codec`, FFmpeg requirement, encoder fallback, silent
  output, and temporary/atomic behavior
- Updates: RuntimeConfig field count from 44 to 45

- [ ] **Step 1: Write failing documentation contract tests**

Require both guides to contain:

```text
--video-codec
mp4v
avc1
FFmpeg
h264_nvenc
libx264
yuv420p
+faststart
no audio
```

Update the expected RuntimeConfig field count to 45 and require a
`video_codec` row.

- [ ] **Step 2: Run documentation tests and verify RED**

Run:

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B -m unittest tests.test_usage_docs -v
```

Expected: failures for the missing option and field.

- [ ] **Step 3: Update all four documents**

Add synchronized examples:

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source mediapipe `
  --save-rendered `
  --video-codec avc1
```

Explain:

- default `mp4v` requires no FFmpeg;
- `avc1` requires FFmpeg on `PATH`;
- NVENC is preferred and libx264 is the fallback;
- output is `yuv420p` with fast-start metadata;
- source audio is not retained;
- codec selection is inert without `--save-rendered`;
- no real FFmpeg runs in default tests.

- [ ] **Step 4: Run documentation tests and verify GREEN**

Run the Task 4 command. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add README.md README_CN.md docs/USAGE.md docs/USAGE_CN.md tests/test_usage_docs.py
git commit -m "Document video codec selection"
```

---

### Task 5: Final Review, Verification, and Publication

**Files:**
- Review all milestone changes
- No new production files unless review finds a tested defect

**Interfaces:**
- Produces: verified commits on `feature/mediapipe-head-tracking`
- Produces: bilingual PR #5 milestone comment

- [ ] **Step 1: Request independent code review**

Review:

- subprocess safety;
- encoder fallback correctness;
- atomic replacement;
- cleanup ordering;
- early error timing;
- default compatibility;
- missing tests or documentation drift.

Fix Important/Critical findings with a failing regression test first.

- [ ] **Step 2: Run compileall outside the repository pycache**

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe `
  -X pycache_prefix=$env:TEMP\codex-gazelle-codec-final `
  -m compileall main.py gazelle tests
```

- [ ] **Step 3: Run the full offline test suite**

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B -m unittest discover -s tests -v
```

- [ ] **Step 4: Run CLI and Git checks**

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B main.py --help
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -B main.py --list-models
git diff --check
git status --short
```

- [ ] **Step 5: Confirm forbidden artifacts are absent**

Confirm no new:

```text
models/
outputs/
__pycache__/
*.pt
*.pth
*.mp4
temporary FFmpeg files
```

- [ ] **Step 6: Push normally**

Fetch first, confirm the remote branch is not ahead, then:

```powershell
git push origin feature/mediapipe-head-tracking
```

Do not force push.

- [ ] **Step 7: Publish a bilingual PR #5 comment**

Use English, then `---`, then Chinese. Include:

- Goal and changes;
- validation commands and exact test count;
- environment versions;
- no real FFmpeg/model/network/CUDA activity unless explicitly run;
- no audio;
- known limitations;
- all milestone commit SHAs.

