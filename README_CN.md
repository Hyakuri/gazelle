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

之后新增用户可见功能、脚本、环境依赖、模型下载方式、推理接口或与 Multi-Pose 的集成说明时，请同时更新 `README.md` 和 `README_CN.md`。命令示例应默认从仓库根目录执行，并明确说明命令是否会下载权重、打开界面、训练模型，或只是进行安全的 import/CLI 验证。

## 项目能力概览

- 输入一张场景图像，以及一个或多个人的头部 bounding box。
- 对每个人输出 gaze heatmap，即画面中该人物可能正在看的区域。
- 对带 `inout` head 的模型，还会输出视线目标是否在画面内的概率。
- 多人推理时，场景图像只编码一次，再针对多个 head box 预测 gaze heatmap。
- 预训练模型基于 DINOv2 backbone，checkpoint 中只包含 Gaze-LLE decoder 权重；DINOv2 backbone 会由 PyTorch Hub 加载。

## 安装方式

官方环境文件是 `environment.yml`：

```powershell
conda env create -f environment.yml
conda activate gazelle
pip install -e .
```

如果系统支持，也可以安装 `xformers` 来加速 attention 计算：

```powershell
pip install -U xformers --index-url https://download.pytorch.org/whl/cu118
```

### Windows / CUDA 推荐环境

如果是在本项目和 Multi-Pose 联合开发的 Windows 机器上调试，可以使用单独的 `Gazelle` 环境，避免修改 Multi-Pose 的运行环境：

```powershell
conda activate Gazelle
```

如果不执行 `pip install -e .`，也可以直接通过 `PYTHONPATH` 使用当前仓库源码：

```powershell
$env:PYTHONPATH = Get-Location
python -c "from gazelle.model import get_gazelle_model; print('gazelle import ok')"
```

这种方式适合在源码仍频繁调整时使用。它不会在仓库里生成 `egg-info`，也不会修改其他项目环境。

### 首次运行前检查

建议先运行不下载模型权重的检查命令：

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "from gazelle.model import get_gazelle_model; print('gazelle import ok')"
```

注意：只要实际调用 `get_gazelle_model(...)` 构建模型，代码会通过 `torch.hub.load('facebookresearch/dinov2', ...)` 加载 DINOv2 backbone。如果本地没有缓存，这一步可能访问网络并下载 DINOv2 权重。

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

## 推理流程

### 输入格式

Gaze-LLE 支持多人推理。输入包括：

- `images`：形状为 `[B, 3, 448, 448]` 的图像张量。
- `bboxes`：每张图像对应一个 head bbox 列表，格式为 `[(xmin, ymin, xmax, ymax)]`。
- bbox 坐标是归一化图像坐标，范围为 `[0, 1]`。
- 对单人场景，如果没有 head bbox，可以传入 `None`；多人场景必须提供 head bbox，用于指定要预测哪一个人的视线。

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
  --model_name gazelle_dinov2_vitb `
  --exp_name train_gazelle_vitb_gazefollow
```

训练 ViT-L：

```powershell
python scripts/train_gazefollow.py `
  --data_path /path/to/gazefollow/data_new `
  --model_name gazelle_dinov2_vitl `
  --exp_name train_gazelle_vitl_gazefollow
```

### 在 VideoAttentionTarget 上训练

VideoAttentionTarget 训练通常从对应的 GazeFollow checkpoint 初始化。该任务还包含 in/out-of-frame 预测，因此模型会额外使用 in/out head 和对应 loss。

训练 ViT-B：

```powershell
python scripts/train_vat.py `
  --data_path /path/to/videoattentiontarget `
  --model_name gazelle_dinov2_vitb_inout `
  --init_ckpt /path/to/gazelle_dinov2_vitb_checkpoint.pt `
  --exp_name train_gazelle_vitb_vat
```

训练 ViT-L：

```powershell
python scripts/train_vat.py `
  --data_path /path/to/videoattentiontarget `
  --model_name gazelle_dinov2_vitl_inout `
  --init_ckpt /path/to/gazelle_dinov2_vitl_checkpoint.pt `
  --exp_name train_gazelle_vitl_vat
```

## 与 Multi-Pose 集成的建议

当前仓库应先作为独立 gaze backend 进行验证，再通过第三方库方式提供给 Multi-Pose。建议路线：

1. 先在本仓库完成独立推理接口和文档。
2. 确认 Windows + CUDA 环境下能稳定 import、加载 checkpoint、输出 heatmap。
3. 为 Multi-Pose 提供稳定的输入输出约定：
   - 输入：RGB 图像、多人 head bbox、设备、可选 in/out threshold。
   - 输出：每个 head bbox 对应的 `[64, 64]` heatmap、可选 in/out score。
4. Multi-Pose 中只调用该稳定接口，不复制 Gazelle 内部模型代码。
5. 权重和 DINOv2 cache 仍作为本地运行资产，不提交到任一仓库。

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
