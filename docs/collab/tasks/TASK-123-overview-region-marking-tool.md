# TASK-123：全局摄像机画面中的区域标记工具

状态：ready（依赖 TASK-132）
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（标记体验）与 Claude（工具审查）
依据：用户 2026-10-15 对 Q8 的回答：之后在設備カメラ的画面中标记取货台、作业台、放置区、工作区等区域。[验证集规范 r2](../../superpowers/specs/2026-10-15-workdata-validation-set-design.md) §4；[多摄像机设计](../../superpowers/specs/2026-10-15-multicamera-attention-design.md) §3.2。
授权：2026-10-14 本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

交付一个本机浏览器工具，让用户在全局摄像机（`cam_e`，設備カメラ）的参考画面上画出各区域的多边形，生成区域定义文件与参考图。区域定义供标注工具（TASK-121）生成类别与参考图，也供第 3 阶段计算“双手所在区域”特征。

### 必须实现

代码放在 `tools/validation/`（含 `__init__.py`），只使用标准库与 `Gazelle` 环境已有的包。本任务建立的本机服务基础代码（127.0.0.1、原子保存、业务逻辑与 HTTP 分离）供 TASK-121 复用。

1. **候选参考帧** `extract_roi_candidates.py`：读取 TASK-132 的清单与重封装后的 E 文件，每次录制在文件时长内均匀取 12 帧，缩放为 1920×1080，JPEG 质量 90，写入 `<数据根>\roi\candidates\<会话>\`；写 `candidates.json`，记录会话、源文件、容器时间、图像 SHA-256。
2. **标记服务** `roi_server.py`：
   - 只绑定 `127.0.0.1`；HTML 与 JavaScript 内联，不引用任何外部资源。
   - 浏览全部候选帧，由用户选定一张作为主参考帧。
   - 画多边形：单击加顶点，回车或双击闭合；可拖动顶点、删除顶点或整个多边形；撤销。
   - 每个多边形选择区域类型。默认列表来自 `tools/validation/default_regions.json`（提交）：取货台 `pick_right`、作业台 `work_front`、放置区 `place_left`，三者为 `target`；工作区 `work_cell`，为 `cell`，表示整个作业区的边界。用户可以新增自定义区域，填写中文名与英文键，类型为 `target`。
   - 核对视图：把当前多边形叠加到每次录制的一张候选帧上并排显示，用于确认摄像机没有移动。
   - 每次修改即原子保存并保留上一版备份；重启后继续。`--regions-path` 指定其他文件供试用与审查；`--annotator` 记录标记者。
3. **区域文件** `roi_regions.json` 的 schema 与校验（`roi_regions.py validate`）：
   - 字段：版本；摄像机 `cam_e`；参考帧（会话、源文件、容器时间、图像 SHA-256、宽高）；区域列表，每项含 `key`、`name_zh`、`kind`（`target` 或 `cell`）、`polygon`（按画面宽高归一化到 0 至 1 的顶点列表）、颜色；标记者；创建与更新时间。
   - 校验：每个多边形至少 3 个顶点、坐标在 0 至 1 之间、不自相交；`key` 唯一；`cell` 至多一个。
4. **参考图渲染** `render_roi_reference.py`：在主参考帧上画出多边形与名称，生成 `roi_reference.png`；另生成每次录制的叠加核对图。
5. **类别生成**：函数从区域文件得到标注类别：各 `target` 区域按顺序，再加固定类别 `cell_other`（在 `work_cell` 内但不在任何目标区域）、`away`、`absent`、`unknown`；输出与 TASK-121 兼容的 `classes.json`，数字键自动分配，`unknown` 为 0。
6. **标记指南** `tools/validation/ROI_GUIDE_CN.md`：启动命令、操作步骤、建议的区域画法（取货台画右侧桌面的取物范围；作业台画前方桌面上实际加工的范围；放置区画前方桌面左侧放置成品的范围；工作区画包含两张桌面与作业者站立位置的整体边界）、预计用时约 10 分钟、隐私说明。
7. **测试**（默认隔离：不联网、不读真实视频、不调用真实 FFmpeg）：区域文件的合法与非法样例（顶点不足、越界、自相交、重复键、多个 `cell`）；归一化坐标换算；类别生成；原子保存、备份与续标；不开端口调用请求处理函数；用伪造的帧来源测试候选帧抽取。
8. **真实运行**（仅 CPU）：为 7 次录制抽取候选帧；启动服务并确认页面能加载候选帧，然后关闭。不代替用户标记。

### 非目标

不做逐时刻标注（TASK-121）；不在画面上显示任何模型输出；不改 `gazelle/`；不改四份用户文档。

### 依据材料

TASK-132 的清单与重封装结果；验证集规范 r2 §4；作业数据分析 §2。

### 不可变约束

源目录只读；候选帧、区域文件与参考图只写数据根 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\roi\`，不进 Git、不上传；默认测试隔离。

### 允许动作

新建 `tools/validation/**` 中与本任务相关的文件与 `tests/test_validation_*.py`；读取源目录与数据根；写数据根；按协作方案 §4 提交并推送（只提交代码、测试、默认区域配置与指南），并在 draft PR 发英中双语评论。

### 禁止

提交任何图像或区域数据；写入源目录或用户独立目录；修改 `gazelle/`；新建分支或 PR、合并、force push；修改环境；下载。

### 验收标准

1. 新增测试通过；完整离线门通过（`compileall` 包含 `tools`），无新增 skip。
2. 候选帧共 84 张（7 次录制各 12 张），`candidates.json` 校验通过。
3. 服务只监听 `127.0.0.1`；页面不请求任何外部 URL。
4. Claude 审查时用 `--regions-path` 指向临时文件，在内置浏览器画出 4 个默认区域，文件通过校验，参考图与叠加核对图生成正确；正式区域文件保持不存在。
5. `git status` 与提交中没有图像或区域数据。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-123-pycache"
& $py -m unittest discover -s tests -p "test_validation_*.py" -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（区域定义决定类别与特征）。
- 需真实运行：抽取候选帧，仅 CPU。
- 文档同步：标记指南；四份用户文档不变，原因是这是研究工具，不改变运行时行为。
- 风险与回退：工具问题只影响标记效率；区域文件可随时重画。回退方式是 `git revert`。
- 依赖：TASK-132。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实运行结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 试标记结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户标记体验与问题：
