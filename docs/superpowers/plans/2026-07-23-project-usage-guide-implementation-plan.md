# Project Usage Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add complete English and Chinese usage guides that document every current CLI option and provide a directly executable MediaPipe head-perception-to-Gazelle gaze inference workflow.

**Architecture:** Keep detailed operational documentation in two structurally equivalent standalone files under `docs/`, with short discoverability links in the existing READMEs. Add an offline unit test that derives option names from `build_parser()` so future CLI additions cannot silently escape both guides.

**Tech Stack:** Markdown, Python `unittest`, `argparse`, existing Gazelle runtime CLI.

## Global Constraints

- Work only on `feature/mediapipe-head-tracking` and PR #5.
- Do not create another branch or PR, merge, rebase pushed history, force push, add GitHub Actions, or modify Multi-Pose.
- Do not change runtime behavior, CLI behavior, dependencies, model files, cache files, outputs, or the local Conda environment.
- Keep English and Chinese user-facing documentation synchronized.
- Examples must run from the repository root and use PowerShell syntax.
- Document whether commands download resources, construct DINOv2, use CUDA, run inference, or write files.
- Default validation must not access the network, download weights, construct real DINOv2, use CUDA, or run real image/video inference.
- PR comments must contain English and Chinese sections separated by `---`.

---

### Task 1: Add Complete Bilingual Usage Guides

**Files:**
- Create: `docs/USAGE.md`
- Create: `docs/USAGE_CN.md`
- Create: `tests/test_usage_docs.py`
- Modify: `README.md`
- Modify: `README_CN.md`

**Interfaces:**
- Consumes: `gazelle.runtime.cli.build_parser()` and `parse_runtime_config(argv)`.
- Produces: two complete usage guides, README navigation links, and an offline documentation contract test.

- [ ] **Step 1: Write the failing documentation contract test**

Create `tests/test_usage_docs.py` with this behavior:

```python
import re
import unittest
from pathlib import Path

from gazelle.runtime.cli import build_parser, parse_runtime_config


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ENGLISH_GUIDE = REPOSITORY_ROOT / "docs" / "USAGE.md"
CHINESE_GUIDE = REPOSITORY_ROOT / "docs" / "USAGE_CN.md"


class UsageDocumentationTest(unittest.TestCase):
    def _read(self, path):
        return path.read_text(encoding="utf-8")

    def test_every_long_cli_option_is_documented_in_both_guides(self):
        parser = build_parser()
        long_options = sorted(
            {
                option
                for action in parser._actions
                for option in action.option_strings
                if option.startswith("--")
            }
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            guide = self._read(guide_path)
            missing = [option for option in long_options if option not in guide]
            self.assertEqual([], missing, "{} is missing CLI options".format(guide_path))

    def test_readmes_link_to_the_matching_usage_guides(self):
        english_readme = self._read(REPOSITORY_ROOT / "README.md")
        chinese_readme = self._read(REPOSITORY_ROOT / "README_CN.md")
        self.assertIn("(docs/USAGE.md)", english_readme)
        self.assertIn("(docs/USAGE_CN.md)", chinese_readme)

    def test_mediapipe_end_to_end_command_is_documented_and_parseable(self):
        argv = [
            "--input",
            r"samples\assembly.mp4",
            "--output-dir",
            "outputs",
            "--overwrite",
            "--head-source",
            "mediapipe",
            "--max-heads",
            "1",
            "--pose-model",
            "full",
            "--head-track-max-gap-ms",
            "500",
            "--model",
            "gazelle_dinov2_vitb14_inout",
            "--device",
            "cuda",
            "--cache-dir",
            "models",
            "--save-rendered",
            "--head-box",
            "--face-box",
            "--face-keypoints",
            "--pose-head-points",
            "--face-mesh",
        ]
        config = parse_runtime_config(argv)
        self.assertEqual("mediapipe", config.head_source)
        self.assertEqual("full", config.pose_model)
        self.assertTrue(config.save_rendered)

        patterns = (
            r"--head-source\s+mediapipe",
            r"--pose-model\s+full",
            r"--head-track-max-gap-ms\s+500",
            r"--model\s+gazelle_dinov2_vitb14_inout",
            r"--cache-dir\s+models",
            r"--save-rendered",
        )
        for guide_path in (ENGLISH_GUIDE, CHINESE_GUIDE):
            guide = self._read(guide_path)
            for pattern in patterns:
                self.assertRegex(guide, re.compile(pattern))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-docs-pycache"
& "C:\Users\yun\anaconda3\envs\Gazelle\python.exe" -m unittest tests.test_usage_docs -v
Remove-Item Env:PYTHONPYCACHEPREFIX
```

Expected: failure because `docs/USAGE.md` and `docs/USAGE_CN.md` do not yet exist.

- [ ] **Step 3: Write `docs/USAGE.md`**

Use the exact section order from
`docs/superpowers/specs/2026-07-23-project-usage-guide-design.md` and include:

- current supported image suffixes `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`;
- current supported video suffixes `.mp4`, `.avi`, `.mov`, `.mkv`, `.m4v`;
- environment setup using `environment.yml`, `conda activate Gazelle`, and
  `pip install -e .`;
