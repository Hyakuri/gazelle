# Gazelle Repository Instructions

## Scope

These instructions apply to the entire repository. A more deeply nested
`AGENTS.md` may add or override rules only for its own subtree.

Keep this file limited to durable repository policy. Do not record a current
branch, pull request number, commit SHA, temporary milestone, or local output
path here. Discover those values from Git and the current task each time.

## Sources Of Truth

Use this precedence when instructions or artifacts disagree:

1. The user's explicit request in the current task.
2. The nearest applicable `AGENTS.md`.
3. An approved design or implementation plan for the current task.
4. Current code and tests for existing behavior.
5. Current user documentation.
6. Historical plans, summaries, comments, and old commit messages.

Treat historical documents as context, not proof of current behavior. Verify
unstable GitHub, dependency, model, and environment facts before reporting
them. When code and user documentation disagree, determine the intended
behavior from the current task and tests, then update both in the same change.

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

- Communicate with the user primarily in Chinese. Keep code identifiers, CLI
  options, schema fields, model names, and other technical literals in English.
- Continue routine work end to end without repeatedly asking for confirmation.
- Ask only when a decision materially changes architecture or scope, an action
  is destructive, the real Conda environment would be modified, required
  external information cannot be discovered, or ambiguity makes a safe choice
  impossible.
- For substantial work, provide concise progress updates and maintain a task
  checklist. Report what was learned, changed, and validated rather than
  narrating every command.
- Choose the execution style that maximizes correctness. On Windows, prefer
  Inline Execution when parallel agents cannot safely share the workspace.
  Use subagents only for genuinely independent tasks with clear ownership and
  no conflicting shared state. If delegation is unavailable, continue inline.
- Do not stop at a proposal when implementation has already been approved.
  Complete implementation, verification, and reporting unless blocked.

## Starting A Task

Before editing, inspect at least:

```powershell
git status -sb
git branch --show-current
git rev-parse HEAD
git log --oneline --decorate -5
```

- If the task names an existing branch or PR, continue using it. Do not create
  another branch or PR unless explicitly requested.
- If synchronization is required, use `git fetch origin --prune` followed by
  `git pull --ff-only` on the intended branch. Do not rebase pushed history.
- A clean workspace may proceed. Review task-related unfinished changes and
  continue them carefully.
- If local changes have an unknown source, do not overwrite, delete, stash, or
  revert them. Stop and report the affected files.
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
- Review `git diff`, `git diff --check`, and staged paths before committing.
- Never merge a PR unless explicitly requested.
- When an approved task belongs to an existing PR, finish validated work by
  committing and pushing the current branch, then post the bilingual PR update
  described below. Do not ask for another routine confirmation.
- If no existing PR context is known, do not invent one or create a PR. Report
  the validated local result and ask only if publication is required.

## Editing And Code Quality

- Read surrounding code and tests before changing behavior. Prefer existing
  patterns, helpers, contracts, and dependency boundaries.
- Use `rg` or `rg --files` for search. Parallelize independent read-only
  inspection when practical.
- Use patch-based edits for manual changes. Do not rewrite unrelated formatting
  or metadata.
- Keep code ASCII unless the file already requires another character set.
- Add comments only where behavior is not self-explanatory.
- Use structured parsers and typed contracts instead of ad hoc string parsing.
- Preserve backward compatibility by default. Add an abstraction only when it
  removes meaningful duplication or establishes a necessary ownership boundary.
- For behavior changes and bug fixes, add or update focused regression tests.
  Confirm that a new test would fail without the intended implementation when
  practical.

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

## Environment And Dependencies

- The preferred environment is the existing Conda environment `Gazelle`.
- On the current Windows host, when activation is unavailable, use:

  `C:\Users\yun\anaconda3\envs\Gazelle\python.exe`

- Do not create, update, prune, install into, or otherwise modify the real
  `Gazelle` environment without explicit user approval. This includes direct
  `pip install`, `conda install`, `conda env create -f environment.yml`, and
  `conda env update -f environment.yml --prune` operations.
- For a proposed dependency upgrade, first clone the existing `Gazelle`
  environment into a disposable sandbox, test imports and repository behavior
  there, report exact versions and conflicts, and wait for approval before
  applying the validated transaction to the real environment.
- `environment.yml` describes the current validated environment.
  `environment_1.0.yml` is the retained rollback/reference definition. Do not
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

During development, run the smallest relevant test module after each coherent
change. Before a final commit or push for code, CLI, schema, dependency, or
user-facing documentation work, run the complete offline gate with the
`Gazelle` interpreter:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-validation-pycache"
python -m compileall main.py gazelle tests
python -m unittest discover -s tests -v
python main.py --help
python main.py --list-models
git diff --check
git status --short
```

When the environment is not activated, replace `python` with the exact
interpreter path above. Keep bytecode outside the repository. Do not claim a
check passed unless the current run completed successfully; report the exact
test count and any non-fatal warnings separately.

A real model or media smoke test is optional unless the user requests it or the
change cannot otherwise be validated. It never replaces offline unit tests.

## Documentation Synchronization

For any user-visible CLI, dependency, download, output format, schema, model,
runtime behavior, or usage change, update all four user documents together:

- `README.md`
- `README_CN.md`
- `docs/USAGE.md`
- `docs/USAGE_CN.md`

Keep English and Chinese semantics synchronized. Commands must run from the
repository root and state whether they download resources, use CUDA, invoke
FFmpeg, run inference, write output, or only inspect configuration. Update
`tests/test_usage_docs.py` when the documented contract changes.

Do not add branch-specific phrases that become stale after merge. For a purely
internal change that needs no user-documentation update, say why in the final
report and PR comment.

## Models, Network, And Real Smoke Tests

- Never claim real model, network, cache, CUDA, MediaPipe, or FFmpeg validation
  unless it actually occurred in the current task.
- Run real image/video smoke tests only in the existing `Gazelle` environment.
- Use temporary input/output directories outside the repository where possible.
- Record the command, interpreter, relevant package versions, device, whether
  each resource was downloaded or reused, external network/Hub activity,
  frames processed, outputs produced, and cleanup status.
- A failed real test must be reported with its actual failure stage and error;
  never convert it into a success claim.

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

- Re-read the latest user request and verify every requested item is addressed.
- Review the final diff for regressions, unrelated changes, stale claims, and
  accidentally generated artifacts.
- Run the required fresh validation and read its final status.
- Confirm the workspace contains only expected changes, or is clean after the
  requested commit.
- Report concise concrete changes, validation, real external activity, known
  limitations, commit/push/PR status, and anything that could not be completed.
