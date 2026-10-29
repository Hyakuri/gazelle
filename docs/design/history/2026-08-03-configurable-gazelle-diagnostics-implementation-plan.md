# Configurable Gazelle Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independently configurable MediaPipe-to-Gazelle head selection and Gazelle prediction rendering policies while preserving conservative defaults.

**Architecture:** `RuntimeConfig` validates and stores an ordered selector tuple plus one render mode. `gaze_policy.py` remains the model-boundary owner, exposes ordered selected indices and heads, and pipelines use those indices both for predictor input and observation traceability. `PredictionRenderer` applies one shared geometry-visibility predicate to every heatmap, contour, arrow, and peak path.

**Tech Stack:** Python 3.11, `argparse`, frozen dataclasses, Pillow, NumPy, PyTorch tensors in renderer tests, `unittest`, existing fake providers/predictors and temporary media helpers.

## Global Constraints

- Work only on `feature/mediapipe-head-tracking` and the existing PR #5.
- Do not create another branch or PR, merge, rebase pushed history, or force push.
- Do not modify Multi-Pose or add GitHub Actions.
- Keep `--gazelle-head-mode eligible` and `--gaze-render-mode valid-only` as behavior-compatible defaults.
- Multiple head selectors use OR semantics; any occurrence of `all` canonicalizes to `("all",)`.
- `gaze_eligible` remains the conservative recommendation; `gazelle_selected` records the actual per-frame inference decision.
- `tracked_only` can only select a bridge observation already emitted within existing lifetime and confidence limits.
- Do not change MediaPipe thresholds, tracking, bbox validation, model weights, resource preparation, audio, or FFmpeg behavior.
- Update `README.md`, `README_CN.md`, `docs/USAGE.md`, and `docs/USAGE_CN.md` together.
- Use `C:\Users\yun\anaconda3\envs\Gazelle\python.exe`; do not modify the Conda environment.
- Tests must not download models, construct DINOv2, access the network, run real CUDA, or invoke real FFmpeg.
- Put bytecode under a temporary `PYTHONPYCACHEPREFIX`, never inside the repository.
- Do not commit models, caches, outputs, `__pycache__`, temporary media, or generated artifacts.
- PR comments must contain English and Chinese sections separated by `---`.

---

## File Structure

- `gazelle/runtime/config.py`: selector/render-mode constants, validators, `RuntimeConfig` fields, and argument mapping.
- `gazelle/runtime/cli.py`: user-facing multi-selector and render-mode arguments.
- `gazelle/runtime/perception/gaze_policy.py`: selector matching, alignment checks, ordered selected indices, and backward-compatible selected-head wrapper.
- `gazelle/runtime/perception/outputs.py`: serialize actual per-frame `gazelle_selected` state.
- `gazelle/runtime/pipeline.py`: apply selection before sidecar output and pass render mode to renderer.
- `gazelle/runtime/renderer.py`: central visibility predicate for all Gazelle geometry.
- `tests/test_runtime_cli.py`: defaults, parsing, normalization, and invalid configuration.
- `tests/test_gaze_policy.py`: preset, state, view, combined, and tracked-only selection behavior.
- `tests/test_outputs.py`: `gazelle_selected` schema and validation.
- `tests/test_image_pipeline.py`: image selection and run-config integration.
- `tests/test_video_pipeline.py`: selection, skipped-frame traceability, statuses, and lazy predictor behavior.
- `tests/test_renderer.py`: default suppression and diagnostic rendering in both renderer branches.
- `README.md`, `README_CN.md`: concise feature overview and examples.
- `docs/USAGE.md`, `docs/USAGE_CN.md`: complete CLI, output schema, semantics, and warnings.

### Task 1: Configuration and CLI Contract

**Files:**
- Modify: `gazelle/runtime/config.py`
- Modify: `gazelle/runtime/cli.py`
- Test: `tests/test_runtime_cli.py`

**Interfaces:**
- Produces: `SUPPORTED_GAZELLE_HEAD_MODE_SELECTORS: Tuple[str, ...]`
- Produces: `SUPPORTED_GAZE_RENDER_MODES: Tuple[str, ...]`
- Produces: `validate_gazelle_head_mode(value) -> Tuple[str, ...]`
- Produces: `validate_gaze_render_mode(value) -> str`
- Produces: `RuntimeConfig.gazelle_head_mode: Tuple[str, ...]`
- Produces: `RuntimeConfig.gaze_render_mode: str`

