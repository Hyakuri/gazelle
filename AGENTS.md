# Gazelle Repository Instructions

## Scope

These instructions apply to the repository within the platform's instruction
hierarchy and tool permissions. A nested `AGENTS.md` applies only to its subtree.
Check applicable overrides when instruction discovery is relevant; manually
reading a file does not prove it was loaded automatically.

Keep this file limited to durable repository policy. Do not record a current
branch, pull request number, commit SHA, temporary milestone, or local output
path here. Discover those values from Git and the current task each time.

Use relevant skills within the user's authorized scope without starting a
second competing workflow. Do not incidentally change global instructions,
skills, plugins, model settings, or permissions while doing repository work.

Start every session by reading `docs/collab/STATE.md`. It names the current
stage and branch, whose turn it is, the active task record, and what to do
next. `docs/rules/COLLABORATION_PLAN_CN.md` defines the procedure and extends
`docs/rules/AGENT_WORKFLOW.md`. Do not write files while the `writer` field in
`docs/collab/STATE.md` names another agent. For machine migration, read
`docs/handoff/HANDOFF.md` on demand. `CLAUDE.md` imports this file; keep project
policy here rather than maintaining different rules for each agent.

## Sources Of Truth

Within project instructions, use this precedence when sources disagree:

1. The user's explicit request in the current task.
2. The nearest applicable `AGENTS.md`.
3. An approved design or implementation plan for the current task.
4. Current code and tests for existing behavior.
5. Current user documentation.
6. Historical plans, summaries, comments, and old commit messages.

Code and tests establish existing behavior, not authority to rewrite an
approved research or evaluation protocol. When implementation, documentation,
and specifications disagree, identify the intended contract and report the
discrepancy. Preserve uncertain scientific or safety constraints until resolved.
Historical documents are context, not proof of current behavior. Verify changing
GitHub, dependency, model, and environment facts when they matter to the task.

## Project Boundaries

- Work in this Gazelle repository unless the user explicitly names another
  repository.
- Multi-Pose is a downstream integration target. Do not modify Multi-Pose
  unless the user explicitly requests it.
- Do not add or modify GitHub Actions unless explicitly requested.
- Do not implement adjacent roadmap items merely because they are mentioned in
  a design or known-limitations section.
- Keep changes scoped to the requested milestone and preserve existing public
  behavior unless the task intentionally changes it.

## Autonomy And Communication

- Communicate primarily in Chinese; keep technical identifiers in English.
- Default to Inline Execution. The main agent owns the goal, contracts, key
  implementation, integration, self-review, and final acceptance.
- Complete authorized work without routine reconfirmation. Ask only for
  unresolved consequential choices or actions lacking necessary authority;
  pause affected work and continue independent safe work.
- Small tasks need direct implementation and suitable checks. For cross-module
  or high-risk work, first define contracts, dependencies, and acceptance.
  Maintain a checklist or handoff record when multiple stages or session
  continuity make it useful. Give concise updates about findings, decisions,
  and remaining uncertainty rather than narrating every command.
- Delegate when an independent investigation, specialist review, or module with
  stable interfaces benefits. Zero subagents is valid; usually start with zero
  to two concurrent helpers and explain any useful expansion. Prefer read-only
  tasks; do not create an agent or document for every small step.
- Give delegates the goal, necessary context, baseline, permitted paths,
  prohibitions, acceptance criteria, and evidence to return. No recursive
  delegation or scope expansion; reuse a delegate for related follow-up.
- Allow one writer at a time in a shared workspace. Parallel writers require
  isolated checkouts and explicit interface ownership; worktrees alone do not
  isolate GPU use, environments, ports, caches, or outputs. Reviews need a stable
  target, and test processes may write files.
- Repeated fixes without progress call for a fresh root-cause and contract
  check, not a fixed number of retries or additional agents.

## Starting A Task

Before editing, establish the repository root, applicable instructions, working
tree changes, branch, HEAD, and recent history:

```powershell
git status -sb
git branch --show-current
git rev-parse HEAD
git log --oneline --decorate -5
```

Reuse still-applicable context during the task; recheck when the tree or task
changes. Read affected code, tests, and relevant specifications on demand:

