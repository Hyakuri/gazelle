# TASK-136：Gazelle 输入预处理移到推理设备

状态：accepted（2026-10-17 第 3 轮审查）
创建：2026-10-17（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：Claude，之后用户在独立 checkout 验收
依据：[候选环境评估](../evidence/2026-10-17-env-next-evaluation.md) §5.3、§5.4；问题登记表 GZ-25。
授权：2026-10-14 本地修改与本地运算授权；作业数据只读；2026-10-17 用户同意 D17。

## 1. 契约

### 目标

`GazellePredictor.predict_frame` 目前在 CPU 上处理整帧图像：先转成浮点张量（ToTensor），再归一化（Normalize），最后缩放到 448×448（带抗锯齿的 Resize）。4K 输入下，这一步占每次调用的一半以上。

改为：把 uint8 RGB 帧拷贝到模型所在设备，在设备上按相同顺序完成同样的运算。接口、输出格式与数值语义不变。

评估中的管线级实测（`Gazelle-next`，4K，300 帧，仓库外探针替换预处理，其余代码不变）：

| 头部来源 | 现有做法 | 设备上预处理 | 输出差异 |
| --- | --- | --- | --- |
| 静态头框 | 98.9 ms | 41.1 ms（可写复制）；35.8 ms（只读数组） | in/out ≤ 1.8e-4，峰值与状态 300/300 一致 |
| MediaPipe | 95.6 ms | 47.9 ms（可写复制） | in/out ≤ 6e-5，峰值、状态与 `gaze_eligible` 一致 |

### 必须实现

1. **识别标准变换（只看结构）**：
   - `self.transform` 是 `torchvision.transforms.Compose`，且其 `transforms` 依次恰好为 `ToTensor`、`Normalize`、`Resize` 三个实例时，走新路径。这与 `gazelle/backbone.py` 中 `DinoV2Backbone.get_transform` 的构造方式一致。
   - 参数不写死，也不另作比较：新路径直接调用这个 Compose 里的 Normalize 与 Resize 对象处理设备上的张量。它们对张量执行的就是原路径中的同一运算。
   - 其他变换一律走原路径，包括测试中的假变换。
   - `transform` 是可以替换的公开属性。每次调用时识别（只有几次类型检查），或在 `transform` 对象改变时重新识别，二者任选；替换后的行为必须跟随新的 `transform`。
2. **输入类型**：
   - 新路径接受两类输入：mode 为 `"RGB"` 的 PIL 图像（读取器的实际输入），以及形状为 `[H, W, 3]`、dtype 为 `uint8` 的 numpy 数组。
   - 数组带负步长或不连续（例如 `frame[:, ::-1]`、`frame[..., ::-1]`）时，先转为连续数组，不得报错。
   - 其他输入一律按原路径处理：其他 mode 的 PIL 图像、浮点或其他整数 dtype 的数组、张量。
   - `_frame_to_pil_rgb` 现有的类型检查与错误信息保持不变。
3. **运算顺序与数值**：在设备上依次执行以下三步，输出 `[1, 3, H, W]` 张量，位于模型设备：
   1. uint8 转为浮点再除以 255。dtype 与 ToTensor 相同，即 `torch.get_default_dtype()`，默认 float32。
   2. 调用原 Compose 中的 Normalize 对象。
   3. 调用原 Compose 中的 Resize 对象。

   不得改用其他缩放算法，不得在 uint8 上先缩放，不得改变归一化常数，也不得启用 TF32、bf16 或 autocast。
4. **CPU 设备**：预测器设备为 CPU 时也可以走新路径；运算相同，只是省去 PIL 往返。
5. **只读数组的 warning**：PIL 图像经 `np.asarray` 得到的数组只读，直接交给 `torch.from_numpy` 会发出 UserWarning。以下两种做法任选其一：
   - 先得到可写数组，例如 `np.array(image)`。4K 下每帧多约 5 ms。
   - 在只读数组转张量、并立即拷贝到设备的那一处，用 `warnings.catch_warnings()` 只忽略这一条消息，并注释原因：主机张量只读取，不写入。

   不得全局过滤 warnings。
6. **计时口径不变**：管线的 `inference_ms` 仍从调用 `predict_frame` 前计到返回后，包含预处理。

### 非目标

- 不改 `VideoFrameReader` 产出的帧类型（仍为 PIL 图像），不改渲染器与 MediaPipe 后端；GZ-25 中的整帧复制问题以后另议。
- 不改模型数值精度。
- 不加 CLI 选项，不改 JSON、JSONL 与 `run_config.json` 的字段，不改 `GazellePredictor` 的公开构造参数。

