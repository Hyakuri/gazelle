# Gaze-LLE
#### CVPR 2025 Highlight

有关完整的 runtime 环境设置、全部 CLI 选项、输入/输出 schema 以及可运行的图像/视频工作流，请参阅[项目使用指南](docs/USAGE_CN.md)。

[English README](README.md)

[Gaze-LLE: Gaze Target Estimation via Large-Scale Learned Encoders](https://arxiv.org/abs/2412.09586)
[Fiona Ryan](https://fkryan.github.io/), [Ajay Bati](https://www.linkedin.com/in/abati777/), [Sangmin Lee](https://sites.google.com/view/sangmin-lee), [Daniel Bolya](https://dbolya.github.io/), [Judy Hoffman](https://faculty.cc.gatech.edu/~judy/)*, [James M. Rehg](https://rehg.org/)*

<div style="text-align:center;">
    <img src="./assets/office_gif.gif" height="300"/>
</div>

本仓库是 Gaze-LLE 的官方实现。Gaze-LLE 是一种基于 Transformer 的 gaze target estimation 方法，用于预测人物正在看的目标区域。它利用冻结的预训练视觉基础模型 DINOv2 作为图像编码器，只训练一个轻量 gaze decoder，因此相比很多旧方法需要学习的参数更少，也不依赖深度图、人体姿态等额外输入。

<div style="text-align:center;">
    <img src="./assets/gazelle_arch.png" height="200"/>
</div>

## 文档维护约定

之后新增用户可见功能、脚本、CLI 参数、环境依赖、模型下载方式、输出格式、推理接口或与 Multi-Pose 的集成说明时，请同时更新 `README.md` 和 `README_CN.md`。命令示例应默认从仓库根目录执行，并明确说明命令是否会下载权重、打开界面、训练模型、执行推理、使用 CUDA、写入输出文件，或只是进行安全的 import/CLI 验证。如果某次纯代码改动不需要更新 README，需要在开发报告或 PR comment 中明确说明原因。

## 项目能力概览

- 输入一张场景图像，以及一个或多个人的头部 bounding box。
- 对每个人输出 gaze heatmap，即画面中该人物可能正在看的区域。
- 对带 `inout` head 的模型，还会输出视线目标是否在画面内的概率。
- 多人推理时，场景图像只编码一次，再针对多个 head box 预测 gaze heatmap。
- 预训练模型基于 DINOv2 backbone，checkpoint 中只包含 Gaze-LLE decoder 权重；DINOv2 backbone 会由 PyTorch Hub 加载。

## 安装方式

`environment.yml` 是当前推荐使用的 Gazelle 环境定义，记录了这次已经验证的 NumPy 2.4.6 依赖栈，包括 Python 3.11、PyTorch 2.6.0 + CUDA 12.6 wheels、xFormers 0.0.29.post3、MediaPipe 0.10.35，以及生产 ByteTrack 依赖 `trackers==2.5.0.post0`、`supervision==0.29.1`，并保留了本次验证事务中的 `ultralytics==8.4.104`。

`environment_1.0.yml` 保留了之前的 NumPy 1.26.4 配置，可用于回滚或对照。两个 YAML 文件里的环境名都声明为 `Gazelle`，因此同一时间只应创建一个名为 `Gazelle` 的环境。

当前正常工作流仍然是激活已经验证过的 `Gazelle` 环境：

```powershell
conda activate Gazelle
pip install -e .
```

如果是在全新机器上配置当前推荐环境，请使用 `environment.yml`：

```powershell
conda env create -f environment.yml
conda activate Gazelle
pip install -e .
```

如果你需要把旧版 NumPy 1.26.4 环境作为并行对照保留下来，请在创建 `environment_1.0.yml` 时显式覆盖环境名：

```powershell
conda env create -f environment_1.0.yml --name Gazelle-1.0
```

激活 `Gazelle` 后，建议先运行以下命令验证 CLI，并准备默认本地模型缓存：

```powershell
python main.py --help
python main.py --list-models
python main.py --prepare-only --model gazelle_dinov2_vitb14_inout --cache-dir models
```

`--help` 和 `--list-models` 不会下载模型，也不会运行推理。`--prepare-only` 首次运行时可能下载 Gazelle checkpoint、DINOv2 PyTorch Hub 仓库和 DINOv2 权重；再次运行相同命令时应复用 `models/checkpoints` 和 `models/torch_hub` 中已有的缓存。

## 预训练模型

官方提供以下预训练模型：

| 名称 | Backbone 类型 | Backbone 名称 | 训练数据 | Checkpoint |
| ---- | ------------- | ------------- | -------- | ---------- |
| `gazelle_dinov2_vitb14` | DINOv2 ViT-B | `dinov2_vitb14` | GazeFollow | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitb14.pt) |
| `gazelle_dinov2_vitl14` | DINOv2 ViT-L | `dinov2_vitl14` | GazeFollow | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitl14.pt) |
| `gazelle_dinov2_vitb14_inout` | DINOv2 ViT-B | `dinov2_vitb14` | GazeFollow -> VideoAttentionTarget | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitb14_inout.pt) |
| `gazelle_dinov2_vitl14_inout` | DINOv2 ViT-L | `dinov2_vitl14` | GazeFollow -> VideoAttentionTarget | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitl14_inout.pt) |
| `gazelle_dinov2_vitb14_inout_childplay` | DINOv2 ViT-B | `dinov2_vitb14` | GazeFollow -> ChildPlay | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitb14_inout_childplay.pt) |
| `gazelle_dinov2_vitl14_inout_childplay` | DINOv2 ViT-L | `dinov2_vitl14` | GazeFollow -> ChildPlay | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitl14_inout_childplay.pt) |

这些 Gaze-LLE checkpoint 只包含 gaze decoder 权重，不包含 DINOv2 backbone 权重。DINOv2 权重会在创建模型时通过 PyTorch Hub 从 `facebookresearch/dinov2` 加载。

