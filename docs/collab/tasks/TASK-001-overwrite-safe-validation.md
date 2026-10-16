# TASK-001：static/json 参数在 `--overwrite` 删除前校验

状态：accepted（2026-10-16）
创建：2026-10-14（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
问题来源：GZ-04（登记表 C004、C008），见 [分析报告 §5](../analysis/2026-10-14-codebase-analysis.md)。

## 1. 契约

### 目标

推理运行（给了 `--input`）在执行任何 `--overwrite` 删除之前，就以 usage error（退出码 2）拒绝能仅凭参数判定的 static/json provider 错误，保护上一轮结果。

### 背景

`create_output_dir` 先执行（`gazelle/runtime/pipeline.py:250`、`:361`），`--overwrite` 时会 `shutil.rmtree`（`:124-125`）。provider 在其后才构造（`:252`、`:367`）。
因此以下错误目前都在删除之后才报，并以 traceback 和退出码 1 结束：static 缺 `--bbox`；`--bbox nan 0 1 1`；`--bbox` 坐标倒序；`--person-id` 数量与 `--bbox` 不符；json 缺 `--head-data`；`--head-data` 指向不存在的文件。

### 必须实现

在 `RuntimeConfig.validate()`（`gazelle/runtime/config.py:274-343`）末尾增加：

1. **始终检查**
   - `head_source` 属于 `none`、`static`、`json`、`mediapipe`。
   - `bbox_format` 属于 `normalized`、`pixel`。
   - 取值集合只保留一个来源。可新增 `SUPPORTED_HEAD_SOURCES`，并复用 `gazelle/runtime/heads.py` 已有的 `SUPPORTED_BBOX_FORMATS`。`cli.py` 的 `choices` 应引用同一常量。
2. **仅当 `input_path` 非空，且 `list_models` 与 `prepare_only` 都为 False 时检查**
   - `head_source == "static"`：
     - `bboxes` 至少 1 个。
     - 每个 bbox 恰为 4 个有限实数，拒绝 bool、NaN、inf。
     - `normalized` 格式必须能通过 `gazelle.runtime.geometry.sanitize_normalized_bbox(bbox, clip=True)`。只校验，不回写：`self.bboxes` 与 `run_config.json` 里的 `bboxes` 保持用户原值。
     - `pixel` 格式要求 `xmin < xmax` 且 `ymin < ymax`。裁剪后是否非空需要图像尺寸，仍留在逐帧时检查。
     - `person_ids` 为 None，或与 `bboxes` 等长、元素为 int 且不是 bool。
   - `head_source == "json"`：`head_data` 非空，且 `Path(head_data).is_file()` 为真（只读检查）。
3. **错误信息**包含对应 CLI 选项名：`--head-source`、`--bbox-format`、`--bbox`、`--person-id`、`--head-data`。`parse_runtime_config` 已会把 `ValueError` 转成 `parser.error`，即退出码 2。
4. `pipeline.py` 与 `heads.py` 中现有的防御性检查保持不变。

### 非目标

- 不改 `pipeline.py` 的执行顺序，不拆分 `create_output_dir`（属于决策 D6）。
- 不在加载期校验 JSON 文件内容（属于 D6）。
- 不处理同帧 `person_id` 重复（C033）。
- 不处理 mediapipe 或 none 模式下被忽略的 `--bbox`。
- 不改 MediaPipe、checkpoint、设备相关的时序。

### 依据材料

- 基线：阶段分支 `feature/stage2-correctness` 执行时的 HEAD。它在 `bbec056` 之上只有文档提交，原先的交接 overlay 已在其中提交（2026-10-15 更正）。
- 代码：`gazelle/runtime/config.py:274-395`、`gazelle/runtime/heads.py:14-170`、`gazelle/runtime/geometry.py:24-42`、`gazelle/runtime/pipeline.py:67-145`、`gazelle/runtime/cli.py:54-99`。
- 测试：`tests/test_runtime_cli.py`（退出码 2 的写法见 `:302-310`、`:590-596`）、`tests/test_image_pipeline.py:187-194`、`:369-375`、`tests/test_usage_docs.py:515-553`。
- 文档：`docs/USAGE.md:141`、`:148-151`、`:288`、`:473` 及 `docs/USAGE_CN.md` 同行；`README.md:182`；`README_CN.md:191`。

