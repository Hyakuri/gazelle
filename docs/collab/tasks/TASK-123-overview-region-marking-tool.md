# TASK-123：全局摄像机画面中的区域标记工具

状态：changes-requested（2026-10-16，必须修复 5 项，见 §3）
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（标记体验）与 Claude（工具审查）
依据：用户 2026-10-15 对 Q8 的回答：之后在設備カメラ的画面中标记取货台、作业台、放置区、工作区等区域。[验证集规范 r2](../../superpowers/specs/2026-10-15-workdata-validation-set-design.md) §4；[多摄像机设计](../../superpowers/specs/2026-10-15-multicamera-attention-design.md) §3.2。
授权：2026-10-14 本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

交付一个本机浏览器工具，让用户在全局摄像机（`cam_e`，設備カメラ）的参考画面上画出各区域的多边形，生成区域定义文件与参考图。区域定义供标注工具（TASK-121）生成类别与参考图，也供第 3 阶段计算“双手所在区域”特征。

### 必须实现

代码放在 `tools/validation/`（含 `__init__.py`），只使用标准库与 `Gazelle-next` 环境已有的包。本任务建立的本机服务基础代码（127.0.0.1、原子保存、业务逻辑与 HTTP 分离）供 TASK-121 复用。

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

不做逐时刻标注（TASK-121）；不在画面上显示任何模型输出；不改 `gazelle/`。

### 依据材料

TASK-132 的清单与重封装结果；验证集规范 r2 §4；作业数据分析 §2。

### 不可变约束

