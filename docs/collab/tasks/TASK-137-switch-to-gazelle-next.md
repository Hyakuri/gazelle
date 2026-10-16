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

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：