- [ ] **Step 1: Write failing configuration tests**

Add tests demonstrating the desired public contract:

```python
def test_gazelle_diagnostic_modes_default_to_conservative(self):
    config = parse_config(["--prepare-only"])
    self.assertEqual(config.gazelle_head_mode, ("eligible",))
    self.assertEqual(config.gaze_render_mode, "valid-only")

def test_parse_combined_gazelle_head_selectors(self):
    config = parse_config([
        "--prepare-only",
        "--gazelle-head-mode", "face_pose", "pose_only", "back_or_occluded", "tracked_only",
        "--gaze-render-mode", "all-predictions",
    ])
    self.assertEqual(
        config.gazelle_head_mode,
        ("face_pose", "pose_only", "back_or_occluded", "tracked_only"),
    )
    self.assertEqual(config.gaze_render_mode, "all-predictions")

def test_runtime_config_deduplicates_gazelle_head_selectors(self):
    config = RuntimeConfig(
        gazelle_head_mode=("face_pose", "pose_only", "face_pose"),
    ).validate()
    self.assertEqual(config.gazelle_head_mode, ("face_pose", "pose_only"))

def test_runtime_config_all_canonicalizes_gazelle_head_selectors(self):
    config = RuntimeConfig(
        gazelle_head_mode=("face_pose", "all", "tracked_only"),
    ).validate()
    self.assertEqual(config.gazelle_head_mode, ("all",))
```

Also test string normalization, empty iterable, boolean, non-string member,
unknown selector, and unknown render mode. Error assertions must name
`gazelle_head_mode` or `gaze_render_mode`.

- [ ] **Step 2: Run the focused CLI tests and verify RED**

Run:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-pycache-diagnostics"
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -p "test_runtime_cli.py" -v
```

Expected: new tests fail because the fields and arguments do not exist.

- [ ] **Step 3: Implement constants and validators**

Add exact selectors and modes:

```python
SUPPORTED_GAZELLE_HEAD_MODE_SELECTORS = (
    "eligible",
    "observed",
    "all",
    "face_pose",
    "face_only",
    "pose_only",
    "tracked_only",
    "frontal",
    "profile",
    "back_or_occluded",
    "unknown",
)
SUPPORTED_GAZE_RENDER_MODES = ("valid-only", "all-predictions")
```

`validate_gazelle_head_mode` accepts one string or a non-empty iterable,
requires exact string members, removes duplicates in first-seen order, and
returns `("all",)` whenever `all` occurs. `validate_gaze_render_mode` strips a
string and accepts only the two supported values.

Add frozen dataclass fields:

```python
gazelle_head_mode: Tuple[str, ...] = ("eligible",)
gaze_render_mode: str = "valid-only"
```

Validate both in `RuntimeConfig.validate()` and map both from parsed args in
`RuntimeConfig.from_args()`.

- [ ] **Step 4: Add CLI arguments**

Add:

```python
parser.add_argument(
    "--gazelle-head-mode",
    nargs="+",
    choices=SUPPORTED_GAZELLE_HEAD_MODE_SELECTORS,
    default=("eligible",),
    metavar="SELECTOR",
    help="Select MediaPipe heads for Gazelle using one or more OR-combined selectors.",
)
parser.add_argument(
    "--gaze-render-mode",
    choices=SUPPORTED_GAZE_RENDER_MODES,
    default="valid-only",
    help="Render only valid Gazelle geometry or every actual prediction.",
)
```

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the Task 1 focused command. Expected: all `test_runtime_cli.py` tests pass.

- [ ] **Step 6: Commit Task 1**

```powershell
git add gazelle/runtime/config.py gazelle/runtime/cli.py tests/test_runtime_cli.py
git commit -m "Add Gazelle diagnostic mode configuration"
```

### Task 2: Head Selection Policy and Traceable Observation Output

**Files:**
- Modify: `gazelle/runtime/perception/gaze_policy.py`
- Modify: `gazelle/runtime/perception/outputs.py`
- Test: `tests/test_gaze_policy.py`
- Test: `tests/test_outputs.py`

**Interfaces:**
- Consumes: normalized `RuntimeConfig.gazelle_head_mode`
- Produces: `select_gazelle_head_indices(result, selectors=("eligible",)) -> Tuple[int, ...]`
- Preserves: `select_gazelle_heads(result, selectors=("eligible",)) -> Tuple[HeadObservation, ...]`
- Extends: `head_frame_to_json_dict(..., gazelle_selected_indices=None) -> dict`

- [ ] **Step 1: Write failing selector-policy tests**

Create table-driven tests over existing `perception(...)` helpers. Cover:

```python
def test_observed_selector_excludes_tracked_only(self):
    result = result_for(current_face, tracked_only)
    self.assertEqual(select_gazelle_head_indices(result, ("observed",)), (0,))