### 依据材料

- `gazelle/runtime/predictor.py`（`predict_frame`、`_frame_to_pil_rgb`）。
- `gazelle/backbone.py`（`get_transform`）。
- `tests/test_predictor.py`。
- 评估记录 §5.3、§5.4。仓库外的探针脚本 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\env-next\pipeline_patch_probe.py` 只作参考，不要复制进仓库。

### 不可变约束

AGENTS.md 的运行时不变量、研究与数据完整性要求、默认测试隔离。默认测试不需要 CUDA，也不构造真实 DINOv2。

### 允许动作

- 修改 `gazelle/runtime/predictor.py` 与对应测试。
- 在 `Gazelle-next` 环境中运行离线门，以及验收标准第 3、4 条的真实 smoke。只用本地缓存，不下载。
- 按协作方案 §4 提交、推送，并在 PR #6 发英中双语评论。
- 问题处理按协作方案 §3.5。

### 禁止

- 协作方案 §3.5 的硬边界。
- 修改任何 Conda 环境，包括作为回退保留的 `Gazelle`。
- 写入源数据目录，提交媒体或运行产物。

### 验收标准

1. **新增测试**（默认离线，只用 CPU）：
   - **标准变换识别**：真实的 `Compose([ToTensor(), Normalize(...), Resize((448, 448))])` 能被识别。以下情况不识别：少一项、多一项、顺序不同、假变换。
   - **替换变换**：构造后把 `transform` 换成假变换，调用走原路径；再换回标准变换，又走新路径。
   - **等价性**：随机 uint8 RGB 帧在 CPU 上新旧两条路径的模型输入最大差 ≤ 1e-5。帧尺寸至少包含 37×53 与 480×640；PIL 与 numpy 两种输入都要覆盖。
   - **步长**：`frame[:, ::-1]` 与 `frame[..., ::-1]` 正常处理，结果与对同一数组先做 `np.ascontiguousarray` 再走原路径一致。
   - **回退**：L 与 RGBA mode 的 PIL 图像、float 数组、uint16 数组、张量输入都走原路径，结果与修改前一致。
   - **模型输入**：形状为 `[1, 3, 448, 448]`、dtype 为 float32，位于预测器设备；调用方的帧对象没有被修改。
   - **warnings**：先调用 `torch.set_warn_always(True)`，测试结束后恢复原值。否则 PyTorch 的同类 warning 在每个进程只出现一次，会被其他测试提前触发。然后用 `warnings.catch_warnings(record=True)` 断言新路径不产生 warnings。
2. **离线门**：完整离线门通过，无新增 skip。
3. **真实 smoke**（CUDA，`Gazelle-next` 环境，本地缓存）：
   - 输入：右侧摄像机 2026-09-11 第 1 段，即 `E:\Gazelle_Workdata\秋田大学様解析用動画\20260911\20260911表情解析用カメラ1-1.mp4`。
   - 参数：`--head-source static --bbox 0.35 0.25 0.55 0.55 --bbox-format normalized --max-frames 300 --device cuda`，输出写到仓库外。
   - 对照：修改前的提交与修改后的提交各运行一次，在同一时段内连续运行。
   - 门槛：
     - 300 帧逐帧状态一致；
     - in/out 最大差 ≤ 1e-3；
     - JSONL 中的热图峰值坐标逐帧一致；
     - `inference_ms` 中位数至少降低 40%。评估实测为 98.9 → 41.1 ms（可写复制）或 35.8 ms（只读数组）。
   - 报告：两次运行的中位数、p90 与首帧耗时。
   - 另外用 `--head-source mediapipe --max-heads 1 --max-frames 300` 各运行一次，只报告相同的比较项，不设门槛。评估实测为 95.6 → 47.9 ms。
4. **1080p 代理**：若届时已有 TASK-134 生成的 1080p 同步代理视频，在一段代理上重复第 3 条的 static 比较，只报告数字，不设门槛。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-136-pycache"
& $py -m unittest tests.test_predictor -v
& $py -m compileall main.py gazelle tests tools
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是。涉及模型输入路径与数值语义。
- 需真实运行：是，即第 3 条的 CUDA smoke，使用本地缓存。
- 文档同步：预计不需要，因为接口、输出格式与数值语义不变。请检索四份用户文档中关于预处理或 `inference_ms` 的描述，若有与新实现不符之处，一并更新。在实施报告与 PR 评论中说明结论与原因。
- 依赖：TASK-137 已完成（在 `Gazelle-next` 中开发与测试）。排在第 3 轮开头、TASK-102 之前，让第 3 轮的真实运行都使用新路径。阶段 2 验收中的修复前基线（`bbec056`）仍是原路径；两者的预处理差异约 2e-4，远小于修复本身带来的变化，比较时注明即可。

## 2. 实施报告（Codex 追加，不要修改上文）

### 2026-10-17 实施与验证

- 接手：STATE 从 TASK-138 推进，writer/next_actor 均为本轮 Codex；基线 `d767dba62bcf4218656a9246d1dfaf5322deaab2`，分支不变。
- 实现：`04096c4e2cdae8a2b7a8a5e23207b90abc750f88` — `Preprocess standard Gazelle RGB inputs on the model device`。本报告随独立提交普通推送到 PR #6。
- 仅改 `gazelle/runtime/predictor.py` 和 `tests/test_predictor.py`。每次识别标准三步 Compose，uint8 先拷贝到模型设备，再按默认 dtype 转换、除以 255、调用原 Normalize/Resize；非标准变换及其他输入保留原路径。PIL 使用可写复制，非连续/只读数组安全复制，无全局 warning 过滤。计时边界未改。

所有 Python 均使用 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`，字节码放 `%TEMP%\gazelle-task-136-pycache`。外部证据根为 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-136`。

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.test_predictor.DevicePreprocessingTest -v`（修改前） | exit 1，5 methods / 5 预期失败：新路径仍调用 legacy 转换 |
| `python -m unittest tests.test_predictor -v` | exit 0，31 tests / 0.189s / 0 skip |
| `python -m compileall main.py gazelle tests tools` | exit 0，日志 `compile.log` |
| `python -m unittest discover -s tests -v` | exit 0，616 tests / 9.157s / 0 skip，日志 `unittest.log` |
| `python main.py --help`、`python main.py --list-models` | 均 exit 0 |
| `git diff --check`、准确暂存路径检查 | 通过；仅暂存上述两个文件 |
| `python ...\task-136\smoke.py` | exit 0，6 次真实 CLI 均 exit 0，每次 300 帧 |