### 不可变约束

- AGENTS.md 的全部 Runtime Invariants 与 Research And Data Integrity。
- `run_config.json` 的键集合与取值语义不变。
- `--list-models` 与 `--prepare-only` 的行为不变。
- `--help` 与 `--list-models` 不得新增导入 `gazelle.model`、`gazelle.backbone`、`mediapipe`（`tests/test_runtime_cli.py:28-52`）。
- 默认测试隔离：不联网、不下载、不用 CUDA、不调用真实 FFmpeg。

### 允许动作

- 读全库。
- 修改：`gazelle/runtime/config.py`；`gazelle/runtime/cli.py`（仅让 `choices` 引用常量，不改选项名、默认值、help 含义）；`tests/test_runtime_cli.py`；`tests/test_image_pipeline.py`；`tests/test_video_pipeline.py`（仅当既有用例因新校验需要调整）；`tests/test_usage_docs.py`；`docs/USAGE.md`、`docs/USAGE_CN.md`、`README.md`、`README_CN.md` 的相关句子。
- 若为避免导入环必须移动常量，可移到无环模块，但 `heads.SUPPORTED_BBOX_FORMATS` 必须继续可导入。
- 在本文件末尾追加「实施报告」；按 [协作方案](../COLLABORATION_PLAN_CN.md) §3 更新 `docs/collab/STATE.md` 中归 Codex 维护的字段。
- 按协作方案 §4 在阶段分支提交并推送。
- 运行下方验证命令。

### 禁止

新建分支或 PR、修改或合并 PR、force push；安装或修改 Conda 环境；下载任何资源；真实模型推理（本任务不需要）；修改上面未列出的文件。

### 验收标准

1. 以下参数组合经 `parse_runtime_config` 以 `SystemExit` 退出码 2 结束，且 stderr 含对应选项名：
   - `--input image.jpg --head-source static`（没有 `--bbox`）
   - `--input image.jpg --head-source static --bbox nan 0 1 1`
   - `--input image.jpg --head-source static --bbox 0.6 0.2 0.3 0.4`
   - `--input image.jpg --head-source static --bbox 1.2 1.3 1.5 1.6`（normalized，裁剪后为空）
   - 两个 `--bbox` 配一个 `--person-id`
   - `--input image.jpg --head-source json`（没有 `--head-data`）
   - `--input image.jpg --head-source json --head-data <不存在的路径>`
2. 以下组合仍被接受：
   - `--prepare-only --head-source static`（没有 `--input`）
   - `--list-models --head-source static`
   - 现有 `test_parse_image_static_config`
   - `--input image.jpg --head-source static --bbox-format pixel --bbox 10 20 30 40`
3. 端到端离线回归：在 `TemporaryDirectory` 中写入 `frame.png`，并预先创建 `outputs/frame_gazelle/predictions.json`（内容为 `old`）。调用 `gazelle.runtime.cli.main([... "--input", <frame.png>, "--output-dir", <outputs>, "--overwrite", "--head-source", "static"])`，断言 `SystemExit` 退出码 2，且 `predictions.json` 内容仍为 `old`。再为“json 指向不存在的文件”写同样一例。
4. 编程接口：
   - `RuntimeConfig(head_source="bogus").validate()` 与 `RuntimeConfig(bbox_format="bogus").validate()` 抛 `ValueError`。
   - `RuntimeConfig(input_path="x.png", head_source="static", bboxes=((0.1, 0.2, 0.3, 0.4),)).validate().bboxes` 与输入完全相同。