源目录只读；候选帧、区域文件与参考图只写数据根 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\roi\`，不进 Git、不上传；默认测试隔离。

### 允许动作

新建 `tools/validation/**` 中与本任务相关的文件与 `tests/test_validation_*.py`；更新四份用户文档的「研究数据工具」小节与 `tests/test_usage_docs.py`；读取源目录与数据根；写数据根；按协作方案 §4 提交并推送（只提交代码、测试、默认区域配置与指南），并在 draft PR 发英中双语评论。

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
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
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
- 文档同步：需要。在四份用户文档的「研究数据工具」小节（TASK-132 建立）中加入本任务的工具：写明用途、在仓库根目录运行的入口命令、读取什么、写到哪里、是否调用 FFmpeg、是否使用 GPU 或网络，并链接 `tools/validation/ROI_GUIDE_CN.md`。`README.md` 与 `README_CN.md` 只放简介与指向 USAGE 的链接；`docs/USAGE.md` 与 `docs/USAGE_CN.md` 放工具表。中英文语义一致；`tests/test_usage_docs.py` 在两份 USAGE 中锁定本任务的入口模块名。原因：这些工具由用户或 Codex 直接运行，属于用户可见的用法，适用 AGENTS.md 的文档同步规则（2026-10-15 按 Codex 接手核对修正）。
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

### 2026-10-16 实施与候选帧检查（Codex）

- **提交与范围**：`26b50f289e374460720f52222cb4ecbb08561fea` — `Add local overview region marking and reference export`；`4220c98fd88d582bfc83901947e7176a710b5bbd` — `Preserve region colors in derived annotation classes`，均已推送。工具、默认区域配置、中文指南、6 项 ROI 测试、文档测试与四份用户文档；未修改 Gazelle 运行时。
- **实现**：每会话 12 个等长区间中点抽帧，记录实际容器时间、请求时间、源与图像哈希；新文件名保留旧候选图，先校验再原子发布 manifest。浏览器页面可选参考帧、画/闭合多边形、拖动/删除顶点、删除区域、撤销、自定义 target、跨日期叠加核对、保存与导出。区域定义与未闭合草稿分开原子保存，各有上一版备份。区域定义校验规范坐标、非退化且不自交、唯一 key、至多一个 cell。类别从配置和 target 顺序生成，unknown=0，保留颜色，供 TASK-121 调用生成函数。
- **离线验证**：新增测试先因包未实现失败，再通过。最终 `python -m compileall main.py gazelle tests tools`、`python -m unittest discover -s tests -v`（**555 项，3.961 s，无 skip**）、`python main.py --help`、`python main.py --list-models`、`git diff --check` 全部退出 0。ROI 6 项覆盖合法/非法几何、类别/颜色、坐标、原子保存/备份/恢复、候选帧伪来源、错误 manifest 保留旧版本、参考图合成、试用导出隔离、直接调用 HTTP handler（不开端口）、Host/Origin/token 边界。聚焦早期 5 ROI + 17 文档 = 22 项通过；最终新增 HTTP 用例包含在 555 中。node 对外置临时脚本执行 `--check`，退出 0。现有微软雅黑字体加载及中文 mask 检查通过。非致命输出仍为既有 OpenCV 无效视频测试与 Git 换行提示。
- **真实抽帧命令**：Gazelle Python 执行 `-m tools.validation.extract_roi_candidates --inventory <data>/inventory/inventory.json --remux-root <data>/remux --out-root <data>/roi`，其中 data 为 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata`；BelowNormal，退出 **0**。20260821、20260828、20260903、20260911、20260925、20261002、20261009 各 12 张，总计 **84 张 1920x1080 JPEG**。重新运行 `validate_candidates(<data>/roi/candidates.json)`，全部 SHA-256、尺寸、格式与元数据通过。
- **页面实测命令**：`-m tools.validation.roi_server --candidates <data>/roi/candidates.json --regions-path <data>/roi/codex_pagecheck.json --annotator codex-pagecheck --port 0`。实际地址为 `http://127.0.0.1:4285`。通过内置浏览器只读打开：页面显示“已加载 84 张候选画面”；DOM 有 84 个候选按钮、7 个日期叠加面板；检查时 47 张 lazy 缩略图已解码为 1920x1080，图像 origin 只有本机地址；浏览器 error 日志为空。没有选择参考或画正式区域，没有截图/上传图像。
- **服务关闭与权限证据**：普通沙盒 `Get-NetTCPConnection` 被拒绝，未提权；改用 `netstat -ano -p tcp` 确认仅 `127.0.0.1:4285 LISTENING`，PID 331148。工具 PTY 的 Ctrl+C 未结束该进程；核对 PID 的 Gazelle Python 路径与本次启动时间后，仅停止该进程；随后无该端口监听，浏览器临时标签已关闭。`roi_regions.json` 与 `codex_pagecheck.json` 均不存在。
- **外部活动**：真实 CPU OpenCV 解码、Pillow resize/JPEG、磁盘与哈希读取；本机 HTTP 页面与图像读取。未调用 FFmpeg 可执行程序、模型、GPU、下载或安装；未改环境，无外部页面资源或数据上传。派生图像/清单仅保存在授权数据根。图像参考渲染通过合成帧单测；没有代画真实区域。
- **反证式复核**：重复/保留 key、bool/NaN/越界点、自交/退化多边形、多个 cell、错误 token、异源请求、越界图像 ID、错误抽帧时间均被拒绝；失败保留旧区域/manifest。相同图像哈希的不同时间候选按完整 reference 元数据匹配。试用区域导出不覆盖正式文件。
- **尚待验收**：Claude 需按契约用临时 regions-path 在浏览器画四个默认区域，确认拖动、删除、撤销、重启恢复、中文参考图与各日期叠加图；用户之后画正式边界。Codex 的页面加载与隔离单测不代替该独立交互/标记体验验收。状态：已静态检查、已实际运行，可交审。

#### 自主决定（A）

- 候选时间取 12 个等间隔区间中点，避开精确 EOF；同时记录实际与请求容器时间。新候选使用独立文件名，避免覆盖已选参考。
- 未闭合草稿放在同名 .draft.json，正式 schema 只包含已闭合且合法区域；试用文件的导出使用独立子目录。
- 页面导出按钮复用 CLI 渲染函数，采用本机现有 CJK 字体；类别颜色随 target 保留，固定类别颜色来自 JSON 配置，符合 TASK-121 彩色时间轴使用方式。
- 只读监听查询被拒绝时使用 netstat；工具 PTY 不能正常传递中断时，核对后停止本次唯一服务 PID，没有更改权限或配置。

#### 范围外改动

无；默认配置与工具代码入 Git，候选帧、实际区域、参考图不入 Git。

#### 待 Claude 判断（B）

无阻塞问题。需要独立审查区域/类别接口与完整浏览器操作，验收仍待进行。

#### 待用户决定（C）

无本轮实施决策。正式画区域属于计划中的用户后续步骤，等待 Claude 先审查工具。


## 3. 审查结论（Claude 追加）

### 2026-10-16 第 1 轮审查

- 审查目标（SHA 范围）：`26b50f2`、`4220c98`，审查时 HEAD 为 `c5473bf`。
- 独立复跑结果：完整离线门 562 项通过，无 skip。Claude 在内置浏览器中用临时文件 `claude_review_trial.json` 与 `claude_review_dblclick.json` 实际操作，正式区域文件全程不存在。另有一份独立代码审查。
- 通过的项目：页面加载 84 张候选帧；选择主参考帧；画区域、回车闭合、自动保存；`roi_regions.py validate` 通过；删除顶点、“至少三个顶点”的限制、撤销；拖出自相交时拒绝保存；重启服务后恢复全部标记；导出 8 张图与 `classes.json`，默认区域下的类别与键值和验证集规范 r2 §4.1 一致；服务只监听 `127.0.0.1`，拒绝异源请求，令牌比较使用 `compare_digest`，图像只按清单 ID 提供，页面不引用外部资源；区域几何校验能拒绝蝶形、T 形、共线重叠、重复顶点与非法坐标。

#### 必须修复

1. **叠放顺序使内部区域无法编辑。** 区域按绘制顺序叠放，最后画的工作区覆盖整个画面。在画面上点击总是选中工作区；从列表选中内部区域后，它的顶点圆点被工作区挡住，按下鼠标又会选回工作区，无法拖动。按指南先画三个目标、最后画工作区，必然出现。修复：`cell` 区域放在最底层；选中区域的顶点圆点在所有多边形之后绘制；画面点击选择包含该点、面积最小的区域。补回归测试。
2. **参考图丢失目标区域。** `render_roi_reference.py` 的 `draw_regions` 在同一个 RGBA 图层上依次调用 `ImageDraw.polygon`，后画的工作区直接覆盖先画的多边形，`roi_reference.png` 与七张叠加图只剩工作区边框和文字。沿边线采样：工作区 61/61 命中，取货台 0/61，放置区 0/61，作业台 3/61（来自画面中本身的蓝色治具）。修复：每个区域单独合成，所有填充之后再画边线与标签，`cell` 先画。补回归测试，检查重叠多边形渲染后每个区域的边线像素都存在。
3. **双击闭合会产生重复顶点。** Claude 已在浏览器中复现：单击两点后在第三点双击，草稿中第三点出现两次，多边形没有闭合；再按回车时提示“未保存：Polygon vertices must be distinct”。原因是 `pointerdown` 事件的 `detail` 在 Chromium 中为 0，`e.detail>1` 的判断不起作用，而且每次按下都重绘画布，`dblclick` 可能不会触发。修复：在 `click` 事件中按 `detail` 只接受第一次点击，或在闭合前去掉与上一点相距约 3 像素以内的重复点；双击能可靠闭合。补回归测试。
4. **区域文件在完成前就已存在。** 选定参考帧后立即生成 `roi_regions.json`，此后每次操作都会重写。TASK-121 以该文件存在作为“正式区域已就绪”，可能用半成品生成正式数据集。修复：导出时写入完成标记，记录完成时间与区域文件的 SHA-256；完成标记要求至少一个 `target` 且恰好一个 `cell`；`make_classes` 拒绝零个目标区域。TASK-121 改为以完成标记为准。
5. **类别键可能超出一位数字，颜色可能撞色。** 目标区域没有数量上限，7 个目标时 `absent` 的键为 10；自定义目标一律使用 `#c0392b`，与 `away` 同色。修复：非零键最多 9 个，超出时拒绝并提示；自定义目标从一组与固定类别不同的颜色中依次分配。另外在指南中说明，键按目标区域的绘制顺序分配，重画会改变键。

#### 建议修复

- 服务端校验错误以英文显示，例如 `Polygon must not self-intersect`、`Polygon vertices must be distinct`，界面其余部分为中文；改为中文提示。
- 备份只保护一步：每次保存（包括草稿点击）都轮换 `.json.bak`，页面重载后无法找回误删的区域。内容未变时不写，或保留多个备份。
- 超大整数触发的 `OverflowError` 与深层嵌套 JSON 触发的 `RecursionError` 没有捕获；应返回 400，并在解析请求体之前检查令牌。
- 草稿只校验 `points`，`region` 与多余字段原样保存；应按 schema 校验。
- `extract_roi_candidates.py` 接受预期路径上的任何 MP4，没有对照 `remux_report.json` 确认已通过校验；没有检查时间递增与接近请求时间；重写 `candidates.json` 时没有备份。
- 补测试：HTTP 超长请求、错误内容类型与令牌 403 的路径；T 形与共线重叠多边形。
- 备注：没有最小面积限制，1 像素的三角形也能通过；可以考虑设下限。

#### 结论

changes-requested。必须修复 1 至 5 完成后由 Claude 复核。A 级自主决定全部认可。复现用的试用文件在仓库外的 `gazelle_data\workdata\roi\claude_review_*`。

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户标记体验与问题：
