# Machine And Agent Handoff

[中文](HANDOFF_CN.md) | [Dated project state](CURRENT_STATE.md) |
[Shared workflow](../rules/AGENT_WORKFLOW.md) | [Full usage](../usage/USAGE.md)

## 1. Read In This Order

1. Root `AGENTS.md`: durable rules, boundaries, environment and validation policy.
2. `CURRENT_STATE.md`: branch/PR snapshot, completed features, evidence,
   uncommitted changes, open problems, and assets not included in the transfer.
3. This guide for a machine move; `AGENT_WORKFLOW.md` for switching/cooperating agents.
4. `USAGE.md` and the affected code/specs only when needed for the next task.

This package transfers project files and evidence, not chat memory, client
permissions, installed skills, credentials, or automatic access to another agent.
The workflow works with a new machine, two clients on one machine, or a reviewer
that receives only an explicit snapshot. No model API integration is required.

## 2. Preserve The Complete Source State

The accompanying portable archive contains:

| Entry | Purpose |
| --- | --- |
| `repository/` | Tracked source plus explicitly included handoff files and current uncommitted document edits |
| `history.bundle` | Reachable Git history of the handoff branch; ends at the recorded HEAD |
| `working-tree.patch` | Binary-capable diff of tracked changes against HEAD; new files are in `repository/` |
| `MANIFEST.json` | Snapshot SHA, branch, file sizes/hashes, overlay paths, exclusions and check evidence |
| `Restore-Handoff.ps1` | Offline restore into a new destination; validates payload hashes and restores Git plus overlay |
| `TRANSFER_README.md` | Package entry and exact restoration instructions |

The archive has a separate SHA-256 file. Hashes detect transfer corruption; they
are not a signature. Keep the original checkout until the destination passes
acceptance. Do not copy a live `.git` directory, a virtual environment folder,
or all hidden files as a substitute for a controlled migration.

**Offline route:** extract the archive to a new ordinary directory, review
`TRANSFER_README.md` and the restore script, then run this template in PowerShell:

```powershell
Get-FileHash 'D:\transfer\gazelle-handoff.zip' -Algorithm SHA256
& 'D:\transfer\gazelle-handoff\Restore-Handoff.ps1' -Destination 'D:\work\gazelle'
```

Replace the paths with the actual archive/extraction/destination paths. Compare
the archive hash with its delivered `.sha256`. The restore requires Git and
PowerShell, creates only a previously nonexistent destination, clones the local
bundle, overlays verified changed/new files, and sets `origin` to the GitHub URL.
Unchanged tracked files retain the destination Git checkout's line endings;
the full byte-for-byte source snapshot remains available in `repository/`.
It does not connect to GitHub, install dependencies, or run the application.
If PowerShell blocks execution, use your approved local script-signing/execution
process; do not disable machine-wide security controls. A failed restore leaves
its partial destination for inspection; choose another new path for a retry.

**GitHub route:** after authenticating independently on the new machine, clone
the recorded branch into a new directory and recheck remote state. Do not assume
the remote includes uncommitted AGENTS or this handoff. Prefer the offline restore
for the exact snapshot; reconcile later remote changes after establishing it.
No push, new PR, or branch creation is implied by possessing this archive.

## 3. Destination Environment

The recorded baseline is Windows with Python 3.14 and PyTorch CUDA 13.0 wheels.
Read the current `environment.yml` and source metadata in the snapshot. Different
OS/architecture/GPU combinations need a separately approved environment plan;
the file is not a cross-platform lock. Do not copy the old Conda directory or
blindly reuse `C:\Users\yun\...` paths.

First inspect without modifying an environment:

```powershell
conda env list
Get-Command git, conda, ffmpeg -ErrorAction SilentlyContinue
```

If `Gazelle-next` exists, activate it and inspect it; do not recreate/prune it. If it
does not exist, obtain authorization for a new destination environment before:

```powershell
conda env create -f environment.yml
conda activate Gazelle-next
```

Creation downloads dependencies and writes a new Conda environment. It was not
performed by this handoff. Existing-environment upgrades still require the
sandbox-first procedure in AGENTS. `environment_py311.yml` preserves the previous Python 3.11 environment named
`Gazelle`; activate that retained environment for rollback, or obtain approval
before recreating it from this file. `environment_1.0.yml` is the older NumPy 1.26
reference. Neither is a command to downgrade the current environment.

Run from the repository root. The source entry `python main.py` can use the
checkout directly. If editable package installation is needed, explicitly
authorize `python -m pip install --no-deps -e .`; it modifies the environment.

```powershell
conda activate Gazelle-next
python -B -c "import os,sys; print(os.environ.get('CONDA_DEFAULT_ENV')); print(sys.executable); print(sys.version)"
python -m pip check
```

