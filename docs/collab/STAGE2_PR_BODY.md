<!-- Source: docs/collab/STAGE2_PR_BODY.md. Claude maintains this file; Codex syncs it to GitHub with gh pr edit --body-file. -->

## Stage 2 goal

Make the three-camera work recordings usable and trustworthy as input, synchronize the cameras, fix the known perception defects, and build the region-labelling tool that stage 3 will be evaluated against.

## Project goal (confirmed by the user on 2026-10-15)

Three fixed monocular cameras film one workstation: two on the desks facing the worker (front and right) and one in the corner looking down at both desks. The system will fuse the three views to estimate, over time, which work region the worker attends to: pick-up desk, front work area, placement area, other in-cell targets, away from work, or absent. It will report time shares, dwell durations, transitions, and off-task time. Processing is offline. Multi-Pose integration is out of scope for now; multi-person inference and real-time processing are later goals.

## Findings that shaped this stage

- The current code cannot process the work data. All 11 AVI files contain empty packets, so OpenCV decodes one frame and the pipeline still reports success (GZ-21). 12 of 29 variable-frame-rate MP4 parts abort in MediaPipe on non-increasing timestamps (GZ-07, raised to P0).
- The burned-in clocks of the three cameras agree within one second. AVI container time drifts by about 0.2%, so synchronization must use the clocks.
- The face cameras see the face but not the desks; the overview camera sees the desks and hands but rarely the head. Region inference therefore needs multi-camera fusion (stage 3 proposal).
- `sample2.mp4` is an edited video from a different workplace, so validation moves to the work data.

Details: `docs/collab/analysis/2026-10-15-workdata-analysis.md`.

## Tasks

| Round | Task | Status |
| --- | --- | --- |
| 1 | TASK-131 Reader: container timestamps, strict monotonicity, fail on truncated decode | ready |
| 1 | TASK-132 Work-data inventory and lossless AVI remux | ready |
| 1 | TASK-001 Validate arguments before `--overwrite` deletes output | ready |
| 2 | TASK-133 Burned-in clock OCR, time maps, sync check | ready after TASK-132 |
| 2 | TASK-134 5 Hz synchronized proxies | ready after TASK-133 |
| 2 | TASK-121 Multi-view region labelling tool (D12 r2) | ready after TASK-134 |
| User | Answer Q7 and Q8, then label 26 one-minute segments (about 2 hours) | pending |
| 3 | TASK-102 Confirm new tracks on their first frame (D2) | ready |
| 3 | TASK-002 Face ray and roll sign alignment | ready |
| 3 | TASK-101 Face–pose association fix (D1) | blocked on TASK-102 |
| — | Stage acceptance by Claude, final acceptance by the user | not started |

Pending user input: Q7 (which face camera is front and which is right), Q8 (region classes), Q9 (worker identity and future recordings), and D13–D15 for stage 3. D4 and the revised D12 were adopted by the coordinator and can be vetoed.

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

三台固定单目摄像机拍摄同一工位：两台放在桌面上对着作业者（前方与右侧），一台在夹角处俯视两张桌面。系统融合三个视角，逐时刻判断作业者注视的作业区域：取货台、前方作业区、放置区、工作区内其他目标、离开工作或不在岗；并报告时间占比、停留时长、切换次数与离开工作的时间。以离线处理为主。暂不考虑 Multi-Pose 接口；多人推断与实时处理是后续目标。

## 影响本阶段安排的发现

- 当前代码无法处理作业数据。11 个 AVI 文件都含空数据包，OpenCV 只解出 1 帧，管线仍报告成功（GZ-21）。29 个可变帧率 MP4 分段中有 12 个因时间戳不递增在 MediaPipe 中止（GZ-07，升为 P0）。
- 三台摄像机的烧录时钟彼此相差不超过 1 秒；AVI 容器时间漂移约 0.2%，同步必须依据画面时钟。
- 人脸摄像机看得到脸、看不到桌面；俯视摄像机看得到桌面与双手，却很少拍到头部。区域推断因此需要多机融合（第 3 阶段提案）。
- `sample2.mp4` 是另一工作场所的剪辑视频，验证改用作业数据。

详见 `docs/collab/analysis/2026-10-15-workdata-analysis.md`。

## 任务

| 轮次 | 任务 | 状态 |
| --- | --- | --- |
| 1 | TASK-131 读取器：容器时间戳、严格递增、解码截断即失败 | ready |
| 1 | TASK-132 作业数据清单与 AVI 无损重封装 | ready |
| 1 | TASK-001 在 `--overwrite` 删除输出前校验参数 | ready |
| 2 | TASK-133 画面时钟识别、时间映射、同步检验 | TASK-132 之后 ready |
| 2 | TASK-134 5 Hz 同步代理视频 | TASK-133 之后 ready |
| 2 | TASK-121 多视角区域标注工具（D12 r2） | TASK-134 之后 ready |
| 用户 | 回答 Q7、Q8，然后标注 26 个一分钟片段（约 2 小时） | 待前置 |
| 3 | TASK-102 新轨迹首帧即确认（D2） | ready |
| 3 | TASK-002 面部射线与 roll 符号对齐 | ready |
| 3 | TASK-101 人脸与姿态关联修正（D1） | 等 TASK-102 |
| — | Claude 阶段验收，用户最终验收 | 未开始 |

待用户输入：Q7（哪台人脸摄像机是前方、哪台是右侧）、Q8（区域类别）、Q9（作业者身份与后续录制），以及第 3 阶段的 D13 至 D15。D4 与修订后的 D12 由协调者先行采用，用户可以否决。

## 本 PR 的用法

- 两个 agent 都从 `docs/collab/STATE.md` 开始。
- Codex 实施每个任务，推送到本分支，并在每次推送后在这里发英中双语报告评论。
- Claude 按提交 SHA 审查，并在 `docs/collab/STAGE2_PR_BODY.md` 中维护本说明；Codex 把该文件同步到本 PR。
- 用户在这里查看进展，在独立目录验收。
- 本 PR 堆叠在 PR #5 之上。用户已决定：项目达到目标功能后，再集中梳理合并 PR #2 至 #5 与本分支。不要合并。

## 数据与隐私

作业视频在本机只读。派生数据、标注与输出都在仓库之外，不上传。报告只含汇总数字。

🤖 Generated with [Claude Code](https://claude.com/claude-code)