def test_all_selector_includes_tracked_only(self):
    result = result_for(current_face, tracked_only)
    self.assertEqual(select_gazelle_head_indices(result, ("all",)), (0, 1))

def test_explicit_state_and_view_selectors_use_or_semantics(self):
    result = result_for(face_pose, face_only, pose_only, tracked_only)
    self.assertEqual(
        select_gazelle_head_indices(
            result,
            ("face_only", "back_or_occluded", "tracked_only"),
        ),
        (1, 2, 3),
    )

def test_eligible_can_be_combined_with_pose_only(self):
    result = result_for(eligible_face, rejected_face, pose_only)
    self.assertEqual(
        select_gazelle_head_indices(result, ("eligible", "pose_only")),
        (0, 2),
    )
```

Retain alignment tests for unequal lengths and mismatched IDs. Assert providers
with no perceptions return every head for every selector mode.

- [ ] **Step 2: Write failing observation-schema tests**

In `tests/test_outputs.py`, add rich-perception assertions:

```python
record = head_frame_to_json_dict(
    frame_index=0,
    timestamp_ms=0.0,
    image_width=64,
    image_height=48,
    provider="mediapipe",
    result=result,
    save_face_landmarks=False,
    gazelle_selected_indices=(1,),
)
self.assertFalse(record["people"][0]["gazelle_selected"])
self.assertTrue(record["people"][1]["gazelle_selected"])
```

Test duplicate, negative, out-of-range, boolean, and non-integer selected
indices. Verify omitted indices default to conservative selection. Bare
none/static/json records remain schema-compatible and do not gain a misleading
perception-only field.

- [ ] **Step 3: Run policy/output tests and verify RED**

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -p "test_gaze_policy.py" -v
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -p "test_outputs.py" -v
```

Expected: missing selection-index API and `gazelle_selected` field failures.

- [ ] **Step 4: Implement ordered selector matching**

Add `_matches_gazelle_selector(perception, selector)` with these exact rules:

```python
if selector == "all":
    return True
if selector == "observed":
    return perception.observed
if selector == "eligible":
    return perception.gaze_eligible and _rejection_status(perception) is None
if selector == perception.state.value:
    return True
if selector == perception.view_state.value:
    return True
return False
```

`select_gazelle_head_indices` validates existing alignment invariants, returns
all indices for no-perception providers, and returns each matching MediaPipe
index once in original order. `select_gazelle_heads` wraps this function and
keeps its default conservative signature.

- [ ] **Step 5: Serialize actual selection**

Extend `_perception_to_json_dict` with a required keyword-only
`gazelle_selected` boolean and serialize it beside `gaze_eligible`.
`head_frame_to_json_dict` validates explicit indices and computes conservative
default indices through `select_gazelle_head_indices` when omitted.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run both Task 2 commands. Expected: all focused tests pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add gazelle/runtime/perception/gaze_policy.py gazelle/runtime/perception/outputs.py tests/test_gaze_policy.py tests/test_outputs.py
git commit -m "Add configurable Gazelle head selection"
```

### Task 3: Image and Video Pipeline Integration

**Files:**
- Modify: `gazelle/runtime/pipeline.py`
- Test: `tests/test_image_pipeline.py`
- Test: `tests/test_video_pipeline.py`

**Interfaces:**
- Consumes: `select_gazelle_head_indices(result, config.gazelle_head_mode)`
- Consumes: `head_frame_to_json_dict(..., gazelle_selected_indices=indices)`
- Produces: predictor input matching observation `gazelle_selected` flags

- [ ] **Step 1: Write failing image-pipeline tests**

Add a fake MediaPipe result containing one eligible face, one pose-only head,
and one tracked-only head. Assert:

- default mode calls predictor with only the eligible face;
- `("pose_only",)` calls predictor with only pose-only head;
- `("face_pose", "tracked_only")` preserves provider order;
- image `head_observations.json` has `gazelle_selected=true` exactly for heads
  passed to predictor;
- `run_config.json` contains the normalized selector tuple as a JSON list and
  the render-mode string.

- [ ] **Step 2: Write failing video-pipeline tests**

Extend the tracked-only regression to assert:

```python
# compatible default
self.assertEqual(row["status"], "no_gaze")
self.assertEqual(predictor.calls, [])