The first command after activation reports identity only; `pip check` checks
installed dependency metadata without downloading or importing a model. Record
its actual errors; do not automatically upgrade packages to hide them. Confirm
the resolved interpreter belongs to the intended environment. FFmpeg is an
external executable, not installed by `environment.yml`. `avc1` needs a working
FFmpeg H.264 encoder; `mp4v` retains the OpenCV path. New encoder/driver setup
requires its own authorization.

## 4. Optional Caches And Research Media

- Source `models/checkpoints`, `models/mediapipe`, and `models/torch_hub` are
  excluded from the normal source package. Transfer separately only if desired,
  while no process is writing them. Record relative paths, sizes and SHA-256;
  compare after copying. Do not copy transient `.downloads` or lock files.
- Torch Hub cache includes executable Python as well as weights; reuse only a
  reviewed source cache. Source cache presence is not a destination test result.
- Missing resources may be downloaded by `--prepare-only` or first inference.
  Those operations require authorization and must record actual cache/network use.
- Original videos, annotations and known results are separate data artifacts.
  Copy only selected files with their matching run config and JSONL. Preserve
  originals and keep generated results out of Git. Paths in an old run_config
  describe the old run, not the new filesystem.
- Do not migrate `.codex`, `.claude` private settings, `.aws`, account tokens,
  global configs, or private agent memory by bulk copying. Sign in locally and
  grant only the needed repository permissions. The project's `CLAUDE.md` is
  portable; machine-specific configuration is not.

## 5. Acceptance Gates

Gate A is source identity: inspect restored branch/HEAD, manifest hashes, working
tree deltas, active instructions and asset exclusions. The expected initial
tree is dirty with the documented overlay, not an accidentally clean old clone.

Gate B is the offline runtime gate after environment identity is confirmed:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'gazelle-destination-pycache'
python -m compileall main.py gazelle tests
python -m unittest discover -s tests -v
python main.py --help
python main.py --list-models
git diff --check
git status --short
```

Use a task-specific pycache path for concurrent work. Preserve/restore any prior
environment-variable value after checks. These commands may write temporary
test files but default tests must not download models, build DINOv2, invoke real
FFmpeg, or execute CUDA. Record exit codes, exact test count, warnings and skips.

Gate C is an authorized real smoke test, independent from Gate B. First verify
the activated `Gazelle-next` environment and actual CUDA/FFmpeg capabilities. Example
preparation (may download and construct DINOv2, no media inference):

```powershell
python main.py --prepare-only --head-source mediapipe --pose-model full --model gazelle_dinov2_vitb14_inout --cache-dir models
```

For a real video, replace `USER_INPUT_PATH` and `USER_OUTPUT_ROOT` with an existing
video and a fresh output root. This template runs models, may use CUDA/download
missing resources, writes JSONL/config/rendered video, and invokes real FFmpeg:

```powershell
python main.py --input USER_INPUT_PATH --output-dir USER_OUTPUT_ROOT `
  --head-source mediapipe --max-heads 1 --pose-model full `
  --model gazelle_dinov2_vitb14_inout --device auto --cache-dir models `
  --max-frames 5 --save-rendered --video-codec avc1 `
  --face-pose-ray --pose-head-ray `
  --gazelle-head-mode eligible --gaze-render-mode valid-only
```

Check both JSONL row counts against `frames_written`, frame indices/timestamps,
`run_config.json`, and decoded rendered-frame count. `no_head`, `no_gaze`, or
`skipped` can be correct; do not force them to `ok`. Use a known visible head to
establish that at least one Gazelle prediction actually ran; an all-empty run
does not verify the model path. For comparison use a separate output root and
`--gazelle-head-mode all --gaze-render-mode all-predictions`. This is exploratory,
including active bridged heads; it cannot revive expired tracks or prove gaze
accuracy. Keep source and destination smoke results separate.

Gate D is agent onboarding: verify instruction loading and an actual small
task/review handoff. Neither this package nor historical test results prove that
a new Codex/Claude session obeys all rules. Use the shared workflow.

## 6. Ready-To-Send Agent Prompt

```text
You are taking over Hyakuri/gazelle. First read AGENTS.md,
docs/handoff/CURRENT_STATE.md, docs/handoff/HANDOFF.md, and docs/rules/AGENT_WORKFLOW.md.
Inspect actual branch, HEAD, working-tree changes and instruction sources.
Distinguish installed metadata, historical tests, and current validation.
Preserve existing edits; do not create branches/PRs, merge, force push, install,
download models, run real inference, or publish without applicable authority.
My role assignment is: <implementation owner OR read-only reviewer>.
My next task and permitted files are: <goal, scope, acceptance>.
First give a concise takeover report and identify blockers only where relevant.
Then complete the authorized task with risk-appropriate checks and evidence.
```

Fill the two role/task lines before use. For takeover only, set the task to
read-only inspection. For multi-session work use [TASK_TEMPLATE](TASK_TEMPLATE.md).
