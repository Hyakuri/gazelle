# TASK-137：项目环境切换到 `Gazelle-next`（仓库侧）

状态：ready（第 2 轮第一项）
创建：2026-10-17（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：[候选环境评估](../evidence/2026-10-17-env-next-evaluation.md) §0、§3、§4、§7。
授权：2026-10-14 本地修改与本地运算授权。2026-10-17 用户决定 D16：尽早切换；现有 `Gazelle` 原样保留作回退，项目改用 `Gazelle-next` 这个名称。

## 1. 契约

### 目标

仓库的环境定义、项目规则与用户文档改为以 `Gazelle-next` 为当前环境。现有 `Gazelle` 环境保留作回退。本任务不改动任何 Conda 环境，也不改运行时代码。

`Gazelle-next` 已由 Claude 建好并验证，组成见评估记录 §3.1。当前完整清单在 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\env-next\freeze_next_current.txt`。

### 必须实现

1. **`environment.yml`** 改为 `Gazelle-next` 的实际组成：
   - `name: Gazelle-next`；channels 不变；`python=3.14`；`pip`。
   - pip 段：`--extra-index-url https://download.pytorch.org/whl/cu130`，以及以下精确版本：

     | 包 | 版本 |
     | --- | --- |
     | torch / torchvision | 2.14.1+cu130 / 0.29.1+cu130 |
     | timm | 1.0.30 |
     | numpy / scipy / pandas | 2.5.4 / 1.18.1 / 2.3.3 |
     | matplotlib / scikit-learn / pillow | 3.11.2 / 1.9.1 / 12.3.0 |
     | opencv-python、opencv-contrib-python | 5.0.0.93 |
     | mediapipe | 1.1.1 |
     | trackers / supervision / av | 2.6.1 / 0.30.9 / 19.0.1 |

   - 不再列出 torchaudio、xformers、ultralytics、pydeprecate、defusedxml、polars、polars-runtime-32、nvidia-ml-py。原因见评估记录 §3.1、§3.2，用户文档的环境小节要逐项写明，不能静默删除。
   - 用脚本核对：文件中每个固定版本都等于 `Gazelle-next` 中 `importlib.metadata` 报告的版本。核对输出写进实施报告。