GazeFollow 模型输出 `[0, 1]` 范围内的空间 heatmap，数值越高代表该位置越可能是 gaze target。经过 VideoAttentionTarget 微调的 `inout` 模型还会输出 `[0, 1]` 范围内的 in/out score，其中 `1` 表示视线目标在画面内。

## PyTorch Hub 使用方式

可以通过 PyTorch Hub 直接加载模型：

```python
model, transform = torch.hub.load("fkryan/gazelle", "gazelle_dinov2_vitb14")
model, transform = torch.hub.load("fkryan/gazelle", "gazelle_dinov2_vitl14")
model, transform = torch.hub.load("fkryan/gazelle", "gazelle_dinov2_vitb14_inout")
model, transform = torch.hub.load("fkryan/gazelle", "gazelle_dinov2_vitl14_inout")
```

如果希望使用本 fork 版本，请优先从源码路径导入，并显式加载 checkpoint。

## 统一 Runtime 入口预览

本项目正在围绕原始研究模型增加统一的本地 runtime。新的入口是：

```powershell
python main.py --help
```

当前 runtime 已提供安全的 CLI / 模型注册表检查、资源准备、单张图片推理，以及离线视频推理：

```powershell
python main.py --list-models
```

`--help` 和 `--list-models` 不会构建 DINOv2 backbone，不会下载 Gazelle checkpoint，不会访问 PyTorch Hub，不会执行图片或视频推理，不会启动摄像头，不会使用 CUDA 执行模型计算，也不会写入输出文件。它们只用于验证本地 CLI 层，并打印当前注册的模型元数据。

当前 runtime registry 只列出 `gazelle/model.py` 目前实际可以构建的四个模型：

- `gazelle_dinov2_vitb14`
- `gazelle_dinov2_vitl14`
- `gazelle_dinov2_vitb14_inout`
- `gazelle_dinov2_vitl14_inout`

`gazelle_dinov2_vitb14` 默认使用 README 中的 `gazelle_dinov2_vitb14.pt`。开发 runtime 时已经验证过旧 `hubconf.py` 文件名 `gazelle_dinov2_vitb14_hub.pt`，它可以 strict load，且与 README checkpoint 字节完全一致。

### 资源准备

使用 `--prepare-only` 可以只准备本地模型资源，不执行图片或视频推理：

```powershell
python main.py --prepare-only --model gazelle_dinov2_vitb14_inout
```

该命令可能下载 Gazelle checkpoint，并且会通过 PyTorch Hub 构建 DINOv2 backbone。如果本地没有 DINOv2 缓存，构建 DINOv2 时可能下载 DINOv2 权重。传入 `--head-source mediapipe` 时，它还会准备所选的官方 MediaPipe task 资源。它不会处理图片、处理视频、打开摄像头、渲染输出，也不会写入 JSON/JSONL 预测结果。

成功时，该命令会输出解析后的 checkpoint 路径、`checkpoint_source`、缓存根目录、Torch Hub 缓存目录，以及注册 checkpoint 候选的 strict-load 校验信息。使用 `--checkpoint` 时，`checkpoint_source` 为 `local`；使用 runtime 注册 checkpoint 时，`checkpoint_source` 为对应候选来源。准备 MediaPipe 资源时还会输出 face detector、face landmarker、所选 pose landmarker 和 pose model。

缓存根目录优先级：

1. `--cache-dir`
2. `GAZELLE_CACHE_DIR`
3. `models`

runtime 使用以下目录结构：

```text
models/
├── checkpoints/
├── mediapipe/
└── torch_hub/
```

如果希望使用本地 checkpoint，并跳过注册 checkpoint 下载，可以指定：

```powershell
python main.py `
  --prepare-only `
  --model gazelle_dinov2_vitb14_inout `
  --checkpoint C:\path\to\gazelle_dinov2_vitb14_inout.pt
```

如果希望刷新已缓存的注册 checkpoint 和所选 MediaPipe 资源，可以使用 `--force-download`：

```powershell
python main.py `
  --prepare-only `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models `
  --force-download
```

为了避免下载失败导致旧缓存丢失，强制下载会先写入相关缓存下的临时 `.downloads` 目录。只有新文件下载完成并通过校验后，runtime 才会替换旧文件。如果下载或校验失败，已有缓存文件会被保留。

runtime 路径中的 checkpoint 校验是严格的：空 state dict、缺失 key、额外 key、tensor shape 不一致、非 tensor 值、checkpoint 顶层结构不兼容都会让准备流程报错停止。

### 单张图片推理

runtime 现在可以对一张图片执行 Gazelle 推理，并写出结构化结果：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source none `
  --model gazelle_dinov2_vitb14_inout
```

该命令会加载图片、创建输出目录、收集 head observation，并写入类似 `outputs/frame_gazelle/` 的单图输出目录，其中包含 `head_observations.json`、`predictions.json` 和 `run_config.json`。只有当 head provider 返回至少一个 head 时才会构建 Gazelle 模型和 DINOv2 backbone；如果所选 Gazelle checkpoint 或 DINOv2 权重尚未缓存，该预测路径可能访问网络并下载它们。图片输入不会打开摄像头，也不会写入视频 JSONL；视频输入由下方的视频推理路径处理。

使用 `--overwrite` 时，runtime 会在写入新结果前清理对应图片的输出目录，因此旧的 heatmap 或 rendered image 不会残留。

head 输入来源：

- `--head-source none` 会创建一个单人 fallback head，bbox 为 `None`。
- `--head-source static` 使用命令行传入的一个或多个 bbox：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source static `
  --bbox 0.10 0.12 0.22 0.30 `
  --bbox-format normalized
