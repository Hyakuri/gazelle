<!-- Source: docs/collab/STAGE2_PR_BODY.md. Claude maintains this file; Codex syncs it to GitHub with gh pr edit --body-file. -->

## Stage 2 goal

Make the three-camera work recordings usable and trustworthy as input, synchronize the cameras, fix the known perception defects, and build the region-labelling tool that stage 3 will be evaluated against.

## Project goal (confirmed by the user on 2026-10-15)

Three fixed monocular cameras film one workstation: two on the desks facing the worker (front: カメラ2, right: カメラ1) and the overview camera 設備カメラ between the two desks, looking down at both. Camera positions are the same in every recording. The system will fuse the three views to estimate, over time, which work region the worker attends to: pick-up desk, front work area, placement area, other in-cell targets, away from work, or absent. It will report time shares, dwell durations, transitions, and off-task time. Processing is offline. Multi-Pose integration is out of scope for now; multi-person inference and real-time processing are later goals.

## Findings that shaped this stage

- The current code cannot process the work data. All 11 AVI files contain empty packets, so OpenCV decodes one frame and the pipeline still reports success (GZ-21). 12 of 29 variable-frame-rate MP4 parts abort in MediaPipe on non-increasing timestamps (GZ-07, raised to P0).
- The burned-in clocks of the three cameras agree within one second. AVI container time drifts by about 0.2%, so synchronization must use the clocks.
- The face cameras see the face but not the desks; the overview camera sees the desks and hands but rarely the head. Region inference therefore needs multi-camera fusion (stage 3 proposal).
- `sample2.mp4` is an edited video from a different workplace, so validation moves to the work data.

Details: `docs/collab/analysis/2026-10-15-workdata-analysis.md`.

## Tasks

| Round | Task | Status |
| --- | --- | --- |
| 1 | TASK-131 Reader: container timestamps, strict monotonicity, fail on truncated decode | accepted |
| 1 | TASK-132 Work-data inventory and lossless AVI remux | accepted |
| 1 | TASK-123 Region marking tool for the overview camera | changes requested; fixed first in round 2 |
| 1 | TASK-001 Validate arguments before `--overwrite` deletes output | accepted |
| User | Draw the regions on the overview camera (about 10 minutes) | after the TASK-123 fix |
| 2 | TASK-137 Switch the project environment to `Gazelle-next` (environment files, AGENTS.md, user docs) | ready; first in round 2 |
| 2 | TASK-135 Round-1 follow-ups: drift-free timestamp fallback, stronger remux tail check, docs and tests | ready |
| 2 | TASK-133 Burned-in clock OCR, time maps, sync check | ready after TASK-132 |
| 2 | TASK-134 5 Hz synchronized proxies | ready after TASK-133 |
| 2 | TASK-121 Multi-view region labelling tool (D12 r2) | ready after TASK-134 |
| User | Label 26 one-minute segments (about 2 hours) | after round 2 review |
| 3 | TASK-136 Run Gazelle input preprocessing on the inference device | ready (D17 approved); first in round 3 |
| 3 | TASK-102 Confirm new tracks on their first frame (D2) | ready |
| 3 | TASK-002 Face ray and roll sign alignment | ready |
| 3 | TASK-101 Face–pose association fix (D1) | blocked on TASK-102 |
| — | Stage acceptance by Claude, final acceptance by the user | not started |

User decisions on 2026-10-15: the front camera is カメラ2 and the right camera is カメラ1; the user will draw the regions on the overview camera; each date has one worker and the camera positions are fixed; D4, D12 r2, and D13–D15 are approved. The stage 3 design is approved, and its task contracts will be written at stage 2 acceptance. The user accepted MediaPipe telemetry (GZ-23) for the development phase; security handling follows the research.

Environment evaluation on 2026-10-17 (`docs/collab/evidence/2026-10-17-env-next-evaluation.md`):

- Claude built a separate candidate environment, `Gazelle-next`, with Python 3.14, PyTorch 2.14, MediaPipe 1.1.1, and OpenCV 5.0. It passes the offline gate and the real checks, and its outputs match the current environment.
- MediaPipe 1.1.1 brings no accuracy or speed gain here. With 4K input, a Gazelle call is about 20% slower in the new environment because of CPU-side copies.
- Moving Gazelle preprocessing to the GPU (TASK-136) cuts a 4K call from about 99 ms to 36–41 ms in the full pipeline, and the outputs stay equivalent.
- User decisions on 2026-10-17:
  - D16: switch early. The existing `Gazelle` environment stays untouched as a rollback, and the project now uses `Gazelle-next`. TASK-137 makes the repository-side switch.
  - D17: TASK-136 is approved and opens round 3.

## How this PR is used

- Both agents start from `docs/collab/STATE.md`.
- Codex implements each task, pushes to this branch, and posts a bilingual report comment here after each push.
- Claude reviews by commit SHA and keeps this description current in `docs/collab/STAGE2_PR_BODY.md`; Codex syncs the file to this PR.
- The user follows progress here and accepts in an independent checkout.
- This PR stacks on PR #5. The user decided to merge the PR #2–#5 chain and this branch only after the project reaches its target functionality. Do not merge.

## Data and privacy

Work videos stay read-only on the local drive. Derived data, labels, and outputs stay outside the repository and are never uploaded. Reports contain aggregates only.

---

## 阶段 2 目标

让三台摄像机的作业录像能够作为可靠输入，把三台摄像机同步，修复已知的感知缺陷，并建立第 3 阶段评估所依据的区域标注工具。