# explicit diagnostic selection
config = replace(config, gazelle_head_mode=("tracked_only",))
self.assertEqual(row["status"], "ok")
self.assertEqual(predictor.calls[0][0].person_id, tracked_id)
```

Add a `frame_step=2` test proving skipped frames set every
`gazelle_selected=false`, even when their perceptions would match `all`, and do
not call the predictor. Add a no-match test retaining `status=no_gaze`.

- [ ] **Step 3: Run pipeline tests and verify RED**

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -p "test_image_pipeline.py" -v
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -p "test_video_pipeline.py" -v
```

Expected: modes do not affect predictor input and sidecars lack actual
selection flags.

- [ ] **Step 4: Integrate image selection before output**

Compute selected indices immediately after `get_frame_result`, derive
`gazelle_heads` from those indices, and pass the same indices to
`write_head_observations_json`. Preserve output-directory and lazy predictor
ordering.

- [ ] **Step 5: Integrate frame-step-aware video selection**

For every frame:

1. Run perception.
2. If `frame.index % frame_step == 0`, compute selected indices using the
   configured selector tuple; otherwise use `()`.
3. Write the observation row with those exact indices.
4. Apply existing `skipped`, `no_head`, `no_gaze`, and `ok` status precedence.
5. Pass only selected ordered heads to the predictor.

This preserves the invariant that `gazelle_selected=true` means inference was
actually requested on that frame.

- [ ] **Step 6: Pass render mode through pipeline render options**

Add:

```python
gaze_render_mode=config.gaze_render_mode,
```

to `_render_options_from_config`.

- [ ] **Step 7: Run pipeline tests and verify GREEN**

Run both Task 3 commands. Expected: all focused pipeline tests pass.

- [ ] **Step 8: Commit Task 3**

```powershell
git add gazelle/runtime/pipeline.py tests/test_image_pipeline.py tests/test_video_pipeline.py
git commit -m "Wire diagnostic modes into media pipelines"
```

### Task 4: Prediction Renderer Mode

**Files:**
- Modify: `gazelle/runtime/renderer.py`
- Test: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `RenderOptions.gaze_render_mode`
- Produces: one shared `_should_draw_gaze_geometry(prediction, options) -> bool`
- Preserves: `render_predictions(...)` defaults and existing byte output

- [ ] **Step 1: Write failing renderer tests**

Retain the existing default suppression test and add:

```python
def test_all_predictions_mode_draws_out_of_frame_gazelle_geometry(self):
    image = Image.new("RGB", (64, 64), color=(20, 20, 20))
    prediction = replace(make_prediction(), gaze_status=GazeStatus.OUT_OF_FRAME)
    options = RenderOptions(
        gaze_render_mode="all-predictions",
        draw_head_box=False,
        draw_labels=False,
    )
    rendered = PredictionRenderer(options).render(image, (prediction,))
    self.assertNotEqual(rendered.tobytes(), image.tobytes())
```

Add equivalent coverage with a perception tuple, and isolate heatmap, contour,
arrow, and peak flags so every geometry path is proven to obey the same mode.
Assert `GazePrediction.gaze_status` and score remain unchanged. Test that
`PredictionRenderer` rejects an invalid `RenderOptions.gaze_render_mode`.

- [ ] **Step 2: Run renderer tests and verify RED**

```powershell
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -p "test_renderer.py" -v
```