```

`--bbox` 可以重复传入以支持多人。`--bbox-format normalized` 表示 `[0, 1]` 归一化坐标，`--bbox-format pixel` 表示图片像素坐标。`--person-id` 可以重复传入，并且数量必须与 `--bbox` 一致；不传时 person id 默认为 `0, 1, 2, ...`。

- `--head-source json` 从 JSON 中读取单图 head 数据：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source json `
  --head-data samples\frame_heads.json
```

### MediaPipe Provider 组合（分阶段）

CLI 接受 `--head-source mediapipe`，并校验 MediaPipe 运行时设置：`--max-heads` 接受 `1` 到 `10`（默认 `1`）；`--pose-model` 接受 `lite`、`full` 或 `heavy`（默认 `full`）；`--head-track-max-gap-ms` 接受大于 `0` 的有限毫秒值（默认 `500.0`）；`--save-face-landmarks` 启用人脸关键点输出配置（默认关闭）。`--face-pose-ray` 与 `--pose-head-ray` 可分别渲染两条无相机标定的 2D head-direction reference，`--reference-ray-length` 控制长度。`--gazelle-head-mode` 选择哪些 MediaPipe perception 可以进入 Gazelle，`--gaze-inout-threshold` 将结果分类为 `valid` 或 `out_of_frame`，`--gaze-render-mode` 则独立控制是否绘制 out-of-frame Gazelle geometry。

使用以下命令准备官方 face detector、face landmarker 和一个所选 pose landmarker，而不执行推理：

```powershell
python main.py `
  --prepare-only `
  --head-source mediapipe `
  --pose-model full
```

pose 选项会分别准备 `pose_landmarker_lite.task`、`pose_landmarker_full.task` 或 `pose_landmarker_heavy.task`。只有当 `<cache-root>/mediapipe` 中已有的资源是普通文件，并且 SHA-256 与对应版本化官方 URL 的固定摘要一致时，才会复用该资源；被篡改、截断或不是文件的缓存项会明确报错，绝不会作为有效路径返回。新资源或强制刷新资源在检查或修改临时 `.downloads/<asset-key>` 目录之前，会以原子方式获取 `.downloads/<asset-key>.lock`；同一资源的并发准备会在不触碰该暂存目录的情况下失败，并明确说明已有缓存项已保留。资源下载到暂存目录后，会先通过校验，再以原子方式移动到缓存中。初始化、加锁、下载、文件缺失、摘要校验或替换失败时，已有缓存项都会保留。任务目录和锁采用 best-effort 清理，范围严格限制在经过校验的下载目录内，并且清理失败不会掩盖资源准备的主要结果。无法确认所有权的锁不会被自动删除，因为它可能属于仍在运行的进程；手动删除陈旧锁之前，必须先确认没有进程正在准备该资源。

默认单元测试使用 fake downloader，不访问网络。注册表中的固定摘要只在建立时进行过一次真实校验：将恰好五个官方版本化资源下载到仓库外的 OS 临时目录，计算 SHA-256，然后删除该临时目录。

`--head-source mediapipe` 现已接入 runtime head provider 工厂。provider 会组合已准备的资源、MediaPipe backend、head/pose fusion；视频还会使用 ByteTrack 跟踪和 500 ms 的短时遮挡桥接。图片 ID 确定且从零开始，视频 ID 来自 ByteTrack。单人模式会在 bridge 后再次裁决，最多保留一个 identity，并清除被当前 observation 替换的 stale identity。默认情况下，只有通过保守 gaze eligibility 的当前 MediaPipe head bbox 才会送入 Gazelle，其中 perception confidence 与 face-ray confidence 均不得低于 `0.50`。

该集成刻意保持较小的模型边界：fusion/tracking 会生成有序 `HeadObservation` 和对齐的 `HeadPerception`。默认 `--gazelle-head-mode eligible` 只传入保守 eligible head。诊断 selector 可以改为一个或多个 state（`face_pose`、`face_only`、`pose_only`、`tracked_only`）或 view（`frontal`、`profile`、`back_or_occluded`、`unknown`）；`observed` 选择当前 observation，`all` 选择全部 active perception，多个 selector 采用 OR 语义。即使处于诊断模式，也不能恢复已经过期的 track，并且仍然要求通过 normalized non-`None` bbox 校验。face bbox、face mesh、face/pose keypoint、两条 head-pose reference ray、head pose 和 tracking state 永远不会加入 Gazelle tensor input。Gazelle 按选中的 person 顺序返回结果。

当前 `environment.yml` 中声明的依赖集合已经用真实 MediaPipe 0.10.35、通过 `trackers==2.5.0.post0` 接入的生产 ByteTrack、Gazelle/DINOv2 CUDA 单图推理，以及一段短视频渲染流程完成验证。因此，本文档现在将这个 NumPy 2.4.6 环境视为当前分阶段 runtime 的推荐端到端配置。这里不宣称已经验证可选的 Ultralytics YOLO 模型推理或导出能力。

runtime 会在延迟导入 ByteTrack 时精确过滤 upstream `trackers` 的 `target=None` 弃用 warning，其他 `FutureWarning` 仍会正常显示。常规 CUDA 图片/视频推理会先解析 checkpoint 而不构建 DINOv2，然后只构建一次启用 xFormers 的 predictor。如果可选 Triton 不存在，并且用户没有设置 xFormers Triton override，模型构建期间会临时使用官方 `XFORMERS_FORCE_DISABLE_TRITON=1` 开关；这只跳过无效的 Triton 探测，不会关闭其他 xFormers operator，也不会修改 Conda 环境。`--prepare-only` 为了 strict-load 校验仍会有意关闭 xFormers，因此该路径上仍可能看到 DINOv2 非致命的 xFormers-disabled/not-available 状态 warning。由于 DINOv2 会在首次 import 时缓存 backend 选择，长生命周期 Python 进程若随后请求不兼容的 CPU/prepare-only 与启用 xFormers 的 CUDA 构建，现在会明确失败，而不是静默复用错误 backend；切换 backend mode 时应启动新进程。

