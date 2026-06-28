# Gaze-LLE
#### CVPR 2025 (Highlight)

[中文说明](README_CN.md)

[Gaze-LLE: Gaze Target Estimation via Large-Scale Learned Encoders](https://arxiv.org/abs/2412.09586) \
[Fiona Ryan](https://fkryan.github.io/), [Ajay Bati](https://www.linkedin.com/in/abati777/), [Sangmin Lee](https://sites.google.com/view/sangmin-lee), [Daniel Bolya](https://dbolya.github.io/), [Judy Hoffman](https://faculty.cc.gatech.edu/~judy/)\*, [James M. Rehg](https://rehg.org/)\*

<div style="text-align:center;">
    <img src="./assets/office_gif.gif" height="300"/>
</div>


This is the official implementation for Gaze-LLE, a transformer approach for estimating gaze targets that leverages the power of pretrained visual foundation models. Gaze-LLE provides a streamlined gaze architecture that learns only a lightweight gaze decoder on top of a frozen, pretrained visual encoder (DINOv2). Gaze-LLE learns 1-2 orders of magnitude fewer parameters than prior works and doesn't require any extra input modalities like depth and pose!

<div style="text-align:center;">
    <img src="./assets/gazelle_arch.png" height="200"/>
</div>

## Documentation Maintenance

When adding user-facing features, scripts, CLI arguments, environment requirements, model download instructions, output formats, or integration notes, update both `README.md` and `README_CN.md` in the same change. Keep examples runnable from the repository root, and state clearly whether a command downloads weights, opens a UI, trains a model, runs inference, uses CUDA, writes outputs, or only validates imports. If a code-only change does not require a README update, note that explicitly in the development report or PR comment.


## Installation

Clone this repo, then create the virtual environment.
```
conda env create -f environment.yml
conda activate gazelle
pip install -e .
```
If your system supports it, consider installing [xformers](https://github.com/facebookresearch/xformers) to speed up attention computation.
```
pip3 install -U xformers --index-url https://download.pytorch.org/whl/cu118
```

## Pretrained Models

We provide the following pretrained models for download.
| Name | Backbone type | Backbone name | Training data | Checkpoint |
| ---- | ------------- | ------------- |-------------- | ---------- |
| ```gazelle_dinov2_vitb14``` | DINOv2 ViT-B | ```dinov2_vitb14```| GazeFollow | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitb14.pt) |
| ```gazelle_dinov2_vitl14``` | DINOv2 ViT-L | ```dinov2_vitl14``` | GazeFollow | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitl14.pt) |
| ```gazelle_dinov2_vitb14_inout``` | DINOv2 ViT-B | ```dinov2_vitb14``` | Gazefollow -> VideoAttentionTarget | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitb14_inout.pt) |
| ```gazelle_dinov2_vitl14_inout``` | DINOv2-ViT-L | ```dinov2_vitl14```  | GazeFollow -> VideoAttentionTarget | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitl14_inout.pt) |
| ```gazelle_dinov2_vitb14_inout_childplay``` | DINOv2 ViT-B | ```dinov2_vitb14``` | Gazefollow -> ChildPlay | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitb14_inout_childplay.pt) |
| ```gazelle_dinov2_vitl14_inout_childplay``` | DINOv2-ViT-L | ```dinov2_vitl14```  | GazeFollow -> ChildPlay | [Download](https://github.com/fkryan/gazelle/releases/download/v1.0.0/gazelle_dinov2_vitl14_inout_childplay.pt) |


Note that our Gaze-LLE checkpoints contain only the gaze decoder weights - the DINOv2 backbone weights are downloaded from ```facebookresearch/dinov2``` on PyTorch Hub when the Gaze-LLE model is created in our code.

The GazeFollow-trained models output a spatial heatmap of gaze locations over the scene with values in range ```[0,1]```, where 1 represents the highest probability of the location being a gaze target. The models that are additionally finetuned on VideoAttentionTarget also predict a in/out of frame gaze score in range ```[0,1]``` where 1 represents the person's gaze target being in the frame.

### PyTorch Hub

The models are also available on PyTorch Hub for easy use without needing to install from source.
```
model, transform = torch.hub.load('fkryan/gazelle', 'gazelle_dinov2_vitb14')
model, transform = torch.hub.load('fkryan/gazelle', 'gazelle_dinov2_vitl14')
model, transform = torch.hub.load('fkryan/gazelle', 'gazelle_dinov2_vitb14_inout')
model, transform = torch.hub.load('fkryan/gazelle', 'gazelle_dinov2_vitl14_inout')
```

## Unified Runtime Preview

A unified local runtime is being developed around the original research model. The runtime entry point is:

```powershell
python main.py --help
```

The runtime currently exposes safe CLI/model-registry inspection, resource preparation, and single-image inference:

```powershell
python main.py --list-models
```

`--help` and `--list-models` do not construct the DINOv2 backbone, download Gazelle checkpoints, access PyTorch Hub, run image or video inference, use a camera, use CUDA for model execution, or write output files. They only validate the local CLI layer and print the registered model metadata.

At this stage, the runtime registry lists the four model names that are currently constructible from `gazelle/model.py`:

- `gazelle_dinov2_vitb14`
- `gazelle_dinov2_vitl14`
- `gazelle_dinov2_vitb14_inout`
- `gazelle_dinov2_vitl14_inout`

`gazelle_dinov2_vitb14` uses the README checkpoint file `gazelle_dinov2_vitb14.pt` by default. The older `hubconf.py` filename `gazelle_dinov2_vitb14_hub.pt` was checked during runtime development and found to be strict-load compatible and byte-identical to the README checkpoint.

### Resource Preparation

Use `--prepare-only` to prepare local model resources without running image or video inference:

```powershell
python main.py --prepare-only --model gazelle_dinov2_vitb14_inout
```

This command may download the Gazelle checkpoint and may construct the DINOv2 backbone through PyTorch Hub. Constructing DINOv2 can download DINOv2 weights if they are not already cached. It does not process images, process videos, open a camera, render output, or write JSON/JSONL predictions.

On success, the command prints the resolved checkpoint path, `checkpoint_source`, cache root, Torch Hub cache directory, and strict-load validation details for registered checkpoint candidates. `checkpoint_source` is `local` when `--checkpoint` is used, or the registered candidate source when the runtime prepares a downloaded checkpoint.

Cache root priority:

1. `--cache-dir`
2. `GAZELLE_CACHE_DIR`
3. `models`

The runtime uses this directory layout:

```text
models/
├── checkpoints/
└── torch_hub/
```

Use a local checkpoint path to skip the registered checkpoint download:

```powershell
python main.py `
  --prepare-only `
  --model gazelle_dinov2_vitb14_inout `
  --checkpoint C:\path\to\gazelle_dinov2_vitb14_inout.pt
```

Use `--force-download` to refresh the cached registered checkpoint for the selected model:

```powershell
python main.py `
  --prepare-only `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models `
  --force-download
```

For safety, forced downloads are written to a temporary `.downloads` directory under the checkpoint cache first. The old cached checkpoint is replaced only after the new file is downloaded and found on disk. If the download fails, the existing cached checkpoint is preserved.

Checkpoint validation is strict in the runtime path: empty state dicts, missing keys, unexpected keys, shape mismatches, non-tensor values, and incompatible checkpoint structures stop preparation with an error.

### Single-Image Inference

The runtime can run Gazelle on one image and write structured outputs:

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source none `
  --model gazelle_dinov2_vitb14_inout
```

This command constructs the Gazelle model and DINOv2 backbone. If the selected Gazelle checkpoint or DINOv2 weights are not already cached, it may download them. It writes a per-image output directory such as `outputs/frame_gazelle/` containing `predictions.json` and `run_config.json`. The current image pipeline supports single images only; it does not process video, open a camera, create a rendered overlay, or write video JSONL.

Head input sources:

- `--head-source none` creates one single-person fallback head with `bbox=None`.
- `--head-source static` uses one or more CLI bboxes:

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source static `
  --bbox 0.10 0.12 0.22 0.30 `
  --bbox-format normalized
```

`--bbox` can be repeated for multiple people. Use `--bbox-format normalized` for `[0, 1]` coordinates or `--bbox-format pixel` for image pixel coordinates. Optional `--person-id` values can be repeated to match the number of `--bbox` entries; otherwise person ids default to `0, 1, 2, ...`.

- `--head-source json` loads image head data from JSON:

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source json `
  --head-data samples\frame_heads.json
```

For single-image inference, JSON head data is read from `frame_index=0`. The JSON format is the same internal head record format used by the runtime head providers, with `bbox_format` set to `normalized` or `pixel` and `heads` containing `person_id`, `bbox`, and optional `confidence`.

Use `--save-heatmaps` to save raw per-person heatmap tensors:

```powershell
python main.py `
  --input samples\frame.jpg `
  --output-dir outputs `
  --head-source none `
  --save-heatmaps
```

Raw heatmaps are saved under `heatmaps/` in the per-image output directory and referenced from `predictions.json`. Heatmaps are not embedded directly in JSON, and `heatmap_peak_value` should not be treated as a calibrated probability.

### Programmatic Single-Frame Predictor

`GazellePredictor` provides a programmatic single-frame interface for already prepared checkpoints:

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

Constructing the predictor loads the Gazelle checkpoint and constructs DINOv2 through PyTorch Hub. Pass the same `cache_dir` used for `--prepare-only` so DINOv2 uses the prepared Torch Hub cache; if DINOv2 is not cached there, construction may access the network. `predict_frame(...)` accepts one in-memory RGB frame plus an ordered list of `HeadObservation` values and returns `GazePrediction` values in the same person order. Each prediction contains `person_id`, the clipped `bbox`, the `[64, 64]` heatmap tensor on CPU, normalized `gaze_peak`, `heatmap_peak_value`, and optional `inout_score`.

Runtime head behavior is intentionally strict:

- `heads=[]` returns an empty prediction list without calling the Gazelle model.
- A single `HeadObservation(..., bbox=None)` uses Gazelle's no-bbox fallback mode.
- Multi-person inference requires a valid bbox for every head.
- Bboxes are validated as finite normalized `(xmin, ymin, xmax, ymax)` values, clipped to `[0, 1]`, and rejected if clipping leaves an empty box.

The programmatic predictor API remains available for direct in-memory use. The CLI image pipeline above is the first user-facing wrapper around it; video CLI integration is still pending.

The following runtime features are planned but not available yet in this milestone: automatic head detection, streaming video inference, video recomposition, rendered overlays, video JSONL output, ROI/process logic, and Multi-Pose integration.


## Usage
### Colab Demo Notebook
Check out our [Demo Notebook](https://colab.research.google.com/drive/1TSoyFvNs1-au9kjOZN_fo5ebdzngSPDq?usp=sharing) on Google Colab for how to detect gaze for all people in an image.

### Input / Output Contract
Gaze-LLE takes one scene image batch and a variable number of head boxes per image. The same encoded scene features are reused for all people in the same image, which is the key interface for multi-person use.

| Field | Type / shape | Meaning |
| ----- | ------------ | ------- |
| `input["images"]` | `torch.Tensor` with shape `[B, 3, 448, 448]` | RGB images after the model transform. |
| `input["bboxes"]` | Python list with length `B` | For each image, a list of head boxes for the people to predict. |
| Head box | `(xmin, ymin, xmax, ymax)` | Normalized image coordinates in `[0, 1]`; callers should pass valid clipped boxes with `xmin < xmax` and `ymin < ymax`. |
| `None` head box | `None` | Optional single-person fallback. For multi-person scenes, pass real head boxes so the model knows whose gaze to estimate. |

`model(input)` returns a dictionary:

| Field | Type / shape | Meaning |
| ----- | ------------ | ------- |
| `output["heatmap"]` | list of length `B`; each item has shape `[num_people, 64, 64]` | Per-person gaze target heatmaps. Values are in `[0, 1]`; higher values indicate more likely gaze targets. |
| `output["inout"]` | `None`, or list of length `B`; each item has shape `[num_people]` | Only available for `*_inout` models. A value near `1` means the gaze target is predicted to be inside the frame. |

The output order always follows the input head box order. For example, `output["heatmap"][i][j]` is the heatmap for the `j`-th head box in the `i`-th image.

### Model Data Flow
At inference time, the current code follows this path:

1. The transform converts each PIL RGB image to a normalized tensor resized to `448x448`.
2. `DinoV2Backbone` encodes each image once and returns patch features, usually a `32x32` feature map for `448x448` inputs with a ViT-14 backbone.
3. Each normalized head box is rasterized into a low-resolution head map matching the feature map size.
4. Image features are repeated along the person dimension, one copy per head box, then combined with the learned head token and head map.
5. The transformer decoder predicts one gaze heatmap per person. `*_inout` models also use an extra token to predict the in/out-of-frame score.

Creating a model with `get_gazelle_model(...)` constructs the DINOv2 backbone through PyTorch Hub. If the DINOv2 weights are not already cached locally, that step can download the backbone weights.

### Gaze Prediction
Gaze-LLE is set up for multi-person inference (e.g. for a single image, Gaze-LLE encodes the scene only once and then uses the features to predict the gaze of multiple people in the image). The input is a batch of image tensors and a list of bounding boxes for each image representing the heads of the people whose gaze we want to predict in each image. The bounding boxes are tuples of form ```(xmin, ymin, xmax, ymax)``` and are in ```[0,1]``` normalized image coordinates. Below we show how to perform inference for a single person in a single image.
```
from PIL import Image
import torch
from gazelle.model import get_gazelle_model

model, transform = get_gazelle_model("gazelle_dinov2_vitl14_inout")
model.load_gazelle_state_dict(torch.load("/path/to/checkpoint.pt", weights_only=True))
model.eval()

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

image = Image.open("path/to/image.png").convert("RGB")
input = {
    "images": transform(image).unsqueeze(dim=0).to(device),    # tensor of shape [1, 3, 448, 448]
    "bboxes": [[(0.1, 0.2, 0.5, 0.7)]]              # list of lists of bbox tuples
}

with torch.no_grad():
    output = model(input)
predicted_heatmap = output["heatmap"][0][0]        # access prediction for first person in first image. Tensor of size [64, 64]
predicted_inout = output["inout"][0][0]            # in/out of frame score (1 = in frame) (output["inout"] will be None  for non-inout models)
```
We empirically find that Gaze-LLE is effective without a bounding box input for scenes with just one person. However, providing a bounding box can improve results, and is necessary for scenes with multiple people to specify which person's gaze to estimate. To inference without a bounding box, use None in place of a bounding box tuple in the bbox list (e.g. ```input["bboxes"] = [[None]]``` in the example above).


We also provide a function to visualize the predicted heatmap for an image.
```
import matplotlib.pyplot as plt
from gazelle.utils import visualize_heatmap

viz = visualize_heatmap(image, predicted_heatmap)
plt.imshow(viz)
plt.show()
```

### Multi-Pose Integration I/O
When using this repository as a gaze backend for Multi-Pose or another real-time system, keep the interface narrow:

- Input from the host system: the current RGB frame, tracked person IDs, and one normalized head box per person.
- Gazelle output to the host system: one `[64, 64]` gaze heatmap per head box and, for `*_inout` models, one in-frame score per head box.
- The host system should handle person tracking, head/person box generation, frame-rate throttling, and any projection from the `64x64` heatmap back to raw-frame or BEV coordinates.
- Gazelle does not perform face identity recognition and does not return identity embeddings.

The source factory in `gazelle/model.py` currently exposes `gazelle_dinov2_vitb14`, `gazelle_dinov2_vitl14`, `gazelle_dinov2_vitb14_inout`, and `gazelle_dinov2_vitl14_inout`. The ChildPlay checkpoints listed above are downloadable pretrained assets, but the current source factory does not expose separate ChildPlay model names.

### Dataset, Training, and Evaluation I/O
The dataset loaders and evaluation scripts use preprocessed JSON files generated by `data_prep/preprocess_gazefollow.py` or `data_prep/preprocess_vat.py`.

- GazeFollow reads `{split}_preprocessed.json` directly as a list of image records.
- VideoAttentionTarget reads `{split}_preprocessed.json` as sequences and flattens sampled frames for training and evaluation.
- Each image or frame record contains `path`, `height`, `width`, and `heads`.
- Each head record contains `bbox`, `bbox_norm`, `gazex`, `gazey`, `gazex_norm`, `gazey_norm`, and `inout`.
- For training, `GazeDataset` returns image tensors, normalized head boxes, normalized gaze points, `inout`, original image size, and a `64x64` target heatmap.
- The training scripts freeze the DINOv2 backbone and save Gaze-LLE decoder weights by default through `model.get_gazelle_state_dict()`.
- `scripts/eval_gazefollow.py` prints `AUC`, `Avg L2`, and `Min L2`.
- `scripts/eval_vat.py` prints `AUC`, `Avg L2`, and `Inout AP`.

## Evaluate
We provide evaluation scripts for GazeFollow and VideoAttentionTarget below to reproduce our results from our checkpoints.
### GazeFollow
Download the GazeFollow dataset [here](https://github.com/ejcgt/attention-target-detection?tab=readme-ov-file#dataset). We provide a preprocessing script ```data_prep/preprocess_gazefollow.py```, which preprocesses and compiles the annotations into a JSON file for each split within the dataset folder. Run the preprocessing script as
```
python data_prep/preprocess_gazefollow.py --data_path /path/to/gazefollow/data_new
```
Download the pretrained model checkpoints above and use ```--model_name``` and ```--ckpt_path``` to specify the model type and checkpoint for evaluation.

```
python scripts/eval_gazefollow.py
    --data_path /path/to/gazefollow/data_new \
    --model_name gazelle_dinov2_vitl14 \
    --ckpt_path /path/to/checkpoint.pt \
    --batch_size 128
```


### VideoAttentionTarget
Download the VideoAttentionTarget dataset [here](https://github.com/ejcgt/attention-target-detection?tab=readme-ov-file#dataset-1). We provide a preprocessing script ```data_prep/preprocess_vat.py```, which preprocesses and compiles the annotations into a JSON file for each split within the dataset folder. Run the preprocessing script as
```
python data_prep/preprocess_vat.py --data_path /path/to/videoattentiontarget
```
Download the pretrained model checkpoints above and use ```--model_name``` and ```ckpt_path``` to specify the model type and checkpoint for evaluation.
```
python scripts/eval_vat.py
    --data_path /path/to/videoattentiontarget \
    --model_name gazelle_dinov2_vitl14_inout \
    --ckpt_path /path/to/checkpoint.pt \
    --batch_size 64
```

## Train
We also provide scripts to train our model. Before running the training script, please:

- Download the dataset(s) and run the preprocessing script(s) following the [previous section](#evaluate).
- Install and authenticate to [wandb](https://docs.wandb.ai/quickstart/) (```pip install wandb```) for metric logging. If you don't want to use wandb, you can remove the wandb logging lines from ```scripts/train_gazefollow.py```. Metrics will still be written to stdout.

By default, the checkpoint for each epoch will be saved to ```./experiments```. You can use the `--ckpt_save_dir` argument to customize this.

### GazeFollow

To train our ViT-B model on Gazefollow:
```
python scripts/train_gazefollow.py
    --data_path /path/to/gazefollow/data_new \
    --model gazelle_dinov2_vitb14 \
    --exp_name train_gazelle_vitb_gazefollow
```

To train our ViT-L model on Gazefollow:
```
python scripts/train_gazefollow.py
    --data_path /path/to/gazefollow/data_new \
    --model gazelle_dinov2_vitl14 \
    --exp_name train_gazelle_vitl_gazefollow
```

### VideoAttentionTarget
Our VideoAttentionTarget training is initialized from the corresponding GazeFollow-trained checkpoint, which can be downloaded from [our set of pretrained models](#pretrained-models). VideoAttentionTarget also includes the task of predicting if the gaze is in or out of frame, so an additional model head and loss term are included.

To train our ViT-B model on VideoAttentionTarget:
```
python scripts/train_vat.py
    --data_path /path/to/videoattentiontarget \
    --model gazelle_dinov2_vitb14_inout \
    --init_ckpt /path/to/gazelle_dinov2_vitb_checkpoint.pt \
    --exp_name train_gazelle_vitb_vat
```

To train our ViT-L model on VideoAttentionTarget:
```
python scripts/train_vat.py
    --data_path /path/to/videoattentiontarget \
    --model gazelle_dinov2_vitl14_inout \
    --init_ckpt /path/to/gazelle_dinov2_vitl_checkpoint.pt \
    --exp_name train_gazelle_vitl_vat
```





## Citation

```
@inproceedings{ryan2025gazelle, 
    author = {Ryan, Fiona and Bati, Ajay and Lee, Sangmin and Bolya, Daniel and Hoffman, Judy and Rehg, James M.},
    title = {Gaze-LLE: Gaze Target Estimation via Large-Scale Learned Encoders},
    year = {2025},
    booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition}
}
```

## References

- Our models are built on top of pretrained DINOv2 models from PyTorch Hub ([GitHub repo](https://github.com/facebookresearch/dinov2)).

- Our GazeFollow and VideoAttentionTarget preprocessing code is based on [Detecting Attended Targets in Video](https://github.com/ejcgt/attention-target-detection).

- We use [PyTorch Image Models (timm)](https://github.com/huggingface/pytorch-image-models) for our transformer implementation.

- We use [xFormers](https://github.com/facebookresearch/xformers) for efficient multi-head attention.