5. `test_static_without_bbox_rejected` 与 `test_json_without_head_data_rejected` 调整为两层断言：`validate()` 层拒绝；provider 层（用未调用 `validate()` 的配置，或 `input_path=None`）仍拒绝。
6. 文档：四份文档说明 static/json 参数错误会在任何 `--overwrite` 删除之前以 usage error（退出码 2）拒绝；删除仍发生在 provider、模型与资源准备之前，JSON 内容错误、MediaPipe 资源、checkpoint 与设备问题仍可能在删除之后才出现。保留 `test_usage_docs.py` 现有全部 token，并新增一个两份 USAGE 都包含的英文 token，例如 ``before any `--overwrite` deletion``。
7. 完整离线门全部通过：测试数等于 531 加新增数，无失败，skip 不增加；`git diff --check` 无错误。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-001-pycache"
& $py -m unittest tests.test_runtime_cli tests.test_image_pipeline tests.test_video_pipeline tests.test_heads tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。`RuntimeConfig.validate()` 是公开接口，CLI 退出码行为也会变化。
- 需真实 smoke：否。
- 文档同步：需要，四份文档加 `tests/test_usage_docs.py`。
- 风险与回退：风险低。库调用者传入无效 static/json 配置时会更早报错。回退方式是撤销本任务的 diff。
- 依赖：无。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：分支、HEAD、`git status -sb`、可见规则来源
- 变更文件（含新增、未跟踪）：
- 命令、退出码、测试数、warnings 与 skips：
- 证据类型：静态 / mock 单测 / 真实模型、GPU、FFmpeg / 正式实验
- 外部活动（网络、下载、缓存、环境）：
- 反证式复核（v1.1 §9）：检查过的反例、边界、最可能失败的路径及结论
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：
- 下一步建议：

### 2026-10-16 实施与回归验证（Codex）

- **基线/提交**：`ab56671bbcf33f823b898125ad30a3766f18f64f` 接手，工作树干净，STATE writer/next_actor 均为 codex，current_task 已按队列推进到本任务。实现提交 `8c0a81b6494957af89e08fdead4aef8caf8cd290` — `Validate static and JSON head arguments before overwrite` 已推送；报告另作提交。保持原分支与 draft PR #6，主线程 Inline Execution。
- **变化**：RuntimeConfig.validate 始终检查 head_source/bbox_format，并在推理模式下检查 static box/ID 与 JSON 文件路径。CLI choices 复用同一常量；normalized 只调用现有 sanitizer 校验，不回写原值；pixel 仅检查有限值/顺序，尺寸相关裁剪仍在原路径。provider 防御性检查、管线执行顺序、JSON 内容检查、模型/资源/设备行为均未改。四份用户文档与文档测试同步，包括剩余 overwrite 风险。
- **RED 与修复**：原实现上运行 3 项新增回归，退出 1（subtest failures 19、errors 2），覆盖原有参数未拒绝和 overwrite 后才报错。首次聚焦 195 项仅 1 error：已有 mocked JSON no-head 测试未提供 head_data，因新校验提前失败；补一个临时空 JSON 文件后保持该用例原来“无头不构造模型”的断言。
- **验证命令**：使用 `C:\Users\yun\anaconda3\envs\Gazelle\python.exe`，`PYTHONPYCACHEPREFIX=%TEMP%\gazelle-task-001-pycache`。`-m unittest tests.test_runtime_cli tests.test_image_pipeline tests.test_video_pipeline tests.test_heads tests.test_usage_docs -v`：**196 项通过**。最后 `-m compileall main.py gazelle tests tools`、`-m unittest discover -s tests -v`：**562 项、4.228 s、无 skip**；`main.py --help`、`main.py --list-models`、`git diff --check` 全部退出 0。新增 6 项 CLI/编程接口测试 + 1 项文档测试。另在全新 Python 进程导入 CLI 后断言 sys.modules 无 gazelle.model / gazelle.backbone / mediapipe，通过。
- **关键证据**：契约 7 组无效 CLI 参数全部退出 2 且包含选项名；static 与 JSON 两种 overwrite 回归均保持原 `predictions.json` 内容 `old`。prepare-only/list-models（含给 input 的组合）继续接受缺 provider 前提参数；none/mediapipe 不检查被忽略 bbox。非法 bool/NaN/inf/短 box、pixel 逆序、错误 ID 数/类型、目录/非路径 head_data 均拒绝。normalized 超范围但可裁剪的原 tuple 对象和值未改变。已存在但内容无效的 JSON 仍能通过参数校验，内容错误留给 provider。
- **外部活动与证据分类**：静态检查、隔离单测、CLI 导入/元数据检查；没有本任务真实模型、GPU、FFmpeg 可执行程序、网络、下载、环境修改或正式实验。测试在 TemporaryDirectory 生成小图/JSON/输出并清理；字节码与日志留在 TEMP。非致命 warning 为既有 OpenCV 无效视频用例的 `moov atom not found`、Git 换行提示，部分 usage 输出为断言错误路径的预期结果。
- **工作区检查**：暂存路径只有 9 个获准代码/测试/用户文档文件；无数据、媒体、权重或凭据。被忽略的 `.codex/`、`models/`、`gazelle/runtime/__pycache__/` 保留；后者文件时间为 2026-10-15 15:53，属于本轮前已存在的缓存，未删除。未改 Multi-Pose、Actions、全局设置、Conda；未创建新分支/重复 PR、force push 或合并。
- **反证式复核与限制**：对比实际 diff，heads/pipeline 防御性检查保持；CLI/help 冷导入不引入模型模块；原始 bbox 与 run_config schema 测试继续通过。保护范围仅参数层，JSON 内容、MediaPipe、checkpoint、设备可用性仍可能在删除后失败，文档未扩大安全承诺。独立 checkout 验收仍待 Claude/用户；Codex 已静态检查、已实际运行，可交审。