### 独立 Head Observation Schema

`gazelle.runtime.perception.outputs` 提供 `head_frame_to_json_dict(...)`，用于序列化单个独立 provider 结果。图片 pipeline 使用 `write_head_observations_json(output_path, **frame_kwargs)` 创建父目录，并写入恰好一个带缩进且末尾换行的 JSON 文档。视频 pipeline 会把每个序列化 provider 结果写成一行紧凑的 `head_observations.jsonl`。record 恰好包含 `frame_index`、`timestamp_ms`、`status`、`width`、`height`、`provider`、`timings_ms` 和 `people` 字段。结果存在 head 时 `status` 为 `"ok"`，否则为 `"no_head"`。`timings_ms` 保留 provider 的 timing 名称及有限的毫秒数值。

每个人包含 `person_id`、`head_bbox_normalized` 和 `confidence`。rich MediaPipe perception 还会包含保守建议 `gaze_eligible`、实际逐帧推理决定 `gazelle_selected`、可选 rejection `gaze_status`、具名 pose-head keypoint，以及可用的两条 reference ray。face reference 使用 Face Landmarker pose 与 face keypoint；pose reference 由可靠的 Pose Landmarker nose/eye 或 nose/ear geometry 独立估计。两者都是无标定 2D reference，并非真实 eye gaze。

每次单图运行都会在 gaze 推理前写入独立 observation；视频帧也先写 observation，再写 gaze。默认情况下，`tracked_only` 只维持 bbox continuity，并使用 `gaze_status="tracked_no_gaze"`；只有在 active bridge track 尚未过期时，显式使用 `tracked_only` 或 `all` 诊断 selector 才会把它送入 Gazelle。`pose_only` 与背脸/遮挡即使被显式选择，也仍保留其保守状态。bridge 不会复制旧 face evidence 或两条 reference ray。

出于隐私和输出体积考虑，默认省略全部 478 个 face landmark。传入 `--save-face-landmarks` 后才会在图片 `head_observations.json` 或视频 `head_observations.jsonl` 中包含它们；这会显著增加输出体积，并保留更多生物特征细节。

单图推理会读取 `frame_index=0` 的 head 数据。JSON 使用 runtime head provider 的内部 record 格式，`bbox_format` 可以是 `normalized` 或 `pixel`，`heads` 中包含 `person_id`、`bbox` 和可选 `confidence`。

`--head-source none` 不提供 bbox。因此渲染时无法绘制 head bbox，也无法计算从 head center 到 gaze peak 的箭头。如果需要 bbox / arrow，请使用 `--head-source static` 或 `--head-source json` 并提供 bbox。

使用 `--save-heatmaps` 可以保存每个人的 raw heatmap tensor：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source none `
  --save-heatmaps
```

raw heatmap 会保存在单图输出目录的 `heatmaps/` 下，并在 `predictions.json` 中以路径引用。heatmap 不会直接写入 JSON，`heatmap_peak_value` 也不应被理解为校准后的概率。

使用 `--save-rendered` 可以保存可视化 overlay 图片：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source static `
  --bbox 0.10 0.12 0.22 0.30 `
  --bbox-format normalized `
  --save-rendered
```

默认情况下，单图推理会写入 `head_observations.json`、`predictions.json` 和 `run_config.json`；只有传入 `--save-rendered` 时才会写可视化图片。默认文件名是 `rendered.png`。可以用 `--rendered-name` 指定 `.png`、`.jpg` 或 `.jpeg` 文件名，用 `--heatmap-alpha` 控制 heatmap 透明度。gaze overlay 可以包含 heatmap、需要显式开启的 Gazelle prediction bbox、在存在 bbox 时从 head bbox 中心指向 gaze peak 的箭头、gaze target peak 位置的红色 X、稳定的 per-person 颜色，以及包含 `person_id`、可选 `inout_score` 和 `heatmap_peak_value` 的 label。Gazelle prediction bbox 默认不绘制；如果 bbox 可用并希望显示它，请传入 `--head-box`。可以用 `--no-heatmap`、`--no-gaze-arrow`、`--no-gaze-peak` 或 `--no-labels` 关闭对应绘制元素。可以用 `--draw-heatmap-contour` 绘制 heatmap 高响应区域轮廓，用 `--heatmap-contour-quantile` 设置阈值，并用 `--heatmap-contour-width` 设置轮廓线宽。渲染不会改变 `predictions.json`，`heatmap_peak_value` 也不是校准后的概率。

当传入 `HeadPerception` 时，primary head bbox 默认绘制。`--face-pose-ray` 绘制蓝色 face reference，`--pose-head-ray` 绘制橙色、独立计算的 pose reference；两者可能不一致，这正是对比用途，请求长度以最终 fused head bbox 为基准。face ray 优先使用双眼中点；仅在仍有至少三个 finite current face keypoints 时，才 fallback 到 face-box center。接近 camera axis 的 face pose 只绘制 origin marker。`tracked_only` primary bbox 使用低透明度虚线，且不保留 stale ray。

绘制层级依次为：gaze heatmap 和可选 contour、现有 gaze bbox/arrow/peak、perception primary head bbox、辅助 face bbox、六个 detector keypoint、pose head/shoulder point、可选 face mesh、perception state/person/confidence label，最后是 gaze prediction label。perception 渲染会原样使用传入的 `HeadPerception`：不会重新计算 perception bbox，不会修改 perception，也不会替换 `GazePrediction.bbox` 或已经传给 Gazelle 的归一化 bbox。MediaPipe perception 已经在内存中保留 `face_landmarks`；`--face-mesh` 独立控制是否绘制这些 landmark，不要求同时使用 `--save-face-landmarks`。单独的 `--save-face-landmarks` 只控制是否把这些 landmark 序列化到 observation JSON/JSONL sidecar。逐帧绘制数百个 mesh point 会增加渲染工作量，序列化它们则会增加 observation 输出体积和保留的生物特征细节。调用方未传 perceptions 或显式传入 `perceptions=()` 时，仍保持逐字节一致的旧版渲染行为；此时 perception 选项不起作用。

