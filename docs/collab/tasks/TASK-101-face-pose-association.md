# TASK-101：人脸与姿态关联修正与连续性选择（决策 D1）

状态：changes-requested（Claude 2026-10-31 第 9 轮审查，见 §3）。实现符合契约 r3，规则本身有缺陷。契约修订 r4 在 §3 末尾，第 9 轮继续
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
问题来源：GZ-01（主线程新发现，见分析报告 §5）。设计：[2026-10-15 规范 §4](../../design/PERCEPTION_D1_D2_DESIGN.md)。
授权：用户 2026-10-15 批准 D1 按 Claude 的推荐执行。

## 1. 契约

### 目标

任何模式下都不再把一个人的脸与另一个人的姿态融合成同一个头框；单人模式在多人入镜时稳定地跟住同一个主体。

### 必须实现

按规范 §4 实现，要点如下：

1. **候选池**：新增唯一定义的 `candidate_pool_size(max_heads)`，返回 `max(max_heads, 3)`。`MediaPipeBackend` 取前 `pool` 个人脸检测做 landmark 裁剪，`PoseLandmarkerOptions.num_poses = pool`；`FaceLandmarkerOptions.num_faces` 不变。
2. **关键点包含约束**：`associate_face_pose` 在原几何门控之外，增加规范 §4.2 的锚点测试（鼻点；否则至少两个头部关键点；否则双肩；否则失败）。
3. **统一匹配**：删除 `build_head_candidates` 中 `max_heads == 1` 的特殊分支，所有情况都走配对匹配；对外签名与“返回前 `max_heads` 个”的语义不变。
4. **选择**：`arbitrate_perceptions` 增加可选参数 `previous_selection`，按规范 §4.4 的三步确定选择：空间连续（有新观测）、身份连续（含桥接）、按原优先级补足；返回保持原顺序。
5. **provider**：视频模式把整个候选池交给 tracker；每帧选择后记录 `(person_id, head_bbox)`，并对所有 `max_heads` 调用 `bridge.retain_person_ids`。图像模式先按优先级选择，再把 `person_id` 重新编号为 `0..n-1`。
   - **契约 r2（2026-10-18，与 TASK-102 的 GZ-30 修复合并）**：临时头对桥接的维护必须“中立”。
     - 规则：每帧另做一次只含已确认感知（排除全部 provisional）的选择，规则与正式选择相同，也传入 `previous_selection`。把这次选择得到的 `person_id` 传给 `retain_person_ids`。
     - 正式输出仍用包含 provisional 的完整选择。
     - 后果：
       - 一帧 spawn 无论是否胜出，都不改变哪些桥接被保留，与它不存在时的结果完全相同。
       - 同一物理位置真正换了身份时，旧身份的桥接在新身份确认的那一帧才被删除，比规范 §4.4 的原写法晚一帧。
     - 依据：第 4 轮审查中，独立审查用真实 ByteTrack 构造了一个场景，记为 S4：A 在 f0–f4 有人脸姿态，B 只有姿态、f4 确认，f5 出现一帧 spawn X。
       - TASK-102 第 2 轮的做法（provisional 胜出时完全不修剪）会让 f6–f8 输出 A/`tracked_only`。
       - 没有 X 时，同一输入输出 B/`tracked_only`。
       - 按本规则，有无 X 结果一致。
6. `HeadPerception` 的 `provisional`（TASK-102 引入）在选择过程中原样保留。选择的三步不区分 provisional 与已确认，只按规范 §4.4 的距离、身份与原优先级规则。

### 非目标

- 不改资格判定、in/out 阈值、保守门控（决策 D10）。
- 不做主体长期身份稳定或躯干优先跟踪（决策 D11）。
- 不改 `FaceLandmarkerOptions.num_faces`（决策 D9）。
- 不改跟踪参数与桥接参数（决策 D5）。
- 不新增 CLI 选项；不改 `run_config.json` 键集合。

### 依据材料

