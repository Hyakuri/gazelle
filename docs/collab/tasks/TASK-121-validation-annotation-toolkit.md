# TASK-121：多视角同步片段的注视区域标注工具（决策 D12 r2）

状态：ready（依赖 TASK-134 与 TASK-123）
创建：2026-10-15（Asia/Tokyo），同日改为 r2　协调者：Claude　实现者：Codex　验收：用户（标注体验）与 Claude（工具审查）
设计：[作业数据验证集规范 r2](../../superpowers/specs/2026-10-15-workdata-validation-set-design.md) §2 至 §6。
授权：用户 2026-10-15 批准 D12 r2。2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。
摄像机角色（用户 2026-10-15 确认）：前方为 `cam_b`（通常名为カメラ2），右侧为 `cam_a`（通常名为カメラ1），全局为 `cam_e`（設備カメラ）。一律按 TASK-132 的物理编号取文件，不按文件名。
修订：r1 的单帧视线点标注（sample1、sample2）已撤回，本契约整体替换 r1。

## 1. 契约

### 目标

交付一套本机工具，让用户在浏览器中同步查看三个视角的 60 秒片段，以 0.2 秒为时间步高效、可中断地标注注视区域，生成可校验的数据集与标注文件。

### 必须实现

代码放在新目录 `tools/validation/`（含 `__init__.py`），只使用标准库与 `Gazelle` 环境已有的包。

1. **片段抽样** `sample_segments.py`：
   - 输入：TASK-134 的 `session.json` 与旁注文件；参数 `--seed`（默认 20261015）、`--per-session`（默认 4，重叠不足 45 分钟的录制取 2）、`--segment-seconds`（默认 60）、`--dataset-root`。
   - 按规范 §3 分层抽样、避开缺口、加入试标片段（2026-09-07 22:20:00 至 22:21:00）。
   - 写 `manifest.json`：数据集版本、种子、方法、重抽记录；每段的会话、起始时钟时刻、在代理网格中的帧号范围、所用三段代理视频的 SHA-256、时间映射版本。
   - 目标目录已存在时拒绝覆盖，除非显式 `--overwrite`。
2. **抽帧** `extract_frames.py`：每段每个时间步生成一张拼接 JPEG，写入 `<dataset>/frames/<segment_id>/<step>.jpg`，在 manifest 中记录哈希。布局：左列上为前方（`cam_b`）、下为右侧（`cam_a`），各 640×360；右侧为全局（`cam_e`），1280×720；共 1920×720，质量 85；每个视角左上角标注其角色名。
3. **类别配置**：数据根中存在 TASK-123 的正式区域文件 `roi_regions.json` 时，用 TASK-123 的类别生成函数得到 `<dataset>/classes.json`，并把 `roi_reference.png` 复制到数据集根目录；否则复制 `tools/validation/default_classes.json`（提交，内容为规范 §4.1 的默认类别、按键与颜色）。工具只从 `<dataset>/classes.json` 读取类别。manifest 记录所用区域文件的 SHA-256。
4. **标注服务** `annotate_server.py`：
   - 标准库 HTTP 服务，只绑定 `127.0.0.1`；HTML 与 JavaScript 内联，不引用任何外部资源。
   - 界面与操作按规范 §5：同步显示三视角；`<dataset>/roi_reference.png` 存在时显示参考图，否则显示文字定义；播放与暂停（1× 与 0.5×）、单步 0.2 秒与 1 秒、数字键从当前步起设定类别直到下一个变化点、删除变化点、撤销、彩色时间轴、跳到下一个未标注步、标记他人入镜的起止。
   - 每次修改即原子写入标注文件并保留上一版备份；重启后从未完成处继续。
   - `--labels-path` 指定其他标注文件，供试用与审查，不污染正式标注；`--annotator` 记录标注者。
   - 业务逻辑与 HTTP 层分离，便于不开端口直接测试。
5. **标注读写与校验** `labels.py`：实现规范 §4.3 的 schema；`validate` 子命令检查标注与 manifest 一致、区间覆盖每一步且不重叠；提供把区间展开为逐步数组的函数。
6. **标注指南** `tools/validation/ANNOTATION_GUIDE_CN.md`：中文说明类别定义与判定规则（规范 §4）、操作步骤、快捷键、预计用时、隐私注意事项。
7. **测试**（默认隔离：不联网、不下载、不用 CUDA、不读真实视频、不调用真实 FFmpeg）：抽样可复现；每层一段；缺口重抽；manifest schema；标注 schema 的合法与非法样例；区间展开；原子写入、备份与续标；不开端口调用请求处理函数，覆盖读取片段、保存修改、拒绝非法输入。
8. **在真实数据上生成数据集**（仅 CPU）：用 TASK-134 的代理视频生成 26 段加 1 段试标片段。正式区域文件已就绪时写入 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2\`；尚未就绪时用默认类别写入 `...\gazelle_validation\roi_r2_trial\`，并在实施报告中说明正式数据集待区域文件就绪后重新生成。运行校验；启动服务并确认能加载第一段（用 `--labels-path` 指向临时文件），确认后关闭服务进程。

### 非目标

- 不改运行时代码（`gazelle/`）与 CLI。
- 不做区域推断与评估（第 3 阶段）。
- 不在界面中显示任何模型预测。
- 不改四份用户文档。

### 依据材料

- 规范 r2；TASK-134 的代理视频、`session.json` 与旁注 schema。
- 本文件 r1 的工具结构（服务与逻辑分离、原子写入、`--labels-path`）在 r2 中保留。

### 不可变约束

- 规范 r2 §2 的隐私与数据规则：代理视频、帧、标注不进 Git、不上传；不写入源目录与用户的验收目录。
- AGENTS.md 的默认测试隔离规则。不修改 Conda 环境，不下载。

### 允许动作

新建 `tools/validation/**` 与 `tests/test_validation_*.py`；读取数据根；在 `C:\Users\yun\Documents\Claude_Code\gazelle_validation\` 下创建数据集；按协作方案 §4 提交并推送（只提交代码、测试、默认类别配置与指南），并在 draft PR 发英中双语评论。

### 禁止

提交任何帧、代理视频、标注或输出；新建分支或 PR、合并、force push；修改环境；下载；修改 `gazelle/` 下的运行时代码。

### 验收标准

1. 新增测试全部通过，完整离线门通过，无新增 skip。
2. 数据集包含 27 段（26 段加试标片段）、每段 300 个时间步的拼接帧、manifest 与 `classes.json`；校验命令退出码为 0。
3. 同一种子重复抽样得到相同片段（实施报告附比较命令与结果）。
4. 标注服务只监听 `127.0.0.1`；页面不请求任何外部 URL。
5. `git status` 与提交记录中没有图像、视频或标注数据。
6. Claude 审查时用 `--labels-path` 指向临时文件，在内置浏览器完整标注试标片段，该文件通过校验；正式标注文件保持不存在或不变。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-121-pycache"
& $py -m unittest discover -s tests -p "test_validation_*.py" -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（Claude 审查代码并实际试用界面）。
- 需真实运行：生成数据集，仅 CPU。
- 文档同步：标注指南；四份用户文档不变，原因是这是研究工具，不改变运行时行为。
- 风险与回退：工具问题只影响标注效率与数据集，不影响运行时；回退方式是 `git revert`，数据集目录可删除重建。
- 依赖：TASK-134；TASK-123 的工具与用户画好的正式区域文件。区域文件尚未画好时，先用默认类别完成开发与测试，正式数据集等区域文件就绪后再生成。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 数据集生成结果（段数、哈希、用时）：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 试标结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户标注体验与问题：