Gazelle gaze arrow 是从 head bbox 中心到预测 gaze peak 的可视化，与两条 reference ray 相互独立，也不是真实眼睛方向。`--gaze-inout-threshold` 默认 `0.5`，低于阈值的 prediction 使用 `gaze_status="out_of_frame"`。默认 `--gaze-render-mode valid-only` 不绘制这些 prediction 的 Gazelle heatmap、contour、arrow 或红色 X，但保留 metadata 及可选 bbox/status label。`--gaze-render-mode all-predictions` 会同时绘制 `valid` 与 `out_of_frame` 的这些 geometry，不会修改状态、分数或 JSON 输出。

只显示 bbox、arrow、红色 X 和 label，不显示 heatmap：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --save-rendered `
  --head-box `
  --no-heatmap `
  --overwrite
```

只显示 heatmap，不显示 bbox / arrow / peak / label：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --save-rendered `
  --no-gaze-arrow `
  --no-gaze-peak `
  --no-labels `
  --overwrite
```

### 视频推理

runtime 可以对本地视频文件进行逐帧离线推理：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source none `
  --save-rendered
```

该命令会以流式方式逐帧处理视频，并创建类似 `outputs/assembly_gazelle/` 的视频输出目录。runtime 始终写入 `head_observations.jsonl`、`predictions.jsonl` 和 `run_config.json`，每个写出帧对应恰好一行 observation 和一行 gaze。Gazelle 及其 DINOv2 backbone 会延迟到首个未被跳过且至少有一个可用 head 的帧才构建，之后复用；全部跳过或全部为 `no_head` 的运行不会构建模型。如果权重尚未缓存，首次预测时可能下载它们。这是离线视频处理，不是实时 webcam 模式。rendered video 是无音频输出。

传入 `--save-rendered` 时会写入渲染后的 `.mp4`；默认文件名是 `rendered.mp4`，也可以用 `--output-video-name` 指定另一个 `.mp4` 文件名。`--video-codec mp4v` 是默认值，保持 OpenCV `VideoWriter` 直接写入的现有行为，不要求 FFmpeg。图片渲染使用的绘制选项同样适用于视频，也包括上述具有相同默认值的 `--face-box`、`--face-keypoints`、`--pose-head-points`、`--face-mesh` 和 `--no-track-state`。

如需更适合浏览器播放的 H.264/AVC output，请安装 FFmpeg 并确保 `ffmpeg` 位于 `PATH`，然后选择 `avc1`：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source mediapipe `
  --save-rendered `
  --video-codec avc1
```

`avc1` 路径先把 rendered frame 流式写入临时 `mp4v` video，再调用 FFmpeg；优先使用 `h264_nvenc`，如果 NVENC 在实际编码启动时不可用，则 fallback 到 `libx264`。H.264 output 使用 `yuv420p`、`-movflags +faststart` 和 `-an`，只有成功编码后才原子替换正式输出，并在成功或失败时安全清理临时文件。FFmpeg capability detection 会在 video/provider/model 构建前执行。未启用 `--save-rendered` 时，`--video-codec` 不产生作用。默认单元测试会 mock FFmpeg，不会启动真实 encoder。

如需观察 Gazelle 对指定非保守 MediaPipe state/view 的输出，请显式使用诊断控制：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source mediapipe `
  --gazelle-head-mode face_pose face_only pose_only back_or_occluded tracked_only `
  --gaze-render-mode all-predictions `
  --face-pose-ray `
  --pose-head-ray `
  --save-rendered `
  --video-codec avc1 `
  --overwrite
```

该模式用于诊断和对比。active `tracked_only` bridge 可以被选择，但已经过期的 track 无法恢复。来自 stale、遮挡、pose-only 或其他 non-eligible head 的 Gazelle prediction 属于探索性结果，不能视为已经验证的真实 eye gaze。

`--head-source none` 可以显示 heatmap、contour 和红色 X gaze peak，但因为没有 bbox，不能显示 bbox 或 arrow。如果需要 bbox 和 arrow，请使用 `--head-source static` 或 `--head-source json` 提供 bbox，并传入 `--head-box`。

在 `none` 模式下渲染 heatmap、contour 和红色 X；此模式下不应期待 bbox 或 arrow：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source none `
  --save-rendered `
  --draw-heatmap-contour `
  --overwrite
```

视频 head 输入复用图片推理的 `--head-source none`、`--head-source static` 和 `--head-source json`，也可使用 `--head-source mediapipe` 进行逐帧 perception 和 tracking。视频 JSON head data 应按 `frame_index` 提供记录，可以使用 JSONL 或 JSON list。缺少某一帧时 observation 和被选中的 gaze 行为 `no_head`；`frame_step` 仍优先写 `skipped`。MediaPipe 帧有 head 但没有 perception 匹配配置的 `--gazelle-head-mode` 时，gaze 行写 `status="no_gaze"`，且不调用 Gazelle；当前或 bridged perception overlay 仍可写入 rendered video。

使用 JSON head data：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source json `
  --head-data samples\assembly_heads.jsonl `
  --save-rendered
```

使用固定 pixel bbox，并只处理视频的一部分：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --max-frames 100 `
  --frame-step 2
```

渲染视频并显示 heatmap 高响应区域轮廓：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --save-rendered `
  --head-box `
  --draw-heatmap-contour `
  --heatmap-contour-quantile 0.90 `
  --heatmap-contour-width 3 `
  --overwrite