## 项目目标（用户 2026-10-15 确认）

三台固定单目摄像机拍摄同一工位：两台放在桌面上对着作业者，前方为カメラ2，右侧为カメラ1；全局摄像机設備カメラ在两张工作台之间俯视两张桌面。各次录制的机位相同。系统融合三个视角，逐时刻判断作业者注视的作业区域：取货台、前方作业区、放置区、工作区内其他目标、离开工作或不在岗；并报告时间占比、停留时长、切换次数与离开工作的时间。以离线处理为主。暂不考虑 Multi-Pose 接口；多人推断与实时处理是后续目标。

## 影响本阶段安排的发现

- 当前代码无法处理作业数据。11 个 AVI 文件都含空数据包，OpenCV 只解出 1 帧，管线仍报告成功（GZ-21）。29 个可变帧率 MP4 分段中有 12 个因时间戳不递增在 MediaPipe 中止（GZ-07，升为 P0）。
- 三台摄像机的烧录时钟彼此相差不超过 1 秒；AVI 容器时间漂移约 0.2%，同步必须依据画面时钟。
- 人脸摄像机看得到脸、看不到桌面；俯视摄像机看得到桌面与双手，却很少拍到头部。区域推断因此需要多机融合（第 3 阶段提案）。
- `sample2.mp4` 是另一工作场所的剪辑视频，验证改用作业数据。

详见 `docs/collab/analysis/2026-10-15-workdata-analysis.md`。

## 任务

| 轮次 | 任务 | 状态 |
| --- | --- | --- |
| 1 | TASK-131 读取器：容器时间戳、严格递增、解码截断即失败 | accepted |
| 1 | TASK-132 作业数据清单与 AVI 无损重封装 | accepted |
| 1 | TASK-123 全局摄像机画面中的区域标记工具 | 退回修改，第 2 轮先修复 |
| 1 | TASK-001 在 `--overwrite` 删除输出前校验参数 | accepted |
| 用户 | 在全局摄像机画面上画出区域（约 10 分钟） | TASK-123 修复后 |
| 2 | TASK-137 项目环境切换到 `Gazelle-next`（环境文件、AGENTS.md、用户文档） | ready，第 2 轮第一项 |
| 2 | TASK-135 第 1 轮审查的后续加固：时间戳回退无漂移、重封装尾部检查、文档与测试 | ready |
| 2 | TASK-133 画面时钟识别、时间映射、同步检验 | TASK-132 之后 ready |
| 2 | TASK-134 5 Hz 同步代理视频 | TASK-133 之后 ready |
| 2 | TASK-121 多视角区域标注工具（D12 r2） | TASK-134 之后 ready |
| 用户 | 标注 26 个一分钟片段（约 2 小时） | 第 2 轮审查后 |
| 3 | TASK-136 Gazelle 输入预处理移到推理设备 | ready（D17 已同意），第 3 轮第一项 |
| 3 | TASK-102 新轨迹首帧即确认（D2） | ready |
| 3 | TASK-002 面部射线与 roll 符号对齐 | ready |
| 3 | TASK-101 人脸与姿态关联修正（D1） | 等 TASK-102 |
| — | Claude 阶段验收，用户最终验收 | 未开始 |

用户 2026-10-15 的决定：前方摄像机为カメラ2，右侧为カメラ1；区域由用户在全局摄像机画面上画出；同一日期为同一作业者，机位固定；批准 D4、D12 r2 与 D13 至 D15。第 3 阶段设计已批准，任务契约在阶段 2 验收时编写。用户决定开发阶段接受 MediaPipe 遥测（GZ-23），研究完成后再做安全处理。

2026-10-17 的环境评估（`docs/collab/evidence/2026-10-17-env-next-evaluation.md`）：

- Claude 另建了候选环境 `Gazelle-next`，包含 Python 3.14、PyTorch 2.14、MediaPipe 1.1.1 与 OpenCV 5.0。它通过了离线门与真实检查，输出与现用环境一致。
- MediaPipe 1.1.1 在本项目中没有精度或速度提升。4K 输入下，新环境的 Gazelle 单次调用约慢 20%，原因是 CPU 端的整帧复制。
- 把 Gazelle 的预处理移到 GPU（TASK-136）后，完整管线中 4K 单次调用由约 99 ms 降到 36 至 41 ms，输出等价。
- 用户 2026-10-17 的决定：
  - D16：尽早切换。现有 `Gazelle` 环境原样保留作回退，项目改用 `Gazelle-next`，仓库侧由 TASK-137 完成。
  - D17：同意 TASK-136，放在第 3 轮开头。

## 本 PR 的用法

- 两个 agent 都从 `docs/collab/STATE.md` 开始。
- Codex 实施每个任务，推送到本分支，并在每次推送后在这里发英中双语报告评论。
- Claude 按提交 SHA 审查，并在 `docs/collab/STAGE2_PR_BODY.md` 中维护本说明；Codex 把该文件同步到本 PR。
- 用户在这里查看进展，在独立目录验收。
- 本 PR 堆叠在 PR #5 之上。用户已决定：项目达到目标功能后，再集中梳理合并 PR #2 至 #5 与本分支。不要合并。

## 数据与隐私

作业视频在本机只读。派生数据、标注与输出都在仓库之外，不上传。报告只含汇总数字。

🤖 Generated with [Claude Code](https://claude.com/claude-code)