Expected: `RenderOptions` lacks the mode and out-of-frame geometry stays hidden.

- [ ] **Step 3: Implement one rendering predicate**

Add `gaze_render_mode: str = "valid-only"` to `RenderOptions`, validate it when
constructing `PredictionRenderer`, and implement:

```python
def _should_draw_gaze_geometry(prediction, options):
    return (
        options.gaze_render_mode == "all-predictions"
        or prediction.gaze_status is GazeStatus.VALID
    )
```

Replace every direct `gaze_status is GazeStatus.VALID` gate for heatmaps,
contours, arrows, and peaks with this predicate in both renderer branches.
Extend `render_predictions` with a trailing defaulted `gaze_render_mode`
keyword to retain source compatibility.

- [ ] **Step 4: Run renderer and pipeline tests and verify GREEN**

Run the Task 4 renderer command, followed by both Task 3 commands. Expected:
all tests pass and default render bytes remain unchanged.

- [ ] **Step 5: Commit Task 4**

```powershell
git add gazelle/runtime/renderer.py tests/test_renderer.py
git commit -m "Add diagnostic Gazelle rendering mode"
```

### Task 5: User Documentation and Full Validation

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `docs/USAGE.md`
- Modify: `docs/USAGE_CN.md`

**Interfaces:**
- Documents: all selectors, OR semantics, compatible defaults, output schema,
  diagnostic warnings, and image/video examples.

- [ ] **Step 1: Update English and Chinese README summaries together**

Replace claims that non-eligible perceptions are never sent to Gazelle with
the default-policy wording. Add one diagnostic video command showing multiple
selectors and `all-predictions`. Explain that `all` may include bridge-only
boxes but cannot revive expired tracks.

- [ ] **Step 2: Update both usage guides together**

Add both options to the complete parameter tables. Update:

- startup examples;
- model-boundary description;
- rendering controls;
- observation schema with `gazelle_selected`;
- `no_gaze` definition;
- `run_config.json` field table;
- tracked-only caveat;
- one conservative command and one fully diagnostic command.

Explicitly state that diagnostic heatmaps are model outputs for experimental
comparison, not validated eye-gaze measurements.

- [ ] **Step 3: Check bilingual synchronization and stale absolute claims**

```powershell
rg -n "never sent|绝不会送入|only eligible|只有 eligible|tracked_only" README.md README_CN.md docs/USAGE.md docs/USAGE_CN.md
rg -n "gazelle-head-mode|gaze-render-mode|gazelle_selected" README.md README_CN.md docs/USAGE.md docs/USAGE_CN.md
```

Expected: old unconditional claims are removed or qualified by the default
policy, and all four files describe both options and the new field.

- [ ] **Step 4: Run fresh full validation**

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-pycache-diagnostics-final"
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m compileall main.py gazelle tests
C:\Users\yun\anaconda3\envs\Gazelle\python.exe -m unittest discover -s tests -v
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --help
C:\Users\yun\anaconda3\envs\Gazelle\python.exe main.py --list-models
git diff --check
git status --short
```

Expected: compilation and every unit test pass; help shows both new options;
model listing remains unchanged; diff check is clean; status contains only the
expected documentation changes before commit.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md README_CN.md docs/USAGE.md docs/USAGE_CN.md
git commit -m "Document Gazelle diagnostic controls"
```

- [ ] **Step 6: Verify repository contents and push**

Check tracked and ignored status for prohibited artifacts, then push the
current branch without force:

```powershell
git status --short
git status --short --ignored
git push origin feature/mediapipe-head-tracking
```

- [ ] **Step 7: Publish bilingual PR #5 comment**

Post English first and Chinese after `---`. Include:

- Goal: independently control inference selection and rendering visibility.
- Changes: selector presets/state/view OR combinations, tracked-only opt-in,
  all-predictions rendering, and `gazelle_selected` traceability.
- Validation: exact commands and final test count.
- Real model/network activity: no model download, DINOv2, PyTorch Hub, CUDA,
  real FFmpeg, or environment modification unless a separate smoke test is
  actually run.
- README: all four English/Chinese user documents updated.
- Known limitation: diagnostic results for occluded/stale heads are not
  calibrated eye gaze.
- Commits: list every milestone SHA and subject.
