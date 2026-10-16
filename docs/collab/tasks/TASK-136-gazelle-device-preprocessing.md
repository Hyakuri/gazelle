# TASK-136：Gazelle 输入预处理移到推理设备

状态：ready（用户 2026-10-17 同意 D17；排在第 3 轮开头）
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