2. **回退定义**：把修改前的 `environment.yml` 原样另存为 `environment_py311.yml`，内容不变，仍声明 `name: Gazelle`。`environment_1.0.yml` 不动。
3. **AGENTS.md**：只改与环境有关的句子，其余政策一字不改。
   - 首选环境改为现有的 Conda 环境 `Gazelle-next`，本机解释器为 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`。
   - 原来指向 `Gazelle` 的规定都改为指向 `Gazelle-next`。包括：未经批准不得修改环境；升级前先克隆到一次性沙盒验证；真实 smoke 只在该环境中运行；离线门使用该解释器；迁移时核实该解释器。
   - 新增一句：现有 `Gazelle` 环境作为回退保留，由 `environment_py311.yml` 描述，同样不得在未经批准的情况下修改。
   - 环境文件的说明改为三份：`environment.yml` 描述当前验证过的环境；`environment_py311.yml` 是上一版（Python 3.11）的回退定义；`environment_1.0.yml` 是更早的 NumPy 1.26 参考定义。
   - Triton 与 xFormers 回退行为的规定保留原意。
4. **四份用户文档**（`README.md`、`README_CN.md`、`docs/USAGE.md`、`docs/USAGE_CN.md`），中英语义一致：
   - **安装与环境小节**：
     - 写明新环境的组成（Python 3.14、PyTorch 2.14.1 + CUDA 13.0、MediaPipe 1.1.1、OpenCV 5.0、NumPy 2.5.4、trackers 2.6.1、supervision 0.30.9 等）。
     - 逐项写明不再包含的包及原因。
     - 说明三份环境文件的关系，以及激活命令 `conda activate Gazelle-next`。
     - 在新机器上，`conda env create -f environment.yml` 会创建 `Gazelle-next`。
     - 回退方式：本机保留了 `Gazelle` 时直接 `conda activate Gazelle`，否则用 `environment_py311.yml` 重建。
   - **已验证范围**：README 中“当前 `environment.yml` 的依赖集合已经用真实 MediaPipe 0.10.35 等验证”一段，改为本次实际验证的内容，即评估记录 §4 与本任务验收第 4 条。
   - **xFormers 段落**：当前环境不安装 xFormers，DINOv2 使用 PyTorch 自带的 `scaled_dot_product_attention`。运行时的 xFormers/Triton 回退逻辑保留，只在装有 xFormers 的环境中起作用。与 `--prepare-only` 有关的提示照此调整。
   - **示例命令**：所有示例命令中的环境名与解释器路径改为 `Gazelle-next`，包括研究数据工具小节。
   - **训练脚本**：训练脚本需要 wandb，沿用 README 中“另行安装”的说明，训练说明的其他内容不改。
   - **测试**：`tests/test_usage_docs.py` 中锁定的环境相关 token 随之更新。
5. **其他当前状态文档**：`docs/HANDOFF.md`、`docs/HANDOFF_CN.md` 中关于环境名、解释器路径与环境文件的当前说明，改为 `Gazelle-next`。以下历史文档不改：带日期的快照（`docs/handoff/CURRENT_STATE.md`、`docs/collab/evidence/` 下的旧记录）与 `docs/superpowers/` 下的历史计划。
6. **不改代码**：`gazelle/`、`tools/`、`scripts/`、`data_prep/`、`main.py` 不在本任务范围内。若发现代码中写死了环境名或解释器路径，按协作方案 §3.5 记录，并交 Claude 判断。

### 非目标

- 不改任何 Conda 环境，不安装或卸载包。
- 不改运行时代码，不实施 TASK-136。
- 不改 `docs/collab/` 下的协作文件；它们由 Claude 维护，已经指向 `Gazelle-next`。

### 依据材料

- 评估记录全文。
- `freeze_next_current.txt`：`Gazelle-next` 当前的完整清单。
- 现有 `environment.yml`、`environment_1.0.yml`、四份用户文档、`docs/HANDOFF*.md`、`tests/test_usage_docs.py`。

### 不可变约束

AGENTS.md 中与环境无关的全部规定；现有 `Gazelle` 环境不改动；默认测试隔离。

### 允许动作

- 修改 `environment.yml`；新建 `environment_py311.yml`。
- 修改 AGENTS.md 中与环境有关的句子、四份用户文档、`docs/HANDOFF.md`、`docs/HANDOFF_CN.md` 与 `tests/test_usage_docs.py`。
- 在 `Gazelle-next` 中运行离线门与验收第 4 条的真实 smoke。只用本地缓存，不下载。
- 按协作方案 §4 提交、推送，并在 PR #6 发英中双语评论。
- 问题处理按协作方案 §3.5。

### 禁止

协作方案 §3.5 的硬边界；修改任何 Conda 环境；改动运行时代码；修改历史文档。

### 验收标准

1. **版本核对**：`environment.yml` 中全部固定版本与 `Gazelle-next` 一致。对仓库全部 Python 文件做第三方导入扫描，除 wandb 外都能在 `Gazelle-next` 中找到。
2. **回退文件**：`environment_py311.yml` 与修改前的 `environment.yml` 逐字节相同。
3. **离线门**：完整离线门在 `Gazelle-next` 中通过，无新增 skip。
4. **真实 smoke**（`Gazelle-next`，CUDA，本地缓存）：
   - 输入：`E:\Gazelle_Workdata\秋田大学様解析用動画\20260911\20260911表情解析用カメラ1-1.mp4`，`--max-frames 300`，输出写到仓库外。
   - 运行三次：
     - `--head-source static --bbox 0.35 0.25 0.55 0.55 --bbox-format normalized`；
     - `--head-source mediapipe --max-heads 1`；
     - `--head-source mediapipe --max-heads 1 --save-rendered --video-codec avc1`。
   - 前两次与评估中的运行比较，位置在 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\env-next\runs\new_static_final\` 与 `new_mediapipe_final\`。逐帧状态、头框、热图峰值与 in/out 应完全一致：代码与环境都相同，只允许计时字段不同。若不一致，给出数据，按 §3.5 的 B 级交 Claude。
   - 第三次输出 300 帧 H.264 视频，临时文件已清理。
5. **文档**：四份用户文档中英语义一致；除回退说明外，不再出现把 `Gazelle` 当作当前环境的说法。
6. **AGENTS.md**：改动只涉及环境句子。实施报告中逐句列出修改前与修改后的文字。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-137-pycache"
& $py --version
& $py -m pip check
& $py -m unittest tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。涉及项目规则与环境定义。
- 需真实运行：是，即验收第 4 条。
- 文档同步：需要，这是本任务的主体。
- 依赖：无。第 2 轮第一项，完成后再做 TASK-123 修复。

## 2. 实施报告（Codex 追加，不要修改上文）

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 真实运行结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 自主决定（A 级）：
- 范围外改动：
- 待 Claude 判断（B 级）：
- 待用户决定（C 级）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

### 2026-10-17 接手与事实核对（Codex）

- 实时入口为 `writer=none`、`next_actor=codex`、TASK-137；接手前 HEAD `c5473bf`。只在指定 Claude_Code 仓库开发，采用 v1.1 主线程 Inline Execution。已领取 writer，并以 `7580849` 提交/推送 Claude 的 19 份协调文档，同步 PR #6 正文。
- 普通沙盒工作区、gazelle_data、gazelle_runs、gazelle_validation、TEMP 的创建/删除探针均成功；Git 根正确。项目 TOML 解析成功，三个外部根和网络权限有实际探针支持。普通 `git ls-remote` 成功，普通 `gh auth status` 凭据无效；沿用常设批准在 yun 上下文认证并发布成功，不把它计为普通沙盒认证通过。
- 解释器为 `Gazelle-next` 的 Python 3.14.8；`pip check` 无冲突。FFmpeg/ffprobe 为 `2025-03-31-git-35c091f4b7-full_build-www.gyan.dev`。GPU RTX 4080 SUPER、驱动 617.14，预检 5803/16376 MiB，利用率 44%；启动 static、MediaPipe 前均约 5825 MiB，无其他训练 Python 进程。没有启动 TASK-136。
- 源目录只读可列出；现有 8 个日期目录，比本轮 7 次录制契约多了 `20261016`。不扩大研究集，后续仍以已批准的七次录制清单为准。
- **待 Claude 判断（B 级，暂定文档修正）**：契约与评估 §3.1 称 pydeprecate、defusedxml 新版不再需要，但现有 freeze 与 `importlib.metadata` 均显示 `pydeprecate==0.13.0`、`defusedxml==0.7.1`；trackers 2.6.1 Requires-Dist 含 pydeprecate，supervision 0.30.9 含二者。已按契约移除显式 pin，但文档如实写为仍必需的间接依赖；不卸载，也不修改契约/评估正文。推荐 Claude 修正该事实，避免照错误描述删包。此问题不阻塞其余验证与后续任务。
- **自主决定（A 级）**：真实 smoke 复用上轮已审查的仓库外 `task-131/offline_cli.py`，仅包装本仓库 main.py 并阻断 Python 层网络；MediaPipe 原生遥测依用户决定允许。参考运行实际位于契约指定目录内的媒体命名子目录，通过搜索定位，不重建对照。
- **范围外改动**：无；仓库外日志/比较脚本属于执行证据。**待用户决定（C 级）**：无。

### 2026-10-17 实施与验证完成（Codex）

- **实现提交**：`8deeb4254f98732e398d1c91240f04ce49a66f90` — `Switch project definitions and guides to Gazelle-next`，已推送。10 个文件：两份环境定义、AGENTS.md、四份用户文档、两份 HANDOFF 与文档测试；`environment_1.0.yml`、运行时代码、两个 Conda 环境均未改动。
- **版本核对**：以新解释器运行正则读取 `environment.yml` 的固定版本，再逐一比较 `importlib.metadata.version`，15/15 相等，退出 0；完整输出在仓库外 `gazelle_runs/task-137/gazelle-task137-version-import.log`：

  | 包 | 声明 = 实际 |
  | --- | --- |
  | torch / torchvision | 2.14.1+cu130 / 0.29.1+cu130 |
  | timm / numpy / scipy / pandas | 1.0.30 / 2.5.4 / 1.18.1 / 2.3.3 |
  | matplotlib / scikit-learn / pillow | 3.11.2 / 1.9.1 / 12.3.0 |
  | opencv-python / opencv-contrib-python | 5.0.0.93 / 5.0.0.93 |
  | mediapipe / trackers / supervision / av | 1.1.1 / 2.6.1 / 0.30.9 / 19.0.1 |

- **导入/回退**：AST 扫描全部 72 个 Git Python 源文件，逐个 `find_spec` 检查第三方导入，仅训练脚本 wandb 缺失，符合契约。修改前 `environment.yml` 与复制所得 `environment_py311.yml` 的磁盘字节 SHA-256 均为 `f95e4f783db353b0ea1438e346800a920317e02630a5a59e1194b5bc06f1e551`；未通过文本重写生成回退文件。
- **离线门**：以下命令均使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，`PYTHONPYCACHEPREFIX=%TEMP%\gazelle-task-137-pycache`：`--version`、`-m pip check`、`-m unittest tests.test_usage_docs -v`（19 项）、`-m compileall main.py gazelle tests tools`、`-m unittest discover -s tests -v`（**563 项，4.327 s，无 skip**）、`main.py --help`、`main.py --list-models`，全部退出 0。`git diff --check` 退出 0；文档 UTF-8 与代码围栏检查通过。新增环境文档测试与激活命令测试先在旧文档失败（2 failures，退出 1），再通过。日志均复制到 `gazelle_runs/task-137/`。
- **真实命令**：新解释器运行仓库外 `gazelle_runs/task-131/offline_cli.py`（包装本仓库 `main.py`），共用参数 `--input E:\Gazelle_Workdata\秋田大学様解析用動画\20260911\20260911表情解析用カメラ1-1.mp4 --max-frames 300 --device cuda --cache-dir C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle\models`，三次分别追加：
  1. `--head-source static --bbox 0.35 0.25 0.55 0.55 --bbox-format normalized --output-dir C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-137\static`；
  2. `--head-source mediapipe --max-heads 1 --output-dir C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-137\mediapipe`；
  3. `--head-source mediapipe --max-heads 1 --save-rendered --video-codec avc1 --output-dir C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-137\mediapipe_avc1`。
- **真实结果**：三次均退出 0，读取/写出各 300 帧，decode_complete=true，299 container + 1 repaired。static 状态全 ok；MediaPipe observation 为 299 ok/1 no_head，prediction 为 73 ok/226 no_gaze/1 no_head。新解释器运行仓库外 `task-137/compare_smoke.py` 退出 0：前两次两份 JSONL 各 300 行，去除 `inference_ms` 与 `timings_ms` 后所有字段与指定 Claude 对照完全相等；in/out 最大差 0，峰值全相等。耗时中位数（跳过首帧）static 98.265 ms、MediaPipe 97.321 ms，仅作记录。`comparison.json` 保留逐项核对结果。
- **H.264**：第三次运行前显存 5809/16376 MiB、利用率 45%，没有其他训练 Python 进程。`ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=codec_name,profile,pix_fmt,width,height,nb_frames,nb_read_frames,duration,r_frame_rate -of json <rendered.mp4>` 退出 0：h264/Main/yuv420p、3840×2160、20 fps、15 秒、声明与实际读取均 300 帧，文件 4,122,016 字节。输出目录仅两份 JSONL、run_config.json、rendered.mp4，无编码临时文件。
- **外部活动与 warnings**：真实 Gazelle/DINOv2 CUDA 推理、MediaPipe CPU 感知、OpenCV 解码、第三次真实 FFmpeg 编码和 ffprobe 解码计数；三次都记录 `Using cache found`，每次 Python 网络审计阻断一次 `urllib.Request`，Torch Hub 成功回退本地缓存。Python 审计不覆盖 MediaPipe 原生网络；其遥测按用户决定允许，不声称整个进程完全离线。未下载模型、未安装/卸载/修改包、未上传数据。非致命输出有 xFormers not available、LiteRT 对齐重分配、NORM_RECT/IMAGE_DIMENSIONS 提示；离线门仍有既有 OpenCV `moov atom not found` 与 Git LF/CRLF 提示。
- **失败/修正的操作**：初次读取对照 run_config 错把父目录当运行目录，查找实际媒体子目录后成功；一次辅助 JSON 读取未指定 UTF-8，遇到 cp932 解码失败，显式 UTF-8 后成功；一次批量文档读取超过工具输出上限，改为读取待编辑段落。均未影响或覆盖对照、原始媒体或环境。
- **反证式复核**：检查实际依赖元数据发现并保留 pydeprecate/defusedxml 的事实偏差；确认所有当前示例均激活新环境，旧名只出现在回退描述；AGENTS diff 只涉及以下环境句子；没有改训练说明与运行时代码。独立审查仍待 Claude，不把主线程自查计为验收通过。
- **状态**：已实际运行、主线程复现；ready-for-review。B 级问题见上节，其他 A 级为命令定位与输出读取修正；无其他范围外改动，无 C 级问题。真实 smoke 与本任务离线门均未跳过。继续 TASK-123 修复。

#### AGENTS.md 逐句变更核对

下表中省略号后的原有句子完全保留；Git diff 与环境段落对照已检查，与环境无关的文本一致。

| 修改前 | 修改后 |
| --- | --- |
| The preferred environment is the existing Conda environment `Gazelle`. | The preferred environment is the existing Conda environment `Gazelle-next`. |
| `C:\Users\yun\anaconda3\envs\Gazelle\python.exe` | `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe` |
| On another machine, discover and verify the existing `Gazelle` interpreter; do not create directories to mimic the old path. | On another machine, discover and verify the existing `Gazelle-next` interpreter; do not create directories to mimic the old path. |
| Do not create, update, prune, install into, or otherwise modify the real `Gazelle` environment without explicit user approval. | 同句仅将环境名改为 `Gazelle-next`。 |
| For a proposed dependency upgrade, first clone the existing `Gazelle` environment into a disposable sandbox, test imports and repository behavior there, report exact versions and conflicts, and wait for approval before applying the validated transaction to the real environment. | 同句仅将环境名改为 `Gazelle-next`。 |
| 无 | The existing `Gazelle` environment is retained as a rollback, described by `environment_py311.yml`, and also must not be modified without explicit approval. |
| `environment_1.0.yml` is the retained rollback/reference definition. | `environment_py311.yml` is the previous Python 3.11 rollback definition; `environment_1.0.yml` is the older NumPy 1.26 reference definition. |
| Use the existing `Gazelle` interpreter for the full offline gate: | Use the existing `Gazelle-next` interpreter for the full offline gate: |
| Run real image/video smoke tests only in the existing `Gazelle` environment. | Run real image/video smoke tests only in the existing `Gazelle-next` environment. |

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：