- 规范：§1.2、§4、§6、§7、§8、§9。
- 代码：`gazelle/runtime/perception/fusion.py`（全文）、`gazelle/runtime/perception/mediapipe_backend.py:64-121`、`:279-443`、`gazelle/runtime/perception/provider.py:16-232`、`gazelle/runtime/perception/gaze_policy.py:64-89`、`gazelle/runtime/perception/contracts.py`。
- 受影响测试：`tests/test_head_fusion.py`（`associate_face_pose` 与 `fuse_head_candidates` 用例需补姿态关键点；`test_one_person_selection_is_deterministic`；`test_inconsistent_face_pose_selects_higher_quality`）；`tests/test_mediapipe_backend.py`（检测截断与 `num_poses`）；`tests/test_mediapipe_head_provider.py`（`test_single_person_post_bridge_arbitration_prunes_stale_identity`、图像编号）；`tests/test_gaze_policy.py`（仲裁用例）。
- 基线数据：`C:\Users\yun\Documents\Claude_Code\_handoff_archive\smoke-20261014\`。

### 不可变约束

- AGENTS.md 的 Runtime Invariants 与 Research And Data Integrity 全部保持。
- 送入 `GazellePredictor` 的头框仍为规范化、有限、裁剪后非空，并与 `person_id` 顺序对齐。
- `gaze_eligible` 仍是保守建议，`gazelle_selected` 仍记录实际调度。
- 默认测试隔离规则不变。

### 允许动作

- 修改：上面“依据材料”列出的四个代码文件与 `contracts.py`、对应测试、`tests/test_usage_docs.py`、四份用户文档的相关段落。
- 按协作方案 §4 在阶段分支提交并推送。
- 运行离线验证与下方真实 smoke（仅缓存资源，输出写到仓库外）。可只读使用作业数据补充真实 smoke：TASK-131 合入后，用 FFmpeg 流复制从 MP4 分段或 TASK-134 的代理视频截取 15 秒片段到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\` 再运行，不写入 `E:\Gazelle_Workdata\`。sample1 只作冒烟输入；sample2 不属于目标场景，不再使用。运行任何 GPU 推理前按协作方案 §5 检查空闲显存。

### 禁止

新建分支或 PR、合并、force push；修改 Conda 环境；下载；修改上面未列出的文件；写入或修改用户独立目录或 `E:\Gazelle_Workdata\` 中的任何文件。

### 验收标准

1. 合成场景：A、B 两人相邻，最高置信的人脸属于 A、最高置信的姿态属于 B。输出中不存在横跨两人的融合框；A 的姿态存在时与 A 的脸融合。
2. 锚点测试四个分支各有用例：鼻点在内与在外、两个头部关键点、只有双肩、没有可用关键点。
3. 连续选择：
   - 两个候选置信度逐帧交替领先时，单人模式输出始终是同一人。
   - 同一物理位置出现新的 tracker 身份时，新观测取代旧身份的 `tracked_only`。
   - 主体被遮挡时保持为 `tracked_only`，直到桥接过期才切换。
   - 契约 r2 新增两个用例，均用真实 trackers 2.6.1 的 ByteTrack，或复刻其语义的 fake：
     - **GZ-30 场景**：P0 在 f0–f4 可见、f5–f8 漏检，f5 在远离 P0 的位置出现一帧 spawn。单人模式下 f5–f8 输出 P0/`tracked_only`：f5 由第 2 步的身份连续选中 P0；f6–f8 桥接未被删除。
     - **一帧 spawn 不删桥接**：P0 在 f5 漏检，同一位置在 f5 出现 provisional 新身份，f6 起又被关联回 P0。f5 可以输出 provisional 头，f6 起恢复为 P0，期间 P0 的桥接始终存在。若新身份在 f6 确认，则 f6 起输出新身份，P0 的桥接在 f6 被删除。
     - **S4，临时头中立**：A 在 f0–f4 有人脸姿态，B 只有姿态、f3–f5 可见并在 f4 确认，f5 出现一帧 spawn X。f6–f8 的输出必须与同一输入去掉 X 时完全相同。
4. 图像模式输出的 `person_id` 从 0 连续编号。
5. backend 用例确认人脸裁剪数量与 `num_poses` 都等于候选池大小。
6. 四份文档说明锚点规则、至少 3 个候选、连续选择规则、视频 ID 不保证从 0 开始；`tests/test_usage_docs.py` 锁定对应 token。
7. 完整离线门通过，无失败，无新增 skip。
8. 真实 smoke（Sunny 30 帧视频，video A 与 video B 参数；外加 `assets/the_office.png`）：
   - 契约 r2 澄清输入与对照：
     - Sunny 统一使用 2026-10-14 基线所用的转码 `C:\Users\yun\Documents\Claude_Code\_handoff_archive\smoke-20261014\media\sunny.mp4`（1,249,455 B，SHA-256 前缀 `1521746f`）的前 30 帧，只读使用。TASK-102 另行生成的转码与它在第 15 帧附近的检出不同，见 TASK-002 §3。
     - “修改前”是本任务开始时的 HEAD，即已含 TASK-102，在同一环境、同一输入上运行。
     - 另报告与 2026-10-14 基线的差异。
   - 姿态鼻点落在人脸派生头框之外的 `face_pose` 感知数为 0。
   - 报告选中主体切换次数、`gaze_eligible` 帧数、Gazelle 推理次数、in/out 分布，并与 2026-10-14 基线对比。
   - 统计脚本放在仓库外或 `docs/collab/evidence/` 的说明中给出命令，不提交生成的媒体与 JSONL。
   - 作业数据补充：从有第二人入镜的时段截取片段，例如录制 20260925（画面日期显示为 2026-09-22）画面时钟约 03:57 与 04:10 的前方摄像机 B，报告单人模式选中的是否始终是作业者。
     - 用 FFmpeg 流复制从源 MP4 截取 15 秒，按原帧率处理，不用 5 Hz 代理；输出写到仓库外。
     - 报告中不放图像，不写人名。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-101-pycache"
& $py -m unittest tests.test_head_fusion tests.test_mediapipe_backend tests.test_mediapipe_head_provider tests.test_gaze_policy tests.test_video_pipeline tests.test_image_pipeline tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。改变感知融合语义、选择策略与核心算法。
- 需真实 smoke：是。
- 文档同步：需要。
- 风险与回退：连续性可能在主体被遮挡时短暂保留旧主体；多人入镜时选中的人可能与旧版本不同。回退方式是 `git revert` 本任务的提交。
- 依赖：TASK-102 已审查通过。

## 2. 实施报告（Codex 追加，不要修改上文）

### 第 8 轮实施记录（Codex，2026-10-31）

- 接手基准 `476ebdfd6d04d2b97da91370fbf85dd55a00096b`；当前分支与 PR #6 延续，主线程 Inline Execution，无子代理。已读契约 r2 与设计 §1.2、§4、§6–9；不改研究阈值、跟踪配置、CLI 或 run_config 键。
- 实现：共享 `candidate_pool_size`，人脸裁剪与姿态池至少 3；鼻点→头部关键点→双肩的优先级锚点门；所有模式统一配对后截断；视频依空间连续、身份连续、原优先级选择并保留原输出顺序；桥接修剪使用独立的非 provisional 选择；图片选择后重新编号。改变 5 个许可代码文件、5 个对应测试及四份用户文档。
- 离线：先加锚点/跨人匹配/连续选择回归，旧实现 44 tests 中 7 failures、3 errors（不支持新参数）；修正后专项 73 tests 通过。完整 `python -m compileall main.py gazelle tests tools`、`python -m unittest discover -s tests -v`（**729 tests / 26.350s / 0 skip**）、`python main.py --help`、`python main.py --list-models`、两个 Node harness、`python -m tools.docs build/check`、`git diff --check` 均 exit 0。文档专项 23 tests 通过。执行使用 `Gazelle-next` 与仓库外 pycache；日志在 `gazelle_runs/codex-round8/task101-*`。无效临时 MP4 的 `moov atom not found` 属既有非致命输出。
- 反证复核：仓库外 `task101-negative.py` 从 `git show 476ebdf:<文件>` 只在一次性进程加载旧函数。新锚点/匹配用例拒绝旧 fusion；保留新候选池调用，仅换回旧 `_assign_people` 时，S4 与图片编号用例均失败，证明不会只靠候选池断言掩盖桥接问题。进程退出，仓库文件不变。
- 真实运行：`task101-smoke.py before` 与 `after` 调用 `task-136/smoke.py cli <repo> ...` 的缓存/网络审计包装。Sunny 使用指定文件（1,249,455 B，SHA-256 `1521746f8392e10ce01a5c6ee13784d35fecdaca5d12e4607af55895681d10b2`），前 30 帧。A：`--max-heads 1 --video-codec avc1`、默认 eligible；B：`--max-heads 2 --video-codec mp4v --gazelle-head-mode all --gaze-render-mode all-predictions --head-box --face-box`。两者另带 `--head-source mediapipe --device cuda --save-rendered --face-pose-ray --pose-head-ray`。office 使用 B 的选择/渲染参数、无视频选项；2026-10-14 图片对照用 max_heads=3，本次为 2，均实际输出 2 个头，故不把该差异归因于算法。

| 对照 | 鼻点在 face-derived 头框外的 face_pose（其中选中推理） | eligible 帧 | 推理调用 / 头数 | valid / out_of_frame | 主体集合变化 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-14 A | 14（12） | 14 | 14 / 14 | 3 / 11 | 7 |
| 本任务开始 A | 14（12） | 15 | 15 / 15 | 4 / 11 | 9 |
| 修改后 A | 0（0） | 17 | 17 / 17 | 6 / 11 | 1 |
| 2026-10-14 B | 2（2） | 17 | 29 / 57 | 36 / 21 | 1 |
| 本任务开始 B | 2（2） | 17 | 30 / 59 | 38 / 21 | 1 |
| 修改后 B | 0（0） | 17 | 30 / 59 | 38 / 21 | 1 |
| office 开始 / 修改后 | 0 / 0 | 0 / 0 | 各 1 / 2 | 各 2 / 0 | 不适用 |

- Sunny 主体按面部框所在左右区域核对，集合变化不把两人输出顺序互换计为主体切换；ID 集合的变化数也相同。A 在初始阶段仍切换一次，此后稳定，不宣称长期身份锁定。各组完整 in/out min/median/max、逐帧框和 ID 在 `task101-summary.json`；开始/修改后 run_config 的键集合相同。office 渲染目视未见跨人融合框，但仍存在 MediaPipe 误检，不能把本项视作检测精度验收。
- 真实环境：Python 3.14.8、torch 2.14.1+cu130、torchvision 0.29.1+cu130、MediaPipe 1.1.1、trackers 2.6.1、supervision 0.30.9、NumPy 2.5.4、OpenCV 5.0.0.93；RTX 4080 SUPER，运行前约 4.75/16.38 GB 占用，无外部训练进程。每次 CUDA 启动再次检查。复用已有 Gazelle/DINOv2/MediaPipe 缓存；Sunny/office 前后缓存文件大小/mtime 清单无变化。Python 审计阻止了每次 Torch Hub 的一次 `urllib.Request`，无下载；MediaPipe native 遥测未由 Python 审计覆盖，不声称对其网络做了完整抓包。实际 FFmpeg：A 的 H.264 finalization，及下述源 MP4 流复制；其余渲染使用 mp4v。无依赖安装、Conda 或全局配置修改。
- 作业数据补充：第一次按拟合目标 PTS 1136.010265 截取 03:57 的 15 秒，FFmpeg stream-copy 含关键帧前导包，容器 426、实际解码 376 帧；运行时完整性检查正确 exit 1。保留失败日志及输出。源关键帧核对后改用 1136.019，仍流复制且保留原分辨率/帧率，ffprobe 两种计数均 376；运行完成 376/376、exit 0。04:10 附近改用源关键帧 1915.980，也完整通过，详见下表后补充结果。所有源视频只读，剪辑/运行/目视图留在仓库外；不放图像到 Git。
- 自主决定（A 级）：旧几何门测试补明确的姿态锚点，保持其 IoU/距离边界；新合成例不要求两个合法扩展头框绝不重叠，而是检查各自宽度和姿态来源，避免错误的测试前提。流复制输入改为精确关键帧截取，运行时完整性标准不变。
- 范围外改动：无仓库范围外代码改动；分析脚本与产物只在授权的仓库外运行目录。
- 待 Claude 判断（B 级）：暂无设计阻塞；独立算法/真实运行验收待 Claude，用户独立 checkout 未验收。
- 待用户决定（C 级）：无。

#### 补充运行完成与提交

- 两段关键帧对齐剪辑均完整通过：03:57 为 15.041 秒、约 25 fps；04:10 附近为 15.040 秒、25 fps；均原生 3840×2160、视频流复制、无音频。两次运行各 376 帧读取/输出，`decode_complete=true`，exit 0，耗时 160.20 / 160.42 秒。
- 03:57：330 face_pose、25 pose_only、21 face_only；274 eligible/推理帧，valid 2、out_of_frame 272；nose-outside 为 0。04:10：297 face_pose、78 pose_only、1 face_only；197 eligible/推理帧，valid 28、out_of_frame 169；nose-outside 为 0。
- 主体核对：逐帧记录中两段各有一个头；额外目视每秒帧及所有 ID 变化的前后帧，共 23 / 46 张，所选均为工位作业者，03:57 的旁人未被选中。第二段人物在画面内移动较多，未见换成旁人；这是抽查与连续轨迹证据，不是 752 帧逐帧人工验收。公开 ID 仍有 4 / 18 次变化，符合“物理主体连续，不承诺长期身份”的边界。图像证据留在本机，不入 Git。
- 脚本失败项：首次统计在视频尚未完成写盘时发现 JSONL 行数不齐，未采用部分统计；等待完成后再统计。目视脚本按帧号随机定位第二段末帧失败，改用顺序解码，完整读取 376 帧并只保留抽查图；未改数据或运行时标准。首次失败剪辑与其日志保留，关键帧修正的新剪辑和新输出使用独立文件名。
- 实现提交 **`569394b30fdbe2e586332e89c02e27483b9c59a9` — `Match face and pose anchors and preserve selected subject continuity`** 已推送；报告另行提交。状态 **ready-for-review / Codex verified**。完整命令、资源活动和统计见仓库外 `task101-before-commands.json`、`task101-after-commands.json`、`task101-workdata-keyframe-commands.json`、`task101-gate.json` 与 `task101-summary.json`。测试进程均已结束，无后台推理遗留。

### 第 9 轮实施记录（Codex，2026-10-31；契约 r3）

- 实现提交 **`d31b41d3f7cae7a1fa387286161a9dc1aa3d6cdd` — `Preserve selected identities across occlusion and provisional heads`** 已推送。状态为 **ready-for-review / Codex verified**，尚待 Claude 独立审查与用户独立 checkout 验收。沿用原分支与 draft PR #6，主线程 Inline Execution，无子代理。
- 选择先保留所有仍被观测的同身份，再做空间连续；曾同时被观测的轨迹不能互相接替。provider 记录包括 provisional 在内的共存对，在任一 ID 离开感知列表时清除，两次裁决均传入；记忆使用已确认的选择，只在其为空时回退正式输出。桥接保留规则未改，CLI 与 run_config 键未改。四份用户文档和文档检查同步。
- 回归先失败：10 failures 复现缺陷；修复后覆盖可见旁人、胜出的一帧 spawn、主体回来、多人顺序、共存删除、空帧、启动时全部 provisional，以及距离闭边界和 y 分量。带种子的真实 ByteTrack 测试核实 200 个实际 provisional spawn，从下一帧起输出与保留集合中立，并断言执行少于 5 秒。补齐耳部、单肩、y 锚点与几何门覆盖。
- 离线命令（解释器均为既有 `Gazelle-next`，pycache 在仓库外）：`python -m compileall main.py gazelle tests tools`；`python -m unittest discover -s tests -v`：**757 tests / 66.647s / 0 skip**；`python main.py --help`；`python main.py --list-models`；`node tests/annotation_page_test.cjs`；`node tests/roi_page_test.cjs`；`python -m tools.docs build`、`check`；`git diff --check`，全部 exit 0。外部包装 `gazelle_runs/codex-round9/run-gate.ps1 -Tag task101-final` 保存逐条命令、退出码与日志。无效临时 MP4 的 `moov atom not found` 与 Git 行尾提示为非致命输出。
- 反证：外部 `task101-mutations.py` 在隔离进程内替换函数，**25/25 变异被检测**，正常对照 66 tests 通过；其中 A12 缺失单肩保护导致 2 个 AttributeError，其余 24 个由断言检测，不能称为全部断言失败。旧变异结果与失败日志保留；仓库源码未被变异改写。
- 真实命令：`python ../gazelle_runs/codex-round9/task101-smoke.py` 依次调用既有 `task-136/smoke.py cli <repo> ...`。Sunny A/B、office 和两段关键帧剪辑沿用第 8 轮指定输入与参数，完整 argv、输入 SHA、耗时、代码 SHA 在 `task101-smoke-commands.json`。均 exit 0；Sunny 各 30 帧，office 1 帧，作业剪辑各 376 帧且读取/输出一致。没有再次裁剪源视频。

| 本轮输入 | face_pose 分母 / 错误鼻点 | eligible 帧 | 推理调用 / 头数 | valid / out_of_frame | ID 集合变化 | in/out min / median / max |
| --- | --- | --- | --- | --- | --- | --- |
| Sunny A | 19 / 0 | 1 | 1 / 1 | 0 / 1 | 0 | 0.3984 / 0.3984 / 0.3984 |
| Sunny B | 19 / 0 | 17 | 30 / 59 | 38 / 21 | 1 | 0.0160 / 0.9162 / 0.9894 |
| office | 1 / 0 | 0 | 1 / 2 | 2 / 0 | 0 | 0.8517 / 0.8995 / 0.9473 |
| 03:57 | 261 / 0 | 223 | 223 / 223 | 1 / 222 | 6 | 0.0047 / 0.0310 / 0.5316 |
| 04:10 | 298 / 0 | 198 | 198 / 198 | 28 / 170 | 14 | 0.0001 / 0.0652 / 0.9860 |

- Sunny A 30 帧全为 ID 0，f2 至 f4 为 tracked_only，符合 r3 预期；eligible 从第 8 轮的 17 降为 1，是保留原主体后的实际结果，没有调整阈值。B 与第 8 轮统计相同。所有真实 face_pose 都走鼻点分支，其余锚点仅有合成覆盖。第 8 轮 A 的 0 错误实际分母为 0；B 为 19、两段作业合计 627；本轮各分母见表，不能将零分母作为融合正确证据。完整历史/本轮重算见 `task101-summary.json`。
- 目视抽查：顺序解码，抽每秒帧及全部 ID 变化相邻帧，03:57 为 **24 张**，04:10 为 **38 张**。选中的均为工位作业者，第一段右侧旁人未被选中；遮挡阶段有窄框/滞留框，ID 仍有变化，不承诺长期身份或逐帧检测精度。这是 62 张抽查，不是 752 帧逐帧人工验收。office 既有误检未解决。图像仅在本机 `codex-round9/task101-*-review-*.jpg`，不上传。
- 实际活动：缓存 Gazelle/DINOv2、MediaPipe、CUDA 与真实 FFmpeg（A 的 H.264 finalization）。每个推理子进程先检查显存；启动前 RTX 4080 SUPER 为 5239/16376 MiB、2% 利用率。前后缓存文件大小/mtime 清单相同。包装阻止每次 Torch Hub 的 Python urllib 探测，无下载；接受既有 MediaPipe native 遥测授权，未抓包，不能称为完全无网络。未安装依赖、修改 Conda/全局配置或读取用户正式标签。测试/推理进程已结束。
- 自主决定（A 级）：新共存测试先确认 A 再引入 provisional B，纠正“首帧临时 A 已进入桥接”的错误夹具假设；修正变异包装以把明确的生产异常计为检测，并补上此前存活的启动记忆变异用例。生产契约与研究门槛不变。
- 范围外改动：无；外部脚本与真实产物留在指定运行目录。
- 待 Claude 判断（B 级）：算法、抽查与真实统计待独立审查；没有未解决的 r3 预期差异。
- 待用户决定（C 级）：TASK-101 无新增事项。

## 3. 审查结论（Claude 追加）

### 2026-10-31 第 8 轮审查（Claude）

- **审查目标**：`569394b`（实现）、`aa13179`（报告），在 HEAD `299bf0f` 上审查，这些生产文件此后没有改动。完整记录见[第 8 轮审查记录](../evidence/2026-10-31-round8-review.md) §4。
- **结论**：**changes-requested**。字面规则大多实现了，人脸与姿态的跨人融合已修好，但契约 r2 写明的后果不成立，验收 3 在契约自己的 Sunny 片段上也不成立。
- **已验证通过**：候选池、锚点规则、统一匹配、图像编号、不加 CLI 选项、`run_config` 键集合不变。只读子代理按原始 JSONL 重算全部统计，与 §2 的表逐格一致；Claude 复现了下面的发现 1。
- **发现**：
  1. **必须修复：临时头胜出后，下一帧丢失主体。**
     - 位置：`gazelle/runtime/perception/provider.py:189` 把含临时头的选择记入 `_previous_selection`。
     - 真实 ByteTrack 复现：A 从 f5 漏检，已确认的旁人 B 一直可见，一帧 spawn X 在 A 的一个对角线内。没有 X 时 f5 至 f11 都是 A/`tracked_only`；有 X 时 f5 输出 X，f6 起输出 B，A 的桥接在 f6 被删，A 回来后也选不回来。
     - 3539 个真实一帧 spawn 的模糊测试：胜出的 170 个中 56 个不中立。这违反契约 r2 的“一帧 spawn 无论是否胜出，都不改变哪些桥接被保留”，四份文档中的“中立”也因此不实。S4 原几何（B 只到 f5）碰不到这个情况，所以测试通过。
  2. **必须修复：共存过的旁人会抢走主体。**
     - 规范第 1 步让一个对角线内的任何观测取代主体，包括一直与主体同时可见的旁人。
     - Sunny A 的 f2：ID 0 漏检，ID 1 距离 0.255，小于对角线 0.430，立即换人且不再回来。§2 的“切换 1 次”就是这次，验收 3 的“主体被遮挡时保持为 `tracked_only`，直到桥接过期才切换”不成立。
  3. **应修：结果依赖上一帧的顺序，仍被观测的主体也可能输给更近的旁人。** 第 1 步是顺序贪心，没有同身份优先。`max_heads=2` 时同样的画面，上一帧顺序是 (A,B) 得 {B,C} 并删掉 A 的桥接，是 (B,A) 得 {B,A}；而输出顺序本来逐帧翻转。
  4. **应修（测试）**：没有 provider 级用例覆盖“主体在桥接中、已确认的旁人可见”。58 个变异中 43 个被捕获。真实缺口：`left_ear`、`right_ear` 不算锚点，单肩，`y` 上边界，距离上限（严格、加倍、减半、长边代替对角线、忽略 `y`），中立选择不传 `previous_selection`，`_previous_selection` 记什么，空帧的处理。S9、S12 等价，S11 经 provider 不可达。
  5. **小项（文档与报告）**：`README.md:231`、`README_CN.md:237` 仍只说单人修剪。§2 表中修改后 A 的 0（0）分母为 0：这次运行没有 `face_pose` 行，实证来自 B 的 19 行与作业数据 627 行，全部走鼻点分支，其余锚点分支只有合成验证。
- **A 级决定**：三项都同意（旧几何测试补锚点、不要求两个合法头框绝不重叠、流复制按关键帧截取）。`test_association_rejects_boxes_outside_both_gates` 现在由锚点先拒绝，名字与内容不符，第 9 轮顺手改名或补锚点。
- **没有检查**：作业数据中选中的是否始终是作业者（这次没有看图像；Codex 目视 69 张）；真实模型没有重跑。

### 契约修订 r3（Claude，2026-10-31；第 9 轮执行）

规范已改为 [PERCEPTION 1.2.0 §4.4](../../design/PERCEPTION_D1_D2_DESIGN.md)。本修订优先于上文中与之冲突的条款。

1. **选择**：`arbitrate_perceptions(perceptions, *, max_heads, previous_selection=(), coexisted=frozenset())`，步骤按 §4.4：同身份优先、空间连续（排除共存过的轨迹）、身份连续、按原优先级补足，返回保持原顺序。
2. **provider**：
   - 每帧把同时被观测的 `person_id` 两两记入 `coexisted`，含临时头；任一 ID 离开感知列表时删除这一对；与 `_previous_selection` 一起重置。
   - 两次选择都传入 `previous_selection` 与 `coexisted`。
   - `_previous_selection` 记已确认的选择；已确认的选择为空时记正式选择。
   - `retain_person_ids` 与正式输出的规则不变。
3. **测试**（默认隔离，可用真实 trackers 2.6.1 的 ByteTrack，或复刻其语义的 fake）。下表的结果 Claude 已在副本上用候选实现跑通，脚本在仓库外 `gazelle_runs\claude-review-r8\reviewers\task101\scripts\`（`harness.py`、`s1_neutrality.py`、`s2_fuzz.py`、`s3_scenarios.py`、`s5_order.py`；`make_rule3_copy.py` 是参考实现，不要求照抄）。

   | 场景 | 必须的结果 |
   | --- | --- |
   | A 从 f5 漏检，已确认的 B 一直可见，X 在 f5 一帧且在 A 的一个对角线内 | f5 可以输出 X；f6 起与没有 X 时完全相同：A/`tracked_only`，A 的桥接保留 |
   | 同上，A 在 f7 回来 | f7 起输出 A |
   | 相邻的 A、B（一个对角线内）同时可见过，A 漏检 3 帧 | 这 3 帧 A/`tracked_only`，之后 A，B 不抢占 |
   | 新身份 N 在 A 的位置出现，且从未与 A 同时被观测 | N 取代 A 的 `tracked_only`；A 的桥接在 N 确认的那一帧删除（验收 3 第 2 项不变） |
   | `max_heads=2`，A 漏检，B 紧邻，C 远 | 上一帧顺序为 (A,B) 或 (B,A) 时结果相同：{B, A/`tracked_only`}，A 的桥接保留 |
   | 主体 A 仍被观测，更近处有旁人 | 仍选 A |
   | 多人时置信度逐帧交替 | 始终是同一人（验收 3 第 1 项不变） |
   | 真实 ByteTrack 的带种子的中立性模糊测试，不少于 200 个场景，5 秒以内 | 去掉一帧 spawn 前后，从 spawn 的下一帧起输出与保留集合完全相同 |

   - `test_s4_spawn_is_neutral_to_bridge_retention` 的基线要改：B 在 f3、f4 与 A 同时可见，不能接替 A，所以没有 X 时 f5 至 f8 是 A，不再是 B。中立性的断言不变。
   - 补上发现 4 列出的缺口，让这些变异失败。距离上限用恰好等于对角线、略大于对角线、只有 `y` 方向差距三个用例。
4. **文档**：四份用户文档写明选择规则的变化（同身份优先、同时可见过的人不能接替主体），改正发现 5 的单人修剪说法；`tests/test_usage_docs.py` 相应更新。CLI 与 `run_config` 键集合不变。
5. **真实运行**（与契约 r2 第 8 条相同的输入与参数，只用缓存资源，运行前检查显存）：
   - Sunny A、B，`the_office.png`，以及 §2 的两段关键帧对齐作业片段。
   - 报告项不变，另写明 `face_pose` 的分母。
   - Sunny A 的预期：Claude 用修改后 B 的逐帧行回放候选规则，30 帧都是同一人，f2 至 f4 为 `tracked_only`，切换 0 次。实测不同时按 B 级报告，不调整规则去迎合。
   - 作业片段继续用目视抽查确认选中的是工位作业者，抽查帧数写入报告；图像只留本机。
6. **完整离线门**，无新增 skip。实现与报告分开提交，PR #6 发双语评论。

### 2026-10-31 第 9 轮审查（Claude）

- **审查目标**：`d31b41d`（实现）、`a692e5a`（报告），在 HEAD `5690745` 上审查。完整记录见[第 9 轮审查记录](../evidence/2026-10-31-round9-review.md) §2。
- **结论**：**changes-requested**。实现与契约 r3 的文字一致，第 8 轮的四项发现都修好了。退回的原因是 r3 的规则本身有缺陷，规则是协调者写的，不是实现错误。
- **已验证通过**：场景表 8 行用真实 ByteTrack 复现；§2 的表逐格与原始 JSONL 一致；7 个测试在 `569394b` 上断言失败，另 2 个在旧代码上也通过；CLI 与 `run_config` 键集合不变；144,000 个模糊场景中，无候选池截断、spawn 帧有已确认感知时，严格的一帧 spawn 失败 0 个（至少 91,368 个）。
- **发现**（只读子代理报告，发现 1、2、3 Claude 另外复现）：
  1. **必须修复：共存关系保留得太短。** 未选中的旁人没有桥接，漏检一帧就离开感知列表，这一对随即被删，随后可以抢走主体。真实 ByteTrack 复现：A 漏检 3 帧、B 每帧漏检概率 5% 时，13.7% 的试验到片尾（A 回来 6 帧后）仍未回到 A。四份文档的“cannot replace each other”不成立。
  2. **必须修复：“同时被观测的两条轨迹是两个人”在作业视频上看来不成立（推断）。** 03:57 的 eligible 帧由 274 降到 223，`tracked_only` 由 0 升到 60。ID 1 与 ID 4 同帧 IoU 0.299–0.483，推断是同一个头的两个候选。§2 写“没有未解决的 r3 预期差异”，没有报告这个下降；今后与上一轮的逐项差异要写入报告，包括下降的项。
  3. **必须修复：没有已确认感知的帧上中立性不成立。** 这时还没有已建立的主体，所以修正的是承诺，不是规则。四份文档的“neutral to bridge pruning”要改。
  4. **应修：候选池已满时，一帧 spawn 不必胜出也能造成主体丢失。** 发现 1 的修正消除 `t3b_pool` 这个场景，但含 spawn 的候选数超过池上限时，仍有约 4.5% 的 spawn 不中立，少数到片尾换了主体。承诺要排除这种情况，并加带池截断的用例。
  5. **应修（测试）**：5 秒的时间断言把导入时间算在内，高负载下不稳，注释也不实；三个真实 tracker 用例缺可选包保护；真实缺口变异 N8、N11、N14、N16、N20、N24 存活。
  6. **小项**：第 2 步仍依赖上一帧顺序（`max_heads=2`，两人都漏检，只有一个新人）。
- **A 级决定**：同意。
- **没有检查**：真实模型没有重跑，图像没有看；未选中的轨迹不在 JSONL 中，真实旁人漏检率未知。

### 契约修订 r4（Claude，2026-10-31；第 9 轮继续）

规范已改为 [PERCEPTION 1.3.0 §4.4](../../design/PERCEPTION_D1_D2_DESIGN.md)。本修订优先于上文中与之冲突的条款。下面的规则 Claude 已在副本上跑通，参考实现在仓库外 `gazelle_runs\claude-review-r9\candidate-r4\make_copy.py`，不要求照抄。

1. **共存的记录**：同一帧两个观测的头框 IoU 小于 0.05 才记入 `coexisted`，等于或大于 0.05 不记。阈值写成 `provider.py` 的命名常量，复用 `fusion` 的 IoU 计算，不写第二份。阈值是看过 03:57、04:10 与 Sunny 之后定的。代价：两个真人的框 IoU 达到 0.05 时可以互相接替。
2. **共存的保留**：一对保留到其中一个 ID 缺席（不在感知列表）超过桥接窗口才删除，以 `timestamp_ms` 计。窗口跟随实际使用的 bridge，取它的公开属性，不读私有属性；现有测试注入 `max_gap_ms=10` 的 bridge，要照样成立。集合大小要有界。
3. **第 2 步**：把未满足的上一帧项与未选中的观测，按头框中心距从小到大全局配对，一个观测只配一项。相同时按原优先级，再按 `person_id` 与索引。结果不依赖上一帧的顺序。
4. **承诺**：一帧 spawn 的中立性限定为 spawn 帧至少有一个已确认感知，且含这个 spawn 在内的候选数没有超过候选池上限。四份用户文档的两句相应改写：`neutral to bridge pruning` 写明这两个条件；`cannot replace each other` 改成明显分开的两个头框才算两个人。新句子不要写成绝对保证。`tests/test_usage_docs.py` 同步。
5. **测试**：

   | 场景 | 必须的结果 |
   | --- | --- |
   | A 漏检期间，不重叠的旁人 B 闪一帧 | 一直是 A/`tracked_only`，A 回来后仍是 A，桥接保留 |
   | B 在 A 首次漏检的前一帧闪一帧 | 同上 |
   | `max_heads=2`，未选中的 C 在 A 漏检时闪一帧 | C 不占 A 的名额 |
   | 同帧两框 IoU ≥ 0.05 的两条轨迹，旧轨迹消失或只断续出现 | 重叠的轨迹当帧接替，不等桥接过期 |
   | IoU 恰为 0.05、略小于 0.05 | 前者不记入，后者记入 |
   | 主体 ID 大于旁人 ID；候选顺序与 ID 顺序相反 | 旁人不接替 |
   | 一个 ID 缺席，窗口内回来；缺席超过窗口 | 前者这一对保留，后者删除 |
   | `max_heads=2`，A、B 都漏检，只有一个新人 | 上一帧顺序为 (A,B) 或 (B,A) 时结果相同 |
   | 含 X 的候选数超过池上限，X 把 B 挤出候选池（带真实截断），B 与 A 的框不重叠 | B 不接替 A |

   - `test_coexistence_includes_provisional_and_drops_disappeared_ids` 与 `test_s4_spawn_is_neutral_to_bridge_retention` 的两个框重叠（IoU 0.11、0.33），改成不重叠的框，原有预期不变。
   - 真实缺口变异 N11、N16、N20、N24 要失败。N8、N14 针对 r3 的逐项贪心，全局配对后原文不再适用：N8 改为“配对不排序，按上一帧顺序处理”，N14 改为“处理完第一个未满足项后不再按 `coexisted` 过滤”，这两个改写也要失败。定义在 `gazelle_runs\claude-review-r9\reviewers\task101\scripts\mutate_r9.py`，代码移动时按原义改写。
   - `test_seeded_real_bytetrack_spawn_neutrality` 先真正加载 tracker 后端再计时，预算改成 20 秒，只防止失控。三个真实 tracker 用例加可选包保护，写法同 `tests/test_head_tracking.py`。模糊测试的中立性断言只在第 4 条的条件下要求。
6. **真实运行**（与契约 r2 第 8 条相同的输入与参数，只用缓存资源，运行前检查显存）：
   - Sunny A、B，`the_office.png`，以及两段关键帧对齐作业片段。报告项同 r3 第 5 条。
   - 与上一轮逐项比较并写入报告，包括下降的项。
   - 预期（回放，部分重建，不是真实运行）：03:57 eligible 274、`tracked_only` 0；Sunny A 30 帧同一 ID，f2 至 f4 为 `tracked_only`。04:10 回放的 12 帧 `tracked_only` 全在 f261–272，未改代码的回放在这里已与实际不符（第 8、9 轮实际都是 ID 10/`face_pose`），不作为预期；真实运行预期第 9 轮的 f46、f55、f56 不再是 `tracked_only`，其余以实测为准。实测不同时按 B 级报告，不调整规则或阈值去迎合。
   - 定阈值用的就是这三段，真实 smoke 只能证明实现与回放一致，不是留出检验。
   - 作业片段继续目视抽查选中的是工位作业者，图像只留本机。
7. **完整离线门**，无新增 skip。实现与报告分开提交，PR #6 发双语评论。

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