离线门在最终 TASK-136 实现和格式整理后运行；之后开始准备 TASK-139 的新测试，不包含在该门或该提交内。非致命输出为既有坏 MP4 的 `moov atom not found`。一次列举不存在的 `workdata\proxy` 路径退出 1，随后确认实际目录是 `proxies`；未改数据。

### CUDA 对照

修改前使用 `git archive d767dba` 导出的仓库外只读基线快照；修改后使用 `04096c4`，未替换模型或 transform。六次顺序执行，真实 argv、退出码与用时见 `commands.json`，数值见 `comparison.json`。4K 输入按契约；1080p 输入为既有 `proxies\20260911\proxy_right.mp4`，仅用于性能 smoke，不宣称旧代理已同步。

命令模板：`python smoke.py cli <baseline-or-repo> --input <input> --output-dir <external-case> --cache-dir <repo>\models --max-frames 300 --device cuda`；静态组加 `--head-source static --bbox .35 .25 .55 .55 --bbox-format normalized`；MediaPipe 组加 `--head-source mediapipe --max-heads 1`。

| 组别 | 推理帧数 | 中位数 ms（前→后） | p90 ms（前→后） | 第 0 帧 ms（前→后） | 中位数降低 | 最大 in/out 差 |
| --- | ---: | --- | --- | --- | ---: | ---: |
| 4K static | 300 | 123.142 → 42.298 | 146.589 → 44.681 | 720.912 → 247.457 | 65.651% | 0.000178397 |
| 4K MediaPipe | 73 | 97.702 → 51.237 | 135.499 → 60.063 | 无推理 → 无推理 | 47.558% | 0.000061065 |
| 1080p static | 300 | 31.314 → 19.972 | 34.147 → 20.802 | 233.525 → 202.220 | 36.219% | 0.000161558 |

三组均 **300/300 帧状态一致、person gaze_status 一致、峰值坐标一致**。MediaPipe 未选头的帧没有 inference_ms，统计只包括 73 次真实推理，没有把其余 227 帧记为零。p90 使用排序后 `floor(.9*(n-1))`；中位数包括首次推理，另在 JSON 保留去掉首个推理的中位数。4K static 的全部硬门槛通过。

### 活动、复核与决定

