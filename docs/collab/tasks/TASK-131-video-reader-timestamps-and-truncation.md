# TASK-131：视频读取器的容器时间戳、严格递增与截断检测（GZ-07、GZ-21）

状态：ready
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
依据：[作业数据分析](../analysis/2026-10-15-workdata-analysis.md) §3.1、§3.2；问题登记表 GZ-07（升为 P0）与 GZ-21（新增）。
决策：D4（时间戳时钟）按 Claude 的建议实施，用户 2026-10-15 批准。
授权：2026-10-14 本地修改与本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

让运行时在可变帧率 MP4 上不中止，保留容器给出的真实时间戳；解码提前停止时不再报告成功。

### 背景（已实际运行的事实）

- 作业数据的 29 个 MP4 分段中有 12 个在下标 2 中止。OpenCV 对下标 0 与 1 都返回 `POS_MSEC = 0`；`VideoFrameReader` 把下标 1 改为 `1000 / fps`（50 或 40 ms），而下标 2 的真实值只有 18 到 35 ms；`mediapipe_backend._video_timestamp` 拒绝取整后不递增的值。
- 原始 AVI 只能解出 1 帧，而 `CAP_PROP_FRAME_COUNT` 为 108219；`run_video_pipeline` 以 `frames_read = 1` 正常完成。

### 必须实现

1. `gazelle/runtime/media.py` 中 `VideoFrameReader.__iter__` 的时间戳规则：
   - R1：输出的 `timestamp_ms` 有限、非负，按整数毫秒取整（`int(round(x))`）后严格递增。
   - R2：`POS_MSEC` 有限、非负且取整后大于上一帧时，原样使用，保留可变帧率的真实间隔。
   - R3：个别不递增的值（包括下标 1 重复的 0）用满足 R1 的最小增量修补，且不推后之后的正常值。
   - R4：`POS_MSEC` 缺失时按上一帧加一个标称帧间隔估计，同样满足 R1。
   - R5：每帧记录时间戳来源，取值为 `container`、`repaired`、`fps_fallback` 之一。`VideoFrame` 新增带默认值的字段，现有构造方式保持兼容。
   - 逐帧算法（r2，2026-10-15 写明，供实现与测试直接对照）。记 `raw` 为该帧的 `POS_MSEC`，`p` 为上一帧输出值取整后的整数毫秒，`fps` 为 `resolve_video_fps(metadata.fps)`：
     1. 第一帧：`raw` 有限且非负时输出 `raw`（`container`），否则输出 `0.0`（`fps_fallback`）。
     2. 之后各帧：`raw` 有限、非负且 `int(round(raw)) > p` 时输出 `raw`（`container`）。
     3. 否则，若 `raw` 有限、非负，且不属于“下标不小于 2 而 `raw` 为 0”，输出 `p + 1`（`repaired`）。
     4. 其余情况（非有限、负数，或下标不小于 2 而 `raw` 为 0）输出 `p + 1000 / fps`（`fps_fallback`）。
   - 单测逐条断言下表。数值单位为毫秒，后缀字母表示来源：`c` 为 `container`，`r` 为 `repaired`，`f` 为 `fps_fallback`。

     | 原始 `POS_MSEC` | fps | 输出 |
     | --- | --- | --- |
     | `[0, 0, 30, 98, 130]` | 20 | `[0 c, 1 r, 30 c, 98 c, 130 c]` |
     | `[500, 480, 520]` | 30 | `[500 c, 501 r, 520 c]` |
     | `[10.2, 10.4]` | 30 | `[10.2 c, 11 r]` |
     | `[0, 0, 0, 0, 0]` | 30 | `[0 c, 1 r, 34.333 f, 67.333 f, 100.333 f]` |
     | `[0, 33.3, NaN, 100]` | 30 | `[0 c, 33.3 c, 66.333 f, 100 c]` |
     | `[-5, 33.3, 66.7]` | 30 | `[0 f, 33.3 c, 66.7 c]` |
     | `[0, 0, 0, 33.3, 66.7]` | 30 | `[0 c, 1 r, 34.333 f, 35 r, 66.7 c]` |

     此前“整段不可用时按 `frame_index * 1000 / fps` 推算”的旧规则由第 4 步取代；对时间戳完全不可用的视频，结果仍是近似恒定帧率的递增序列。