#### 自主决定（A）

- 调整一条既有 mocked no-head 测试的 fixture，提供真实临时 JSON 路径，避免新前提检查掩盖其原有测试目标。
- Path 的类型/值/访问错误统一转成带 --head-data 的 ValueError；维持 usage exit 2，不修改 JSON 内容校验时机。

#### 范围外改动

无；所有代码与测试在任务许可路径内。TASK-131 报告仅补充本轮实际环境版本，便于复跑 GPU smoke。

#### 待 Claude 判断（B）

无阻塞问题。请独立审查提前校验边界、原值保留与两条 overwrite 回归。

#### 待用户决定（C）

无。本轮之后交回 Claude，待协调者审查后再由用户独立验收。


## 3. 审查结论（Claude 追加）

- 审查目标：实现提交 `8c0a81b`，审查时 HEAD 为 `c5473bf`。
- 独立复跑结果：Claude 实际运行完整离线门，562 项通过，无 skip。独立代码审查确认：契约的 7 组无效参数与另外 4 组均以退出码 2 拒绝，信息含选项名；应接受的组合仍被接受；`bboxes` 与 `person_ids` 保持原对象与原值；图像与视频两种输入在 `--overwrite` 下，旧的 `predictions.json` 都得以保留；`--list-models` 新进程不导入 torch、numpy、cv2、PIL、mediapipe 或模型模块；新增测试在旧代码上失败。
- 发现：无阻塞或应修复项。两条备注：程序化调用传入 `bboxes=None` 时的错误信息较原始；保护范围只在参数层，JSON 内容、模型与设备错误仍可能在删除之后才出现，文档已如实说明。
- 结论：accepted。
- 集成记录：本任务的提交位于 TASK-123 两个提交之后，所以 `last_accepted` 暂时只能推进到 `e7244d0`；TASK-123 修复通过后一并计入。

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
- 合并状态：