- 真实 RTX 4080 SUPER / driver 617.14 / Gazelle-next / CUDA；启动前空闲 10211 MiB、使用率 9%，后续各启动也检查显存和占用。未改 TF32、autocast、dtype 或环境。MediaPipe 使用既有 CPU 配置。
- Python 网络 audit 拦截每次 Torch Hub 的 `urllib.Request` 尝试，随后复用已有 DINOv2 与 Gazelle 缓存。六次均记录 `NETWORK_AUDIT=["urllib.Request"]`。缓存全部文件 size/mtime 前后相同，无下载；audit 不覆盖 MediaPipe 原生库的潜在遥测，不将其描述为网络绝对隔离。xFormers 三项不可用 warning 保留。未调用真实 FFmpeg 可执行程序；视频由运行时解码，无渲染编码。
- 反证复核：37×53 与 480×640、RGB PIL/numpy、负步长、只读、float64 默认 dtype、Normalize inplace、自定义 Resize、公开 transform 替换均覆盖。非 RGB 与非 uint8 继续原转换，没有强行纳入优化；无头仍不调用变换或模型。
- A 级决定：采用可写数组复制，避免只读 warning；每次检查 transform 结构，以保证公开属性替换立即生效。只读基线是已提交源码快照，非新增开发 checkout 或分支。
- 四份用户文档已检索预处理和 inference_ms；没有声称 CPU 预处理的内容，接口、schema、数值语义与计时口径均未改，故不需要修改用户文档。
- 范围外改动：无。C 级待决：无。B 级：请 Claude 独立审查输入数值边界及复跑 CUDA；自审与实际 smoke 不等同独立验收。
- 无未执行的契约检查；性能只代表此次连续运行条件，不是正式基准或科学准确性结论。原始数据只读，媒体、输出与凭证均未上传。

**已实施、已静态检查、已实际运行；待 Claude 独立验收。**

## 3. 审查结论（Claude 追加）

### 2026-10-17 第 3 轮审查（Claude）

- **审查目标**：`04096c4`（实现）与 `1c761c5`（报告），在 HEAD `f0c4311` 上审查。`predictor.py` 此后没有改动。
- **独立复跑结果**：
  - 完整离线门 643 tests，0 skip。
  - 一份只读代码审查（子代理）：`tests.test_predictor` 31 项通过；CPU 探针上，新旧路径对 1080×1920 PIL 图像与数组的输出 `torch.equal`；回退输入完全一致；没有任何 warnings 过滤。
  - **CUDA 对照（Claude）**：
    - 条件：`Gazelle-next`、RTX 4080 SUPER，启动前空闲显存约 12 GB；契约规定的 20260911 右侧摄像机第 1 段，300 帧。
    - 修改前用 `git archive d767dba` 的仓库外快照，修改后用 HEAD。静态头框组新旧交替各跑两次，另跑一组 MediaPipe。
    - Python 网络访问由 audit hook 阻断，Torch Hub 请求被拦截后回退到缓存，无下载。
    - 脚本与日志在 `gazelle_runs\claude-review-r3\t136\`。

    | 组别 | 推理中位数 ms（前→后） | p90 ms（前→后） | 降低 | 状态 / 峰值一致 | in/out 最大差 |
    | --- | --- | --- | ---: | --- | ---: |
    | 4K static 第 1 组 | 121.0 → 42.7 | 148.5 → 46.2 | 64.7% | 300/300、300/300 | 1.78e-4 |
    | 4K static 第 2 组 | 106.5 → 42.7 | 125.2 → 45.5 | 59.9% | 300/300、300/300 | 1.78e-4 |
    | 4K MediaPipe | 125.2 → 50.3 | 136.4 → 65.1 | 59.8% | 299/300 | 6.1e-5 |

    - 第 1 组运行期间，Claude 另有约 1 分钟 CPU 计算，修改前的数值可能偏高；第 2 组没有干扰。两组都高于 40% 的门槛。
    - MediaPipe 组唯一不一致的是第 0 帧：Claude 的“修改后”是 HEAD，已经包含 TASK-102 的首帧确认，所以第 0 帧多一个临时头。这与本任务无关。Codex 的对照只隔离了本任务，300/300 一致。
- **发现**（小项，不阻塞，不另排任务）：
  - 结构识别用 `isinstance`，ToTensor 或 Compose 的子类也会走新路径，契约的本意是“恰好为”；改用 `type(x) is` 更严格。目前 `backbone.py` 只用精确类型，所以没有影响。
  - `test_default_dtype_and_transform_parameters_are_retained` 没有阻断旧路径，抓不到“参数不同而意外回退”的情况。
  - CUDA 上数值不是逐位相同：设备上的除法与抗锯齿核不同，差异 1.8e-4，在 1e-3 门槛内。
- **结论**：**accepted**。按协作方案 §5，GPU 与 CPU 和其他实验共用，性能数字只代表本次条件。
