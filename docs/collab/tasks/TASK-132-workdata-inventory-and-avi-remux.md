# TASK-132：作业数据清单与 AVI 无损重封装

状态：ready
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude（工具与数据报告）
依据：[作业数据分析](../analysis/2026-10-15-workdata-analysis.md) §1 至 §3.1；GZ-22。
授权：2026-10-14 本地运算授权；2026-10-15 用户提供 `E:\Gazelle_Workdata` 供分析，只读使用。

## 1. 契约

### 目标

为作业数据生成可复现的只读清单，并把全部 11 个 AVI 无损转成 OpenCV 能完整解码的 MP4，存放在仓库外的数据缓存中。

### 必须实现

代码放在新包 `tools/workdata/`（含 `tools/__init__.py` 与 `tools/workdata/__init__.py`），只用标准库与 `Gazelle` 环境已有的包；FFmpeg 与 ffprobe 通过子进程调用，路径默认取 PATH，可用 `--ffmpeg`、`--ffprobe` 覆盖。

1. **摄像机身份配置** `tools/workdata/camera_roles.json`（提交到仓库）：
   - 物理编号 `cam_a`、`cam_b`、`cam_e`，以及每台的识别特征：文件名规则、时钟样式（A 紧贴左边缘，B 向右缩进，E 带星期与 `CAM3`）、MP4 容器帧率（A 为 30，B 为 50）。
   - 按会话的覆盖规则：`20260903` 中 `カメラ1` 对应 `cam_b`，`カメラ2` 对应 `cam_a`。
   - `front` 与 `right` 的语义映射留空（`null`），等用户回答 Q7 后由 Claude 填写。
2. **清单** `python -m tools.workdata.inventory --root <源目录> --out <数据根>\inventory\inventory.json`：
   - 每个文件记录：会话文件夹、相对路径、大小、修改时间、SHA-256（按大小与修改时间缓存，未变化时不重算）、ffprobe 视频流信息（编码、宽高、`r_frame_rate`、`avg_frame_rate`、`nb_frames`、`duration`、视频流 `start_time`）、是否有音轨、前 60 秒小于 64 字节的包所占比例、分段序号（文件名中的 `-1`、`-2`、`-3`）、物理摄像机编号与判定来源（`filename` 或 `override`）、`needs_remux`。
   - 只读源目录，输出写到数据根；目标文件存在时原子替换。
3. **重封装** `python -m tools.workdata.remux --inventory <inventory.json> --out-root <数据根>\remux`：
   - 对每个 `needs_remux` 的 AVI 执行 `ffmpeg -fflags +genpts -i <in> -map 0:v:0 -c:v copy -bsf:v "noise=drop=lt(size\,64)" <tmp.mp4>`，校验通过后原子改名为 `<out-root>\<会话>\<文件名主干>.mp4`。
   - 校验：输出包数等于输入中不小于 64 字节的包数；时长与输入相差不超过 0.5%；包的 PTS 严格递增；OpenCV 在开头、中间、结尾各连续读出 30 帧。
   - 已有且校验通过的输出跳过；`--force` 才重做。失败时删除临时文件，保留已有的有效输出。
   - 写 `remux_report.json`：每个文件的输入与输出大小、包数、小包数、时长、校验结果、用时。
4. **测试**（默认隔离：不调用真实 FFmpeg，不读真实视频）：文件名规则与会话覆盖；小包比例计算；FFmpeg 命令参数逐项断言；用伪造的 ffprobe 结果覆盖校验通过与失败；原子发布（失败不留下目标文件，已有有效输出不被破坏）；SHA-256 缓存命中与失效；命令行参数解析。
5. **真实运行**（CPU 与磁盘 I/O）：对整个源目录生成清单；重封装全部 11 个 AVI；在实施报告中记录文件数、各会话摄像机编号、重封装结果、总输出大小与用时。数据根为 `C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata\`。

### 非目标

- 不改 `gazelle/` 下的运行时代码与 CLI。
- 不做时钟识别、时间映射与同步（TASK-133）。
- 不重新编码，不改变分辨率。

### 依据材料

- 作业数据分析 §1 至 §3.1；本任务的命令即分析中已验证的命令。
- `docs/collab/COLLABORATION_PLAN_CN.md` §5 的数据规则。

### 不可变约束

- 源目录只读。派生数据只写到数据根，不进 Git，不上传。
- AGENTS.md 的默认测试隔离与“下载与发布使用临时文件和原子替换”的原则。

### 允许动作

新建 `tools/__init__.py`、`tools/workdata/**`、`tests/test_workdata_*.py`；读取源目录；写数据根；按协作方案 §4 提交并推送，并在 draft PR 发英中双语评论。

### 禁止

写入 `E:\Gazelle_Workdata\` 或用户独立目录；提交任何视频、帧、清单或报告数据；修改 `gazelle/` 下的代码；新建分支或 PR、合并、force push；修改环境；下载。

### 验收标准

1. 新增测试通过；完整离线门通过（`compileall` 包含 `tools`），无新增 skip。
2. 清单含 40 个文件，会话与摄像机编号与作业数据分析 §1、§2 一致，`20260903` 的覆盖规则生效。
3. 11 个 AVI 全部重封装并通过校验；报告中每个文件的输出包数等于输入的非空包数。
4. 用仓库的 `VideoFrameReader` 读取任一重封装文件的前 600 帧，帧数为 600，时间戳严格递增（TASK-131 合入前后都应成立）。
5. `git status` 与提交中没有数据文件。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-132-pycache"
& $py -m unittest discover -s tests -p "test_workdata_*.py" -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（数据完整性）。
- 需真实运行：是，仅 CPU 与磁盘。
- 文档同步：四份用户文档不变，原因是这些工具服务于本项目的数据准备，不改变运行时行为；用法写在 `tools/workdata/README_CN.md`。
- 风险与回退：重封装只复制视频流，源文件不变；问题只影响缓存，删除缓存即可重建。
- 依赖：无。

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
- 发现：
- 结论：