2. `gazelle/runtime/pipeline.py` 的截断检测（r2，2026-10-15 修正。r1 用整段帧数计算容差，`--max-frames` 较小时永远不会报错，由 Codex 接手核对时发现）：
   - `metadata.frame_count` 不可用时不检测，`frames_required` 与 `decode_complete` 记为 `null`。
   - 容差只用于抵消容器帧数的估计误差：`count_tolerance = max(2, ceil(0.005 * frame_count))`。
   - 设置了 `--max-frames` 且 `max_frames <= frame_count - count_tolerance` 时，`frames_required = max_frames`，一帧都不能少；其余情况 `frames_required = frame_count - count_tolerance`。
   - `frames_read < frames_required` 即判为截断：先写出 `run_config.json`（`decode_complete` 为 false），关闭资源，不做 H.264 终结，再抛出明确错误，CLI 以非零码退出。已写出的 JSONL 保留。
   - 错误信息包含已读帧数、要求帧数、容器帧数与输入路径，并提示“文件可能含无法解码的数据包；AVI 空包的处理见 USAGE”。
   - 单测逐条断言下表：

     | 容器帧数 | `--max-frames` | 实际读出 | 结果 |
     | --- | --- | --- | --- |
     | 108219 | 无 | 1 | 截断 |
     | 108219 | 50 | 1 | 截断 |
     | 33600 | 300 | 300 | 正常 |
     | 33600 | 300 | 299 | 截断 |
     | 33600 | 33590 | 33550 | 正常（`max_frames` 接近结尾时使用容差） |
     | 1000 | 无 | 996 | 正常 |
     | 30 | 无 | 1 | 截断 |
     | 30 | 100 | 30 | 正常 |
     | 未知 | 无 | 1 | 不检测 |

3. 视频 `run_config.json` 新增四个键：`container_frame_count`（未知时为 `null`）、`frames_required`（不检测时为 `null`）、`decode_complete`（布尔，不检测时为 `null`）、`timestamp_sources`（三种来源的计数对象）。
4. 四份用户文档：说明时间戳取自容器并做最小修补；解码提前停止即失败及其判定规则；`run_config.json` 的四个新键（更新 USAGE 中的键表与计数）；给出 AVI 空包的无损重封装命令（作业数据分析 §3.1）。`tests/test_usage_docs.py` 锁定四个新键名与重封装命令中的 `noise=drop`。
5. 测试（默认隔离，不读真实视频）：用 fake capture 覆盖第 1 条表格中的全部时间戳用例与第 2 条表格中的全部截断用例；截断时不做 H.264 终结；`run_config.json` 新键；现有 `tests/test_media.py`、`tests/test_video_pipeline.py` 全部通过。

### 非目标

- 不引入新依赖，不安装 PyAV。
- 不改输出视频帧率，`resolve_video_fps` 不变。
- 不实现跳读或起始偏移。
- 不处理 AVI 空包本身（TASK-132 负责重封装）。
- 不改 `predictions.jsonl` 与 `head_observations.jsonl` 的逐帧字段。

### 依据材料

- 分支 `feature/stage2-correctness`，基线为 STATE.md 的 `last_pushed`。
- 代码：`gazelle/runtime/media.py`、`gazelle/runtime/pipeline.py`（`_video_run_config_payload`、主循环）、`gazelle/runtime/perception/mediapipe_backend.py`（`_video_timestamp`，只读参考，不改其拒绝规则）。
- 测试：`tests/test_media.py`、`tests/test_video_pipeline.py`、`tests/test_usage_docs.py`。
- 文档：`docs/USAGE.md` 中 `run_config.json` 的键表。

### 不可变约束

- AGENTS.md 全部运行时不变量。视频保持流式处理；观测、预测与渲染帧数一致。
- MediaPipe 后端的严格递增检查保留；修补在读取器完成。
- 默认测试隔离。

### 允许动作