| Work | Starting points |
| --- | --- |
| CLI/config | `main.py`, `gazelle/runtime/cli.py`, `gazelle/runtime/config.py`, `tests/test_runtime_cli.py` |
| Model boundary/geometry | `gazelle/runtime/contracts.py`, `gazelle/runtime/geometry.py`, `gazelle/runtime/predictor.py`, `gazelle/runtime/heads.py`; matching tests |
| Perception/tracking | `gazelle/runtime/perception/`, matching tests, relevant approved design in `docs/design/` |
| Media/rendering/output | `gazelle/runtime/pipeline.py`, `gazelle/runtime/media.py`, `gazelle/runtime/outputs.py`, `gazelle/runtime/renderer.py`, `gazelle/runtime/ffmpeg.py`; matching tests |
| Resources/environment | `environment.yml`, `environment_1.0.yml`, `gazelle/runtime/resources.py`, `gazelle/runtime/environment.py`, `gazelle/runtime/perception/resources.py` |
| Usage/schema | `docs/usage/USAGE.md`, `docs/usage/USAGE_CN.md`, matching README sections, `tests/test_usage_docs.py` |
| Research evaluation | Relevant approved protocol, `scripts/eval_gazefollow.py`, `scripts/eval_vat.py`, `gazelle/utils.py` |

Do not read every route or historical plan for every task.

- If the task names an existing branch or PR, continue using it. Do not create
  another branch or PR unless explicitly requested.
- If synchronization is required, use `git fetch origin --prune` followed by
  `git pull --ff-only` on the intended branch. Do not rebase pushed history.
- A clean workspace may proceed. Review task-related unfinished changes and
  continue them carefully.
- Preserve unknown local changes: do not overwrite, delete, stash, or revert
  them. Pause conflicting edits and report affected files; unrelated changes
  do not block independent work.
- If Git reports unsafe repository ownership, use a command-scoped
  `git -c safe.directory=<repo> ...`; do not change global Git configuration.

## Git Safety And Delivery

- Never use `git reset --hard`, `git checkout --`, `git restore` to discard
  work, `git clean`, or another destructive cleanup without an explicit,
  path-specific user request.
- Do not force push or rewrite pushed history. If a normal push is rejected,
  fetch and inspect the remote change, then stop and report the conflict.
- Never revert user changes merely to obtain a clean diff. Work with relevant
  changes and ignore unrelated ones.
- Use focused commits with imperative English commit messages.
- Before authorized publication, review relevant committed, staged, unstaged,
  and untracked changes, not just a base-to-HEAD diff. Check exact staged paths
  and `git diff --check` results.
- Never merge a PR unless explicitly requested.
- Staging, committing, pushing, and PR publication require authorization covering
  the task, repository, and action. Honor existing explicit standing authority
  without asking again; an existing PR alone does not grant it. A current
  local-only restriction overrides earlier delivery defaults.
- When publication is authorized, use the current branch and existing PR,
  complete required validation, and post the bilingual update below.
- If no existing PR context is known, do not invent one or create a PR. Report
  the validated local result and ask only if publication is required.

## Editing And Code Quality

- Read nearby code and tests; reuse existing helpers, typed contracts, structured
  parsers, and dependency boundaries. Preserve compatibility unless the task
  intentionally changes it.
- Use `rg` or `rg --files`; batch independent reads when useful. Use patch-based
  manual edits, keep code ASCII unless the file needs other characters, and
  avoid unrelated formatting, metadata changes, or redundant comments.
- Add abstractions only for meaningful duplication or a necessary boundary.
- For defects, establish a minimal reproduction or focused regression test,
  then make the smallest adequate fix. Verify that the test detects the original
  defect when practical. Behavior changes need focused coverage; cosmetic edits
  need no artificial tests.

## Runtime Invariants

Preserve these invariants unless the current task explicitly redesigns them:

- `HeadProvider` produces ordered `HeadObservation` values and does not run
  Gazelle, read video, render output, or write prediction files.
- Provider bboxes reaching `GazellePredictor` are normalized, finite, clipped,
  nonempty, and aligned with `person_id` order. A single `bbox=None` fallback is
  allowed where the predictor contract permits it; invalid multi-person bbox
  combinations are rejected before the upstream model is called.
- A frame with no selected heads does not construct or call the Gazelle model.
- MediaPipe `gaze_eligible` remains the conservative recommendation;
  `gazelle_selected` records the actual per-frame scheduling decision.
- Diagnostic selection does not revive expired tracks, fabricate stale face
  evidence, or change prediction status. Rendering options do not mutate
  predictions or JSON/JSONL output.
- `--gaze-inout-threshold` classifies `gaze_status` independently from
  `--gaze-render-mode`.
- Video processing remains streaming. Do not load a complete video into memory.
  Keep observation, prediction, and rendered-frame counts aligned.
- Output-directory conflicts and required external capabilities are checked
  before model construction or inference whenever possible.
- Downloads use validated temporary staging and atomic replacement. A failed
  refresh must preserve an existing valid cache entry.
- H.264 finalization uses temporary files and atomic publication. It does not
  preserve audio unless a future task explicitly changes that policy.

## Research And Data Integrity

- Protect original inputs, annotations, weights, and existing formal results.
  Preserve approved splits, label meanings, missing-value handling, normalization,
  randomness, metric formulas, and aggregation unless a task explicitly changes
  the protocol. Never hide failures by relaxing assertions, excluding failing
  samples, leaking evaluation data, or silently changing metrics.