```

perception 和 tracking 会在每个解码并写出的帧上恰好运行一次。`--frame-step` 只控制 Gazelle：被跳过的帧仍会写 observation 和 prediction 行，且所有 rich perception 都记录为 `gazelle_selected=false`。renderer 会接收 `ok`、`no_gaze`、`skipped`、`no_head` 帧的 perceptions，因此可以持续显示 head continuity 和当前 reference ray，而不会伪造 Gazelle output。`--max-frames` 会把两份 JSONL 和可选渲染视频限制到相同帧数；`--output-fps` 仅在源 FPS 无效时使用。视频仍不支持 `--save-heatmaps`。

### 真实 smoke test

真实图片 / 视频 smoke test 应在现有本地 Conda 环境 `Gazelle` 中运行：

```powershell
conda activate Gazelle
```

单图 smoke test：

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source none `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models `
  --save-rendered `
  --save-heatmaps `
  --overwrite
```

短视频 smoke test：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source none `
  --max-frames 5 `
  --save-rendered `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models `
  --overwrite
```

这些命令会在每次图片运行中构建一次真实 Gazelle predictor 和 DINOv2 backbone，或在视频首个可用帧上构建一次，随后加载 Gazelle checkpoint、执行推理并写出输出目录。checkpoint 解析本身不会构建 DINOv2。如果 `models/checkpoints` 或 `models/torch_hub` 为空，首次运行可能下载 Gazelle checkpoint、DINOv2 PyTorch Hub 仓库和 DINOv2 权重；再次运行相同命令时应复用缓存。CPU smoke test 可以使用 `--device cpu`；在 CPU 上构建 DINOv2 时，runtime 会临时关闭 xFormers，避免本地 CUDA-only xFormers wheel 强制使用不支持的 CPU attention kernel。CUDA 构建会保持 xFormers 启用，并只在 Triton 不可用时跳过可选 Triton 探测。重复的 programmatic 构建可以复用该进程已经选择的 backend，但在不兼容的 CPU/prepare-only 与启用 xFormers 的 CUDA mode 之间切换时必须启动新进程。

### 编程式单帧 Predictor

`GazellePredictor` 为已经准备好的 checkpoint 提供编程式单帧接口：

```python
from PIL import Image

from gazelle.runtime.contracts import HeadObservation
from gazelle.runtime.predictor import GazellePredictor

predictor = GazellePredictor.from_checkpoint(
    model_name="gazelle_dinov2_vitb14_inout",
    checkpoint_path="models/checkpoints/gazelle_dinov2_vitb14_inout.pt",
    cache_dir="models",
    device="auto",
)

frame = Image.open("path/to/frame.png").convert("RGB")
predictions = predictor.predict_frame(
    frame,
    [
        HeadObservation(person_id=1, bbox=(0.10, 0.12, 0.22, 0.30)),
        HeadObservation(person_id=2, bbox=(0.45, 0.10, 0.58, 0.31)),
    ],
)
```

构建 predictor 会加载 Gazelle checkpoint，并通过 PyTorch Hub 构建 DINOv2。请传入与 `--prepare-only` 相同的 `cache_dir`，让 DINOv2 使用已经准备好的 Torch Hub cache；如果该 cache 中没有 DINOv2，这一步可能访问网络。`predict_frame(...)` 接收一帧内存中的 RGB frame，以及按顺序排列的 `HeadObservation` 列表，并按相同 person 顺序返回 `GazePrediction`。每个 prediction 包含 `person_id`、裁剪后的 `bbox`、CPU 上的 `[64, 64]` heatmap tensor、归一化 `gaze_peak`、`heatmap_peak_value`，以及可选 `inout_score`。

runtime 对 head 的处理规则是严格的：

- `heads=[]` 会直接返回空 prediction list，不调用 Gazelle 模型。
- 单个 `HeadObservation(..., bbox=None)` 会使用 Gazelle 的无 bbox fallback 模式。
- 多人推理必须为每个 head 提供有效 bbox。
- bbox 会按有限数值的归一化 `(xmin, ymin, xmax, ymax)` 校验，裁剪到 `[0, 1]`，并拒绝裁剪后为空的 bbox。

编程式 predictor API 仍然可以直接用于内存中的单帧调用。上面的 CLI image pipeline 和离线视频 pipeline 都是基于它的用户可见封装。

以下 runtime 功能在当前里程碑尚未完成：实时 webcam perception/tracking、ROI / 工序逻辑、Multi-Pose 集成、音频 remux、视频 raw heatmap 导出，以及高性能异步推理。

## 推理流程

### 输入 / 输出合约

Gaze-LLE 支持多人推理。一次前向推理接收一批场景图像，以及每张图中需要预测视线的一个或多个人的头部框。对于同一张图，DINOv2 场景特征只编码一次，然后复用到每个人的 gaze heatmap 预测中。

输入字段：

| 字段 | 类型 / 形状 | 含义 |
| ---- | ----------- | ---- |
| `input["images"]` | `torch.Tensor`，形状为 `[B, 3, 448, 448]` | 经过模型 transform 后的 RGB 图像 batch。 |
| `input["bboxes"]` | 长度为 `B` 的 Python list | 每张图对应一个 head bbox 列表。 |
| head bbox | `(xmin, ymin, xmax, ymax)` | 归一化图像坐标，范围为 `[0, 1]`；调用方应保证 bbox 已裁剪、合法，并满足 `xmin < xmax`、`ymin < ymax`。 |
| `None` head bbox | `None` | 仅建议作为单人场景 fallback。多人场景必须传入真实 head bbox，否则模型无法区分要预测哪一个人的视线。 |

`model(input)` 返回一个 dict：

| 字段 | 类型 / 形状 | 含义 |
| ---- | ----------- | ---- |
| `output["heatmap"]` | 长度为 `B` 的 list；每项形状为 `[num_people, 64, 64]` | 每个人的 gaze target heatmap，数值范围为 `[0, 1]`，数值越高表示越可能是视线目标区域。 |
| `output["inout"]` | `None`，或长度为 `B` 的 list；每项形状为 `[num_people]` | 仅 `*_inout` 模型输出。接近 `1` 表示模型认为视线目标在画面内。 |

输出顺序与输入 head bbox 顺序一致。例如 `output["heatmap"][i][j]` 表示第 `i` 张图中第 `j` 个 head bbox 对应人物的 gaze heatmap。

### 模型内部数据流

当前代码中的前向推理流程如下：

1. `transform` 将 PIL RGB 图像转换为归一化张量，并 resize 到 `448x448`。
2. `DinoV2Backbone` 对每张图像编码一次；对于 `448x448` 输入和 ViT-14 backbone，通常得到 `32x32` patch feature map。
3. 每个归一化 head bbox 会被 rasterize 成与 feature map 同尺寸的低分辨率 head map。
4. 图像特征会按照每张图的人数进行复制，再与 head token 和 head map 融合。
5. Transformer decoder 为每个人输出一个 gaze heatmap；`*_inout` 模型还会使用额外 token 输出 in/out-of-frame score。

注意：调用 `get_gazelle_model(...)` 构建模型时会通过 PyTorch Hub 构建 DINOv2 backbone。如果本地没有 DINOv2 缓存，首次构建模型可能会联网下载 backbone 权重。

### 单图单人示例

```python
from PIL import Image
import torch
from gazelle.model import get_gazelle_model