- 修改上述代码、测试、四份用户文档与 `tests/test_usage_docs.py`。
- 只读读取 `E:\Gazelle_Workdata\` 做下方真实检查；输出写到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-131\`。
- 按协作方案 §4 提交并推送，并在 draft PR 发英中双语评论。

### 禁止

修改其他文件；写入 `E:\Gazelle_Workdata\` 或用户独立目录；新建分支或 PR、合并、force push；修改环境；下载。

### 验收标准

1. 新增与既有单测通过；完整离线门通过，无新增 skip。
2. 真实读取检查（仅 CPU）：对 29 个 MP4 分段各解码前 600 帧，套用 `_video_timestamp` 的取整递增规则，违规为 0；报告每段三种来源的计数。检查脚本放在仓库外，实施报告给出命令。
3. 真实截断检查：对一个原始 AVI（例如 `20260911\20260911_設備カメラ.avi`）以 `--max-frames 50` 运行 CLI，退出码非零，错误信息符合“必须实现”第 2 条；报告报错前是否已构建模型。
4. 真实 smoke（GPU，先按协作方案 §5 检查空闲显存）：对此前会中止的 `20260911\20260911表情解析用カメラ1-1.mp4` 以 `--head-source mediapipe --max-heads 1 --max-frames 300` 运行，退出码 0；`frames_read` 为 300；两份 JSONL 各 300 行；`decode_complete` 为 true；报告 `no_head` 与 `ok` 帧数。不加 `--save-rendered`。
5. 四份用户文档与 `tests/test_usage_docs.py` 同步。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-131-pycache"
& $py -m unittest tests.test_media tests.test_video_pipeline tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。涉及时序语义与输出 schema。
- 需真实 smoke：是，见验收标准第 2 至 4 条。
- 文档同步：需要。
- 风险与回退：修补后的时间戳与真实采集时间可能相差毫秒级；容器估算帧数不准时截断检测可能误报，误报时在实施报告中列出文件与数字，不放宽阈值。回退方式是 `git revert` 本任务的提交。
- 依赖：无。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：`08dd48f`（`Record stage draft PR`）；`c5bd358b0999e736fd8aa399e1a37ef5d7e26c3c`（`Report TASK-131 timestamp contract conflict`），均已核对推送成功。本行与 STATE 释放写入权另作交接记录提交；没有实现提交。
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实检查结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

### 2026-10-16 接手与契约核对报告（Codex，尚未实施）

- **接手基线**：新仓库 `C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle`；`feature/stage2-correctness`；初始 HEAD `42d1e48076178d6db4d837b65267ac20e86f7a39`，工作区干净，`bbec056..HEAD` 无 `.py` 改动。当前记录基线为 `08dd48f`（`Record stage draft PR`）。已读取本任务 r2、作业数据分析 §3.1/§3.2、读取器、管线、MediaPipe 时间戳校验与相关测试；采用当前对话 v1.1，主线程执行，未开启子代理。
- **预检与发布**：仓库、`gazelle_data`、`gazelle_runs`、`gazelle_validation`、`%TEMP%` 的空目录/文件创建与删除均在普通沙盒实测通过，探针已清理；原始数据只读列出 7 个目录。Python `3.11.15`；FFmpeg/ffprobe `2025-03-31-git-35c091f4b7-full_build-www.gyan.dev` 可执行。GPU 查询为 RTX 4080 SUPER，接手时 `5670 / 16376 MiB`，未推理。普通沙盒账户的 GitHub CLI 认证失败（HTTP 401）；用户明确批准本轮必要 Git/GitHub 命令经审批使用 `yun` 用户上下文，后者认证与 API 成功。此项记录为授权例外，不是普通沙盒认证通过。阶段分支已首次推送，远程 SHA 已核对，创建前查询无已有对应 PR；已创建 [draft PR #6](https://github.com/Hyakuri/gazelle/pull/6)，base 为 `feature/mediapipe-head-tracking`，正文取自既有 `STAGE2_PR_BODY.md`。
- **阻塞：R1 与 r2 第 4 步不能对当前接受的全部 FPS 同时成立。** `resolve_video_fps(2000)` 返回 `2000.0`，没有上限约束。原始值为 `[0, NaN]` 时，第一帧输出 `0`；第二帧按精确公式 `p + 1000 / fps` 输出 `0.5`。Python `int(round(0.5)) == 0`，整数毫秒序列为 `[0, 0]`，违反 R1。直接调用现有 `MediaPipeBackend._video_timestamp`（不构造 backend 或模型）得到 `ValueError: MediaPipe video timestamps must strictly increase after rounding`。这是合成边界复现，不是对这批作业视频故障率的测量。
- **命令与结果（已实际运行，普通沙盒、现有 Gazelle 环境）**：设置 `$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'gazelle-task-131-pycache'`，将逐帧 r2 算法与断言作为标准输入交给 `& 'C:\Users\yun\anaconda3\envs\Gazelle\python.exe' -`。契约表的全部 7 组数值/来源用例均通过对照（`math.isclose` 用于表中省略的小数）；额外边界对照如下。诊断脚本正常结束，退出码 0；未运行 unittest suite，没有 suite 测试数或 skip 结果可报告。最小复现代码如下，可单独从仓库根目录运行：

  ```python
  from types import SimpleNamespace
  from gazelle.runtime.media import resolve_video_fps
  from gazelle.runtime.perception.mediapipe_backend import MediaPipeBackend

  fps = resolve_video_fps(2000)
  checker = SimpleNamespace(_last_timestamp_ms=None)
  MediaPipeBackend._video_timestamp(checker, 0.0)
  fallback = 0 + 1000 / fps  # r2 step 4 for the second raw value NaN
  assert fallback == 0.5 and int(round(fallback)) == 0
  try:
      MediaPipeBackend._video_timestamp(checker, fallback)
  except ValueError as error:
      print(type(error).__name__ + ': ' + str(error))
  else:
      raise AssertionError('Expected the existing strict timestamp check to reject')
  ```

  | 输入 raw | FPS（原值/resolve 后） | r2 输出 | 整数毫秒 | 现有 backend 校验 |
  | --- | --- | --- | --- | --- |
  | `[0, NaN]` | `30 / 30.0` | `[0, 33.333333333333336]` | `[0, 33]` | 通过 |
  | `[0, NaN]` | `1000 / 1000.0` | `[0, 1.0]` | `[0, 1]` | 通过 |
  | `[0, NaN]` | `2000 / 2000.0` | `[0, 0.5]` | `[0, 0]` | 拒绝，违反 R1 |

- **需要 Claude 明确的契约**：建议 R1 优先，补充 fallback 在整数毫秒上的最小递增约束，例如有限计算结果使用 `p + max(1.0, 1000 / fps)`，并补充高帧率边界测试；是否采用及最终算法由 Claude 决定。另一方向是显式界定并验证支持的 FPS 范围，但会改变当前输入兼容性。Codex 尚未采用任一方案，未更改帧率、读取器或 backend 检查。
- **反证式复核**：核对了 `resolve_video_fps` 的实际返回值、Python 的实际取整以及生产 backend 的实际拒绝；30/1000 FPS 的对照通过，2000 FPS 的同路径对照失败。7 组表格用例本身一致，问题在通用 R1 与精确 fallback 公式的覆盖范围。未把独立校验声称为完整读取器或真实视频测试。
- **变更范围与文档**：仅修改本任务的实施报告及 STATE 执行记录；任务契约、代码、测试、设计规范、ROADMAP 和四份用户文档保持不变。没有用户可见实现变化，因此本次无需同步四份用户文档。`git diff --check` 与首次发布前的 `git diff --check bbec056..HEAD` 通过；已观察到已有 LF/CRLF 转换提示，为非致命 Git 提示。
- **外部活动**：GitHub 认证查询、分支推送、draft PR 创建与报告发布；Python 导入现有依赖，字节码放 `%TEMP%`。仅调用 FFmpeg/ffprobe 的版本查询与 `nvidia-smi` 状态查询。没有模型构造、推理、CUDA 运算、资源下载、Conda 修改、视频解码、FFmpeg 编解码或数据上传；没有复制或输出凭证。原始数据未写入。
- **未运行与交接**：实现、聚焦单测、完整离线门、29 个 MP4 前 600 帧检查、原始 AVI 截断 CLI 检查、300 帧 GPU smoke 均未运行；TASK-132、TASK-123、TASK-001 未启动。按协作方案 §3.1 第 4 步，报告冲突并交回 Claude；`next_actor=claude`，`writer=none`，`current_task` 留在 TASK-131，任务不标为 `ready-for-review`。
- **状态标签**：已静态检查；已实际运行（契约最小复现与首次发布）；尚未实施；待 Claude 修订契约及后续独立验收。

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