- cache priority `--cache-dir`, `GAZELLE_CACHE_DIR`, then `models`;
- cache layout `checkpoints/`, `mediapipe/`, and `torch_hub/`;
- the four runtime model names from `gazelle/runtime/model_registry.py`;
- `--prepare-only` examples both with and without `--head-source mediapipe`;
- a complete option table with columns for option, accepted value/default,
  scope, and behavior;
- provider-specific examples for `none`, repeated `static` bboxes, image JSON,
  video JSONL, JSON list records, and `mediapipe`;
- image inference, raw image heatmaps, image rendering, video inference,
  frame stepping, frame limits, and video rendering examples;
- independent head-observation output and Gazelle prediction output schemas;
- output status semantics `ok`, `no_head`, `skipped`, and reserved `error`;
- download/network/device/xFormers behavior and current limitations.

The primary end-to-end command must appear exactly as a PowerShell command and
must include the arguments exercised by the test. Explain this data flow:

```text
MediaPipe Face Detector / Face Landmarker / Pose Landmarker
  -> fusion
  -> ByteTrack and 500 ms short-occlusion bridge for video
  -> normalized HeadObservation
  -> GazellePredictor
  -> gaze heatmap / peak / in-out score
  -> head_observations.jsonl / predictions.jsonl / rendered.mp4
```

State that first use may download the Gazelle checkpoint, DINOv2 repository and
weights, and MediaPipe task assets. State that rendered videos do not preserve
audio and that this is offline processing rather than webcam/real-time mode.

- [ ] **Step 4: Write `docs/USAGE_CN.md`**

Mirror the English section order and technical content in Chinese. Keep CLI
options, model names, filenames, environment variables, JSON field names, enum
values, and code literal values in English. Preserve the same executable
PowerShell examples. Translate explanatory prose without changing defaults,
validation rules, network behavior, output semantics, or limitations.

- [ ] **Step 5: Add README navigation links**

Near the top of `README.md`, add a short link:

```markdown
For complete runtime setup, every CLI option, input/output schemas, and runnable
image/video workflows, see the [Project Usage Guide](docs/USAGE.md).
```

Near the top of `README_CN.md`, add the matching Chinese link:

```markdown
有关完整 runtime 配置、全部 CLI 参数、输入/输出 schema 及可直接执行的图片/视频工作流，请参阅[项目使用说明](docs/USAGE_CN.md)。
```

- [ ] **Step 6: Run focused documentation tests**

Run:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-docs-pycache"
& "C:\Users\yun\anaconda3\envs\Gazelle\python.exe" -m unittest tests.test_usage_docs -v
Remove-Item Env:PYTHONPYCACHEPREFIX
```

Expected: 3 tests pass without network or model activity.

- [ ] **Step 7: Review documentation accuracy and synchronization**

Check:

```powershell
rg -n "TBD|TODO|implement later|fill in" docs/USAGE.md docs/USAGE_CN.md
rg -n "^## " docs/USAGE.md
rg -n "^## " docs/USAGE_CN.md
git diff --check
```

Expected: no placeholders, matching high-level section counts/order, and no
whitespace errors.

- [ ] **Step 8: Commit the implementation**

```powershell
git add docs/USAGE.md docs/USAGE_CN.md README.md README_CN.md tests/test_usage_docs.py
git commit -m "Add comprehensive project usage guides"
```

### Task 2: Validate And Publish The Documentation Milestone

**Files:**
- Modify only if validation uncovers a documentation or test defect:
  `docs/USAGE.md`, `docs/USAGE_CN.md`, `README.md`, `README_CN.md`,
  `tests/test_usage_docs.py`

**Interfaces:**
- Consumes: Task 1 guides and tests.
- Produces: validated branch state and a bilingual PR #5 milestone comment.

- [ ] **Step 1: Run the full offline validation**

Use the existing Conda environment and a temporary bytecode cache:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-validation-pycache"
& "C:\Users\yun\anaconda3\envs\Gazelle\python.exe" -m compileall main.py gazelle tests
& "C:\Users\yun\anaconda3\envs\Gazelle\python.exe" -m unittest discover -s tests -v
& "C:\Users\yun\anaconda3\envs\Gazelle\python.exe" main.py --help
& "C:\Users\yun\anaconda3\envs\Gazelle\python.exe" main.py --list-models
Remove-Item Env:PYTHONPYCACHEPREFIX
git diff --check
git status --short
```

Expected: compile, all tests, help, model listing, and diff check pass; the
working tree is clean after any necessary fix commit.

- [ ] **Step 2: Confirm validation activity boundaries**

Record that validation performed:

- no checkpoint download;
- no DINOv2 construction;
- no PyTorch Hub access;
- no MediaPipe asset download;
- no real CUDA execution;
- no image/video inference;
- no Conda environment modification.

- [ ] **Step 3: Push the current branch**

```powershell
git push origin feature/mediapipe-head-tracking
```

Do not force push and do not change PR draft status.

- [ ] **Step 4: Add a bilingual PR #5 comment**

Post an English section followed by `---` and a concise Chinese section. Include:

- goal and changed files;
- all validation commands and results;
- exact test count;
- real model/network activity boundaries;
- confirmation that runtime and CLI behavior did not change;
- both commits:
  `Document project usage guide design` and
  `Add comprehensive project usage guides`.