model, transform = get_gazelle_model("gazelle_dinov2_vitl14_inout")
model.load_gazelle_state_dict(torch.load("/path/to/checkpoint.pt", weights_only=True))
model.eval()

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

image = Image.open("path/to/image.png").convert("RGB")
inputs = {
    "images": transform(image).unsqueeze(dim=0).to(device),
    "bboxes": [[(0.1, 0.2, 0.5, 0.7)]],
}

with torch.no_grad():
    output = model(inputs)

predicted_heatmap = output["heatmap"][0][0]
predicted_inout = output["inout"][0][0]
```

输出说明：

- `output["heatmap"][0][0]`：第一张图、第一人的 gaze heatmap，形状为 `[64, 64]`。
- `output["inout"][0][0]`：第一张图、第一人的 in/out score；非 `inout` 模型中该字段为 `None`。

### 多人推理示例

```python
inputs = {
    "images": transform(image).unsqueeze(dim=0).to(device),
    "bboxes": [[
        (0.10, 0.12, 0.22, 0.30),
        (0.45, 0.10, 0.58, 0.31),
        (0.70, 0.18, 0.82, 0.40),
    ]],
}

with torch.no_grad():
    output = model(inputs)

heatmaps_for_first_image = output["heatmap"][0]
```

`heatmaps_for_first_image` 中会包含三个 heatmap，顺序与输入 head bbox 顺序一致。

### 可视化 heatmap

```python
import matplotlib.pyplot as plt
from gazelle.utils import visualize_heatmap

viz = visualize_heatmap(image, predicted_heatmap)
plt.imshow(viz)
plt.show()
```

### 数据集、训练与评估 I/O

数据集加载和评估脚本依赖 `data_prep/preprocess_gazefollow.py` 或 `data_prep/preprocess_vat.py` 生成的预处理 JSON。

- GazeFollow 读取 `{split}_preprocessed.json`，每个元素是一张图像记录。
- VideoAttentionTarget 读取 `{split}_preprocessed.json`，原始结构是 sequence，加载时会按帧展开。
- 每个图像或帧记录包含 `path`、`height`、`width`、`heads`。
- 每个 head 记录包含 `bbox`、`bbox_norm`、`gazex`、`gazey`、`gazex_norm`、`gazey_norm`、`inout`。
- 训练阶段 `GazeDataset` 返回图像张量、归一化 head bbox、归一化 gaze 点、`inout`、原始图像尺寸，以及 `[64, 64]` 的监督 heatmap。
- 训练脚本默认冻结 DINOv2 backbone，并通过 `model.get_gazelle_state_dict()` 只保存 Gaze-LLE decoder 权重。
- `scripts/eval_gazefollow.py` 输出 `AUC`、`Avg L2`、`Min L2`。
- `scripts/eval_vat.py` 输出 `AUC`、`Avg L2`、`Inout AP`。

## 推荐执行顺序

第一次在本机运行时，建议按下面顺序逐步确认：

1. 确认环境和 CUDA：

   ```powershell
   python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
   ```

2. 确认源码导入：

   ```powershell
   $env:PYTHONPATH = Get-Location
   python -c "from gazelle.model import get_gazelle_model; print('import ok')"
   ```

3. 准备 checkpoint，例如：

   ```text
   checkpoints\gazelle_dinov2_vitb14_inout.pt
   ```

4. 首次真实推理前设置 PyTorch Hub 缓存目录，避免权重散落到不明确位置：

   ```powershell
   $env:TORCH_HOME = Join-Path (Get-Location) ".torch_cache"
   ```

5. 构建模型并加载 checkpoint。此时如果 `.torch_cache` 中没有 DINOv2，会下载 DINOv2 backbone。

6. 后续用于 Multi-Pose 集成时，优先使用 ViT-B + inout 模型：

   ```text
   gazelle_dinov2_vitb14_inout
   ```

   ViT-B 通常比 ViT-L 更适合作为实时系统的第一版后端。

## 评估

本仓库提供 GazeFollow 和 VideoAttentionTarget 的评估脚本，用于复现 checkpoint 结果。

### GazeFollow

先下载 GazeFollow 数据集，并运行预处理脚本：

```powershell
python data_prep/preprocess_gazefollow.py --data_path /path/to/gazefollow/data_new
```

然后指定模型类型和 checkpoint 运行评估：

```powershell
python scripts/eval_gazefollow.py `
  --data_path /path/to/gazefollow/data_new `
  --model_name gazelle_dinov2_vitl14 `
  --ckpt_path /path/to/checkpoint.pt `
  --batch_size 128