- Preserve normalized `(xmin, ymin, xmax, ymax)` bbox ordering, `person_id`
  alignment, frame indices, millisecond timestamps, and declared angle/coordinate
  conventions across conversions and outputs. Reuse geometry validation.
- Gazelle receives RGB image tensors and head bboxes; face/pose metadata remains
  separate. The two independent head-pose rays are uncalibrated 2D references,
  not measured eye gaze or calibrated 3D rays. Missing evidence stays missing.
- Distinguish provider absence (`no_head`), selector rejection (`no_gaze`),
  skipped inference, and an actual prediction. Diagnostic modes may select active
  `tracked_only` perceptions but must retain expiry and geometry checks.
- For evaluation changes, inspect the relevant protocol and metric functions.
  Do not assume GazeFollow and VideoAttentionTarget use interchangeable AUC or
  L2 definitions. A successful smoke test does not establish scientific accuracy.

## Environment And Dependencies

- The preferred environment is the existing Conda environment `Gazelle-next`.
- On the current Windows host, when activation is unavailable, use:

  `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`

- That absolute path is source-host-specific. On another machine, discover and
  verify the existing `Gazelle-next` interpreter; do not create directories to mimic
  the old path. Creating a destination environment needs authorization and must
  not overwrite an existing environment. See `docs/handoff/HANDOFF.md` for acceptance.

- Do not create, update, prune, install into, or otherwise modify the real
  `Gazelle-next` environment without explicit user approval. This includes direct
  `pip install`, `conda install`, `conda env create -f environment.yml`, and
  `conda env update -f environment.yml --prune` operations.
- For a proposed dependency upgrade, first clone the existing `Gazelle-next`
  environment into a disposable sandbox, test imports and repository behavior
  there, report exact versions and conflicts, and wait for approval before
  applying the validated transaction to the real environment.
- The existing `Gazelle` environment is retained as a rollback, described by
  `environment_py311.yml`, and also must not be modified without explicit approval.
- `environment.yml` describes the current validated environment.
  `environment_py311.yml` is the previous Python 3.11 rollback definition;
  `environment_1.0.yml` is the older NumPy 1.26 reference definition. Do not
  downgrade the working environment to match historical upstream pins.
- If an approved environment change is applied, update environment files and
  all four English/Chinese user documents from actually verified versions.
- Do not install Triton merely to satisfy optional xFormers paths. Preserve the
  runtime's scoped xFormers/Triton fallback behavior unless explicitly changing
  it.

## Default Test Isolation

Default unit tests must not:

- access the network;
- download checkpoints, DINOv2 code/weights, or MediaPipe assets;
- construct a real DINOv2 backbone;
- require CUDA or execute real CUDA inference;
- invoke real FFmpeg;
- require external image or video files; or
- modify the Conda environment.

Use fakes, mocks, dependency injection, and `TemporaryDirectory` for these
boundaries. Generate temporary media outside the repository and clean it up.

## Validation

Choose checks by behavioral impact, not line count. Inspect a test's boundaries
before running it; its name does not guarantee no network, writes, or cost.

- During development, run focused checks for the affected contract. Reuse
  recorded evidence only while the tested content, dependencies, and configuration
  remain applicable; rerun affected checks after changes or failures.
- Pure prose or internal instruction edits need static checks for diff, encoding,
  Markdown, references, and retained constraints. Do not run the full project
  suite solely for cosmetic wording changes.
- Command/schema documentation needs the relevant documentation checks. Code,
  CLI, schema, dependency, or documented behavior changes retain the complete
  offline gate below before delivery or authorized publication. Run it on the
  final relevant state, not after every small edit.
- Always self-review actual changes. Research semantics, core algorithms, public
  interfaces, compatibility-sensitive changes, other high-risk work, and major
  implementation milestones require independent review of a stable state. One
  reviewer may cover specification and code quality. Batch similar low-risk
  changes; do not require paired reviews or a full SDD workflow for each task.
- If required independent review is unavailable, report it as pending acceptance;
  do not present self-review or a subagent's DONE as equivalent. Unresolved
  blocking defects prevent delivery of results that depend on them.

