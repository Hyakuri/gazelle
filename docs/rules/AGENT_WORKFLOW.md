# Shared Agent Workflow

[中文](AGENT_WORKFLOW_CN.md) | [Migration](../handoff/HANDOFF.md) |
[Task template](../handoff/TASK_TEMPLATE.md)

## 1. One Policy, Explicit Ownership

`AGENTS.md` is shared project policy. `CLAUDE.md` imports it rather than duplicating
it. Read only task-relevant documentation and the current task record. This
workflow is a human-coordinated convention, not a scheduler, filesystem lock,
permission configuration, or cross-product message transport.

Default: one implementation owner (Codex or Claude), another agent optionally
reviews a stable snapshot read-only. Roles can rotate; neither product is
intrinsically the coordinator. The human chooses a single coordinator per task.
Ordinary ChatGPT/Claude web chats do not acquire repository access from these
files: supply the documents and diffs explicitly or use an authorized local
coding client. Do not assume conversations or memories synchronize.

## 2. Task Lifecycle

1. The coordinator records the goal, baseline SHA and working-tree delta,
   acceptance, write ownership, resource reservations, and publication authority
   using the template. Keep small tasks in chat; persist multi-session handoffs.
2. The owner inspects the actual tree, acknowledges scope, and performs focused
   implementation and validation. Stop only the part blocked by a conflict.
3. Freeze writes before review. Provide HEAD plus staged/unstaged diffs and all
   relevant new files, or a hashed snapshot. HEAD alone misses uncommitted work.
4. The reviewer reports severity, exact file/line, evidence, reproduction, and
   remaining gaps. No code edits, checkout/reset/install, or unapproved tests.
   If the snapshot changed, re-review affected portions before acceptance.
5. The owner resolves findings. Required independent review that is unavailable
   stays pending; a DONE response is not acceptance evidence.
6. For handover, stop running writers first, record final files and command
   results, release resources, and have the next owner acknowledge the baseline.
   Only the authorized integration owner stages, commits, pushes, or comments.

The coordinator is the sole editor of a persisted active task record; helpers
return reports without racing to update it. With separate clones/machines,
identify one canonical coordinator record and distribute acknowledged copies.
A stale timestamp is not permission to take ownership. Missing acknowledgments
or an active writer block takeover, not unrelated read-only work.

## 3. Shared Computer And Resources

| Resource | Coordination rule |
| --- | --- |
| Same checkout and Git index | One writer at a time, even for different files; no concurrent checkout/stage/commit |
| Reviewer | Read-only stable snapshot; tests may write and need explicit task allocation |
| Parallel implementation | Only when authorized, isolated checkouts and explicit interfaces; current no-new-branch rule still applies |
| GPU | One allocated job unless measured capacity and task authorization allow more; record device and process owner |
| Conda `Gazelle` | Runtime reads may share; package changes are exclusive and require approved sandbox-first workflow |
| Torch Hub / MediaPipe caches | Prefer prepared read-only reuse; serialize preparation/refresh; no concurrent force-download |
| Outputs and temporary media | Unique task/agent directories; never use `--overwrite` on another owner's results |
| Ports, subprocesses, temporary pycache | Allocate per task; track process IDs and clean only owned resources |
| GitHub | One authorized publisher for the existing PR; no independent competing pushes |

A worktree isolates source files, not Git metadata operations, packages, GPU,
cache, or outputs. No new branches/worktrees are created by this handoff.
Do not use auto-sync folders to merge two live checkouts. Between machines,
exchange commits when authorized or reviewed patches/snapshots with their base.

## 4. Validation And Scientific Meaning

Apply the risk-based gate in AGENTS. Static prose checks are enough for wording;
behavior changes require relevant regressions and the full offline gate. Metric,
coordinate, timing, threshold, interface, and compatibility changes require
independent review even if the diff is one line. No model/network/CUDA/real
FFmpeg activity in default tests. Optional real tests require authorization,
resource ownership, exact commands, and separately reported results.

Every report distinguishes observed behavior, interpretation, and proposal.
Preserve raw observations and prediction status when comparing render modes.
Do not present head-pose rays or a model heatmap peak as measured eye gaze.

## 5. Client Startup Check

Start at the repository root. Ask the agent to identify visible instruction
sources, its role, allowed files, prohibited actions, and unresolved acceptance.
Distinguish startup-loaded instructions from later manual reads. A local/global
override or client setting may change effective loading; report it rather than
changing settings without authorization. Verify again after changing clients.

Codex documents directory-scoped AGENTS discovery. Claude Code supports imports
from CLAUDE.md; this project's explicit import avoids maintaining a second
policy. Support depends on client/version/settings; this task did not launch a
Claude session or verify a fresh Codex session. Official references, checked
2026-10-14: [Codex instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[Claude Code memory](https://code.claude.com/docs/en/memory).

No plugin, model API, account credential, persistent agent, or unattended
automation is required or installed by this workflow.