```

### VideoAttentionTarget

先下载 VideoAttentionTarget 数据集，并运行预处理脚本：

```powershell
python data_prep/preprocess_vat.py --data_path /path/to/videoattentiontarget
```

然后指定模型类型和 checkpoint 运行评估：

```powershell
python scripts/eval_vat.py `
  --data_path /path/to/videoattentiontarget `
  --model_name gazelle_dinov2_vitl14_inout `
  --ckpt_path /path/to/checkpoint.pt `
  --batch_size 64
```

## 训练

训练前需要：

- 下载对应数据集，并按上面的评估章节完成预处理。
- 安装并登录 `wandb` 用于训练日志记录；如果不想使用 wandb，可以移除训练脚本中的 wandb 记录逻辑，指标仍会输出到 stdout。

默认每个 epoch 的 checkpoint 会保存到 `./experiments`。可以通过 `--ckpt_save_dir` 自定义输出目录。

### 在 GazeFollow 上训练

训练 ViT-B：

```powershell
python scripts/train_gazefollow.py `
  --data_path /path/to/gazefollow/data_new `
  --model gazelle_dinov2_vitb14 `
  --exp_name train_gazelle_vitb_gazefollow
```

训练 ViT-L：

```powershell
python scripts/train_gazefollow.py `
  --data_path /path/to/gazefollow/data_new `
  --model gazelle_dinov2_vitl14 `
  --exp_name train_gazelle_vitl_gazefollow
```

### 在 VideoAttentionTarget 上训练

VideoAttentionTarget 训练通常从对应的 GazeFollow checkpoint 初始化。该任务还包含 in/out-of-frame 预测，因此模型会额外使用 in/out head 和对应 loss。

训练 ViT-B：

```powershell
python scripts/train_vat.py `
  --data_path /path/to/videoattentiontarget `
  --model gazelle_dinov2_vitb14_inout `
  --init_ckpt /path/to/gazelle_dinov2_vitb_checkpoint.pt `
  --exp_name train_gazelle_vitb_vat
```

训练 ViT-L：

```powershell
python scripts/train_vat.py `
  --data_path /path/to/videoattentiontarget `
  --model gazelle_dinov2_vitl14_inout `
  --init_ckpt /path/to/gazelle_dinov2_vitl_checkpoint.pt `
  --exp_name train_gazelle_vitl_vat
```

## 与 Multi-Pose 集成的建议

当前仓库应先作为独立 gaze backend 进行验证，再通过第三方库方式提供给 Multi-Pose。建议路线：

1. 先在本仓库完成独立推理接口和文档。
2. 确认 Windows + CUDA 环境下能稳定 import、加载 checkpoint、输出 heatmap。
3. 为 Multi-Pose 提供稳定的输入输出约定：
   - 输入：当前 RGB 帧、tracked person id、每个人对应的归一化 head bbox、设备、可选 in/out threshold。
   - 输出：每个 head bbox 对应的 `[64, 64]` gaze heatmap、可选 in/out score。
4. Multi-Pose 中只调用该稳定接口，不复制 Gazelle 内部模型代码。
5. 权重和 DINOv2 cache 仍作为本地运行资产，不提交到任一仓库。

Multi-Pose 侧应负责人物跟踪、head/person bbox 生成、推理频率控制，以及将 `[64, 64]` heatmap 映射回原图或 BEV 坐标。Gazelle 本身不做人脸身份识别，也不会输出身份 embedding。

当前 `gazelle/model.py` 中的 source factory 支持 `gazelle_dinov2_vitb14`、`gazelle_dinov2_vitl14`、`gazelle_dinov2_vitb14_inout`、`gazelle_dinov2_vitl14_inout`。上方表格中的 ChildPlay checkpoint 是可下载的预训练资产，但当前 source factory 尚未提供单独的 ChildPlay 模型名。

## 常见问题

### 为什么 checkpoint 不能单独运行？

Gaze-LLE checkpoint 只保存 gaze decoder 权重。模型还需要 DINOv2 backbone。首次构建模型时，DINOv2 会通过 PyTorch Hub 加载；如果本地没有缓存，就需要联网下载。

### 多人推理为什么必须传 head bbox？

模型需要知道要预测哪一个人的视线。单人场景可以用 `None` 近似运行；多人场景必须传每个人的 head bbox，否则无法区分不同人的 gaze target。

### 应该先使用 ViT-B 还是 ViT-L？

如果目标是后续接入实时系统，建议先使用 `gazelle_dinov2_vitb14_inout`。ViT-L 通常更重，适合作为精度对照或离线评估。

### 这个模型会做人脸身份识别吗？

不会。Gazelle 只根据图像和 head bbox 预测 gaze target，不建立人脸库，也不输出身份 embedding。

## 引用

```bibtex
@inproceedings{ryan2025gazelle,
    author = {Ryan, Fiona and Bati, Ajay and Lee, Sangmin and Bolya, Daniel and Hoffman, Judy and Rehg, James M.},
    title = {Gaze-LLE: Gaze Target Estimation via Large-Scale Learned Encoders},
    year = {2025},
    booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition}
}
```

## 参考

- 本项目的模型建立在 PyTorch Hub 中的 DINOv2 预训练模型之上：[facebookresearch/dinov2](https://github.com/facebookresearch/dinov2)。
- GazeFollow 和 VideoAttentionTarget 预处理代码基于 [Detecting Attended Targets in Video](https://github.com/ejcgt/attention-target-detection)。
- Transformer 实现使用 [PyTorch Image Models (timm)](https://github.com/huggingface/pytorch-image-models)。
- 高效 multi-head attention 可使用 [xFormers](https://github.com/facebookresearch/xformers)。