Use the existing `Gazelle-next` interpreter for the full offline gate:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-validation-pycache"
python -m compileall main.py gazelle tests
python -m unittest discover -s tests -v
python main.py --help
python main.py --list-models
git diff --check
git status --short
```

When not activated, use the exact interpreter under Environment And Dependencies.
Keep bytecode outside the repository. Before reporting success, verify command
exit status, failures/skips, test count, and nonfatal warnings against the
applicable state. Label prior evidence as prior, and unrun checks as unrun.

Keep static checks, mocked tests, real model/GPU/FFmpeg smoke tests, and formal
experiments distinct. A real smoke test is optional unless requested or necessary
to validate the change; it requires applicable authorization and never replaces
offline tests.

## Documentation Synchronization

For any user-visible CLI, dependency, download, output format, schema, model,
runtime behavior, or usage change, update all four user documents together:

- `README.md`
- `README_CN.md`
- `docs/usage/USAGE.md`
- `docs/usage/USAGE_CN.md`

Keep English and Chinese semantics synchronized. Commands must run from the
repository root and state whether they download resources, use CUDA, invoke
FFmpeg, run inference, write output, or only inspect configuration. Update
`tests/test_usage_docs.py` when the documented contract changes.

Do not add branch-specific phrases that become stale after merge. For a purely
internal change that needs no user-documentation update, say why in the final
report and PR comment.

## Documentation Records

`docs/rules/DOCS_SYSTEM_CN.md` defines the project's documentation records.

- Documents live in category folders: `docs/requirements/`, `docs/design/`,
  `docs/rules/`, `docs/collab/`, `docs/usage/`, `docs/handoff/`, and
  `docs/archive/`. Put a new document in the matching folder.

- Controlled documents are the design baselines and the process rules listed
  there. Every change to one gets a new `MAJOR.MINOR.PATCH` version in its
  front matter and a new top row in its version log. It is then archived with
  `python -m tools.docs release`.
- Snapshots and baselines under `docs/archive/` are append-only. A rollback is a
  new version restored from an archived one, never a rewrite of history.
- `docs/portal/index.html` and `docs/README.md` are generated from the
  documents. Never edit them by hand.
  - After changing any source, run `python -m tools.docs build`.
  - Before a handoff, `python -m tools.docs check` must pass.
- `docs/superpowers/` is the superpowers skills' workspace.
  - Its files are copies of project files, synchronized by the tool.
  - The project file in its category folder is authoritative.
  - When a skill writes or edits a file there, adopt it into the project folder
    with `python -m tools.docs adopt`, or register a new project file, before
    the handoff.
- Progress belongs in `docs/collab/ROADMAP.md` and `docs/collab/STATE.md`, not
  in controlled documents.
- Publishing the generated page to any external service requires the user's
  approval each time.

## Models, Network, And Real Smoke Tests

- Run real image/video smoke tests only in the existing `Gazelle-next` environment.
  Model downloads, installs, training, batch processing, paid/shared services,
  and other external activity need authorization covering those actions.
  Reuse valid prior authorization; stop only the unauthorized dependent action.
- Never claim real model, network, cache, CUDA, MediaPipe, or FFmpeg validation
  unless it occurred and is identified as such. Static inspection or mocks
  cannot demonstrate device availability, speed, or model accuracy.
- Prefer temporary input/output directories outside the repository. Record the
  command, interpreter, relevant versions, device, resource download/cache reuse,
  network/Hub activity, frame counts, produced outputs, and cleanup status.
- Report real-test failures with their actual stage and error. Do not modify
  dependencies or the environment as an unapproved attempt to make a test pass.

## Generated And Sensitive Artifacts

Do not commit:

- model weights such as `*.pt`, `*.pth`, or `*.onnx`;
- Torch Hub, MediaPipe, or other model caches;
- `models/`, `outputs/`, `__pycache__/`, bytecode, coverage, or temporary files;
- generated smoke-test images, videos, JSON/JSONL, or rendered media; or
- tokens, passwords, credentials, private keys, or authentication data.

Tracked project assets are an exception only when the task explicitly requires
them and they are reviewed intentionally. Before committing, inspect staged
paths and ignored artifacts so generated files cannot enter Git accidentally.

The repository is private, so PR comments may include useful local paths,
environment versions, model/cache activity, and validation details. Privacy
does not permit publishing secrets or credentials.

## GitHub Reporting

When posting a commit update to an existing PR, write English first, then a line
containing `---`, then a concise Chinese translation. Preserve technical names
and literals in English. Include:

1. Goal
2. Changes
3. Validation, with exact commands and results
4. Real model/network/environment activity
5. Documentation status
6. Known limitations
7. Commit SHA and subject

Update an existing PR rather than creating a duplicate. Do not change draft
state, title, body, base branch, or merge status unless the user requests it or
the current task explicitly includes that action.

## Completion Checklist

Before reporting completion:

- Recheck the latest request, final diff, retained scientific/safety constraints,
  required acceptance, and any blocked dependent work.
- Inspect all changed and new files, including untracked files; preserve existing
  work and report the actual workspace state.
- Report concrete changes, applicable validation evidence, unrun checks, real
  external activity, remaining risks, and actual commit/push/PR status.
- Only claim completion of the work and checks performed. Saving instruction
  files does not prove a new session loaded them or that performance improved.
