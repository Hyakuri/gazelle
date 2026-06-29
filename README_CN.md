# Gaze-LLE
#### CVPR 2025 Highlight

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

当前 fork 的 runtime pipeline 以本地已经验证过的 Conda 环境 `Gazelle` 为推荐环境。开发或运行当前分阶段 CLI 时，优先激活这个环境：

```powershell
conda activate Gazelle
pip install -e .
```

仓库中的 `environment.yml` 已对齐本地验证环境：Python 3.11、PyTorch 2.6.0 + CUDA 12.6 wheels、TorchVision 0.21.0 + CUDA 12.6、TorchAudio 2.6.0 + CUDA 12.6、OpenCV 4.11.0，以及 xFormers 0.0.29。原始 upstream Gazelle 的旧环境配置不再作为本 fork 当前 runtime pipeline 的主要依据。如果你已经有可运行的本地 `Gazelle` 环境，请优先激活它，不要为了匹配旧 upstream 设置而降级当前环境。

如果是在一台全新机器上配置，`environment.yml` 记录了当前预期的包版本：

```powershell
conda env create -f environment.yml
conda activate Gazelle
pip install -e .
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

该命令可能下载 Gazelle checkpoint，并且会通过 PyTorch Hub 构建 DINOv2 backbone。如果本地没有 DINOv2 缓存，构建 DINOv2 时可能下载 DINOv2 权重。它不会处理图片、处理视频、打开摄像头、渲染输出，也不会写入 JSON/JSONL 预测结果。

成功时，该命令会输出解析后的 checkpoint 路径、`checkpoint_source`、缓存根目录、Torch Hub 缓存目录，以及注册 checkpoint 候选的 strict-load 校验信息。使用 `--checkpoint` 时，`checkpoint_source` 为 `local`；使用 runtime 注册 checkpoint 时，`checkpoint_source` 为对应候选来源。

缓存根目录优先级：

1. `--cache-dir`
2. `GAZELLE_CACHE_DIR`
3. `models`

runtime 使用以下目录结构：

```text
models/
├── checkpoints/
└── torch_hub/
```

如果希望使用本地 checkpoint，并跳过注册 checkpoint 下载，可以指定：

```powershell
python main.py `
  --prepare-only `
  --model gazelle_dinov2_vitb14_inout `
  --checkpoint C:\path\to\gazelle_dinov2_vitb14_inout.pt
```

如果希望刷新已缓存的注册 checkpoint，可以使用 `--force-download`：

```powershell
python main.py `
  --prepare-only `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models `
  --force-download
```

为了避免网络失败导致旧缓存丢失，强制下载会先写入 checkpoint 缓存下的临时 `.downloads` 目录。只有新文件下载完成且确认存在后，runtime 才会替换旧 checkpoint。如果下载失败，已有 checkpoint 会被保留。

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

该命令会构建 Gazelle 模型和 DINOv2 backbone。如果所选 Gazelle checkpoint 或 DINOv2 权重尚未缓存，运行时可能访问网络并下载它们。命令会创建类似 `outputs/frame_gazelle/` 的单图输出目录，并写入 `predictions.json` 和 `run_config.json`。图片输入不会打开摄像头，也不会写入视频 JSONL；视频输入由下方的视频推理路径处理。

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

单图推理会读取 `frame_index=0` 的 head 数据。JSON 使用 runtime head provider 的内部 record 格式，`bbox_format` 可以是 `normalized` 或 `pixel`，`heads` 中包含 `person_id`、`bbox` 和可选 `confidence`。

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

默认情况下，单图推理只写入 `predictions.json` 和 `run_config.json`；只有传入 `--save-rendered` 时才会写可视化图片。默认文件名是 `rendered.png`。可以用 `--rendered-name` 指定 `.png`、`.jpg` 或 `.jpeg` 文件名，用 `--heatmap-alpha` 控制 heatmap 透明度。可视化 overlay 可以包含 heatmap、head bbox、gaze peak、person id 和可选的 `inout_score`；可以用 `--no-head-box`、`--no-gaze-peak` 或 `--no-labels` 关闭对应绘制元素。渲染不会改变 `predictions.json`，`heatmap_peak_value` 也不是校准后的概率。

### 视频推理

runtime 可以对本地视频文件进行逐帧离线推理：

```powershell
python main.py `
  --input samples\assembly.mp4 `
  --output-dir outputs `
  --head-source none `
  --save-rendered
```

该命令会构建 Gazelle 模型和 DINOv2 backbone。如果所选 Gazelle checkpoint 或 DINOv2 权重尚未缓存，运行时可能访问网络并下载它们。视频会以流式方式逐帧处理，并创建类似 `outputs/assembly_gazelle/` 的视频输出目录，始终写入 `predictions.jsonl` 和 `run_config.json`。这是离线视频处理，不是实时 webcam 模式。渲染视频不会保留音频。

传入 `--save-rendered` 时会写入渲染后的 `.mp4`；默认文件名是 `rendered.mp4`，也可以用 `--output-video-name` 指定另一个 `.mp4` 文件名。图片渲染使用的绘制选项同样适用于视频：`--heatmap-alpha`、`--no-head-box`、`--no-gaze-peak` 和 `--no-labels`。

视频 head 输入复用图片推理的 `--head-source none`、`--head-source static` 和 `--head-source json`。视频 JSON head data 应按 `frame_index` 提供记录，可以使用 JSONL 或 JSON list。如果 JSON head data 缺少某一帧，runtime 会为该帧写入 `status="no_head"` 的 `predictions.jsonl` 行，并跳过该帧的模型推理。

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

`--frame-step` 表示每隔 N 帧运行一次 Gazelle。被跳过的帧仍会写入 `status="skipped"` 的 `predictions.jsonl` 行；如果启用了渲染，这些帧会以原帧写入渲染视频。`--max-frames` 限制写出的帧数。`--output-fps` 只在源视频 FPS 无效时作为 fallback；源视频 FPS 有效时会保留源 FPS。当前里程碑不支持视频 `--save-heatmaps`，使用时会报错 `video heatmap export is not implemented yet`。

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

这些命令会构建真实 Gazelle predictor 和 DINOv2 backbone，加载 Gazelle checkpoint，执行推理，并写出输出目录。如果 `models/checkpoints` 或 `models/torch_hub` 为空，首次运行可能下载 Gazelle checkpoint、DINOv2 PyTorch Hub 仓库和 DINOv2 权重；再次运行相同命令时应复用缓存。CPU smoke test 可以使用 `--device cpu`；在 CPU 上构建 DINOv2 时，runtime 会临时关闭 xFormers，避免本地 CUDA-only xFormers wheel 强制使用不支持的 CPU attention kernel。

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

以下 runtime 功能在当前里程碑尚未完成：实时 webcam 输入、自动 head detection、tracking、ROI / 工序逻辑、Multi-Pose 集成、音频 remux、视频 raw heatmap 导出，以及高性能异步推理。

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
