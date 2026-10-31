# 项目使用指南

迁移电脑和跨 agent 开发请参阅[交接指南](../handoff/HANDOFF_CN.md)与[共用协作流程](../rules/AGENT_WORKFLOW_CN.md)。

## 1. 范围和当前能力

Gazelle 对一张受支持图像或一个离线视频文件执行本地注视目标推理。头部输入可来自单人回退、重复静态框、JSON/JSONL record 或 MediaPipe face/pose 感知。运行时写出独立头部观测、Gazelle prediction、配置元数据和可选可视化；它不是 webcam/real-time 管线。

PowerShell 示例从仓库根目录运行。凡命令含字面量 `USER_INPUT_PATH`，它就是模板而不是可直接运行的命令：必须把每一个 `USER_INPUT_PATH` 替换为后缀受支持且确实存在的本地文件，不能原样输入 placeholder。

## 2. 环境安装和激活

`environment.yml` 描述当前 `Gazelle-next` 环境：Python 3.14（实际验证为 3.14.8）、PyTorch 2.14.1 与 CUDA 13.0 wheels、MediaPipe 1.1.1、OpenCV 5.0。显式固定版本为 `torch==2.14.1+cu130`, `torchvision==0.29.1+cu130`, `timm==1.0.30`, `numpy==2.5.4`, `scipy==1.18.1`, `pandas==2.3.3`, `matplotlib==3.11.2`, `scikit-learn==1.9.1`, `pillow==12.3.0`, `opencv-python==5.0.0.93`, `opencv-contrib-python==5.0.0.93`, `mediapipe==1.1.1`, `trackers==2.6.1`, `supervision==0.30.9`, `av==19.0.1`。pandas 保留在 2.3 系列，因为数据预处理脚本尚未用 pandas 3.0 验证。

`environment_py311.yml` 逐字节保留上一版 Python 3.11 定义，仍声明 `name: Gazelle`；本机现有环境原样保留作回退。`environment_1.0.yml` 是更早的 NumPy 1.26.4 参考定义，也声明为 `Gazelle`；需要并行创建时应另起环境名。

显式依赖清单的变化如下：

- 不再列出 `torchaudio`：仓库代码不使用，评估的依赖栈中没有配套 torch 2.14 的音频包。
- 不再列出 `xformers`：评估过的 Windows 包与当前 torch 版本不配套，或缺少 CUDA operator。DINOv2 使用 PyTorch 的 `scaled_dot_product_attention`。
- 不再列出 `ultralytics`：仓库代码不导入，YOLO 推理和导出未经验证。
- `polars`、`polars-runtime-32`、`nvidia-ml-py` 随未使用的 Ultralytics 依赖组移除。
- `pydeprecate` 与 `defusedxml` 不再显式固定版本，但仍作为 trackers/supervision 必需的间接依赖安装：`pydeprecate==0.13.0`、`defusedxml==0.7.1`。不能为了匹配清单中的省略而卸载它们。

已有安装只需激活，不重新安装包：

```powershell
conda activate Gazelle-next
```

新机器获得创建环境授权后执行：

```powershell
conda env create -f environment.yml
conda activate Gazelle-next
pip install -e .
```

创建会下载依赖并写入新的 `Gazelle-next` 环境，editable 安装也会修改环境；二者都不运行推理。从仓库根目录使用 `python main.py` 可直接运行源码。不要重新创建或 prune 已有环境。

回退时，本机保留了旧环境就直接 `conda activate Gazelle`；仅在旧环境不存在且获准重建时运行 `conda env create -f environment_py311.yml`。上游训练脚本仍需另行安装 `wandb`，本次切换不代表训练已验证。

## 3. 快速开始和资源准备

```powershell
python main.py --help
python main.py --list-models
python main.py --prepare-only --model gazelle_dinov2_vitb14_inout --cache-dir models
python main.py --prepare-only --head-source mediapipe --pose-model full --cache-dir models
```

`--help` 和 `--list-models` 不构造模型、不下载、不使用 CUDA、不写输出。`--prepare-only` 不处理媒体或写 prediction，但会构造 DINOv2 以严格加载 checkpoint，并可能下载 Gazelle checkpoint 和 DINOv2 repository/weight。MediaPipe 形式还会准备 face detector、face landmarker 和所选 pose landmarker。

## 4. 端到端 MediaPipe 头部感知和注视推理

此图像命令可从仓库根目录运行，因为 `assets\the_office.png` 是 tracked asset。首次使用可能下载 model/task 资源，并写入 `outputs\the_office_gazelle`：

```powershell
python main.py --input assets\the_office.png `
  --output-dir outputs `
  --overwrite `
  --head-source mediapipe `
  --max-heads 1 `
  --pose-model full `
  --model gazelle_dinov2_vitb14_inout `
  --device auto `
  --cache-dir models `
  --save-rendered `
  --head-box `
  --face-box `
  --face-keypoints `
  --pose-head-points `
  --face-mesh `
  --face-pose-ray `
  --pose-head-ray `
  --reference-ray-length 2.5 `
  --gaze-inout-threshold 0.5 `
  --gazelle-head-mode eligible `
  --gaze-render-mode valid-only
```

下面的视频工作流明确是模板，因为仓库没有提交任何视频。执行前将 `USER_INPUT_PATH` 替换为确实存在的受支持视频；only the input path must be supplied（只需提供输入路径）。保留其余全部参数，即可维持 MediaPipe、ByteTrack、500 ms bridge、Gazelle、cache 选择和 rendering：

```powershell
python main.py --input USER_INPUT_PATH `
  --output-dir outputs `
  --overwrite `
  --head-source mediapipe `
  --max-heads 1 `
  --pose-model full `
  --head-track-max-gap-ms 500 `
  --model gazelle_dinov2_vitb14_inout `
  --device cuda `
  --cache-dir models `
  --save-rendered `
  --video-codec mp4v `
  --head-box `
  --face-box `
  --face-keypoints `
  --pose-head-points `
  --face-mesh `
  --face-pose-ray `
  --pose-head-ray `
  --reference-ray-length 2.5 `
  --gaze-inout-threshold 0.5 `
  --gazelle-head-mode eligible `
  --gaze-render-mode valid-only
```

为了进行探索性对比，请将下面的 `DIAGNOSTIC_VIDEO_PATH` 替换为已有视频。该命令会把指定的保守及诊断 MediaPipe state/view 送入 Gazelle，并同时渲染 in-frame 与 out-of-frame prediction：

```powershell
python main.py --input DIAGNOSTIC_VIDEO_PATH `
  --output-dir outputs `
  --overwrite `
  --head-source mediapipe `
  --gazelle-head-mode face_pose face_only pose_only back_or_occluded tracked_only `
  --gaze-render-mode all-predictions `
  --face-pose-ray `
  --pose-head-ray `
  --save-rendered `
  --video-codec avc1
```

这是诊断模式。`tracked_only` 仍只限于 active short-occlusion bridge，不能恢复已过期 track。stale、遮挡、pose-only 或其他 non-eligible head 的 prediction 属于探索性 model output，不能视为经过验证的真实眼睛 gaze measurement。

```text
MediaPipe Face Detector / Face Landmarker / Pose Landmarker
  -> fusion + 两条独立 face/pose 2D reference ray
  -> ByteTrack and 500 ms short-occlusion bridge for video
  -> post-bridge max-head arbitration
  -> normalized HeadObservation + conservative gaze eligibility
  -> 配置的 Gazelle head selector -> GazellePredictor
  -> gaze heatmap / peak / in-out score + final gaze_status
  -> head_observations.jsonl / predictions.jsonl / rendered.mp4
```

首次使用可能下载 Gazelle checkpoint、DINOv2 repository/weight 和 MediaPipe task asset；有效 cache entry 会被复用。图像 ID 从零开始，视频 ID 来自 ByteTrack。默认 `--gazelle-head-mode eligible` 保留保守边界：perception confidence 与 face-ray confidence 均至少为 `0.50`，并在推理前再次复核 state 与 quality。`--gazelle-head-mode` 也可接受一个或多个采用 OR 语义的 selector：`eligible`、`observed`、`all`，state `face_pose`/`face_only`/`pose_only`/`tracked_only`，或 view `frontal`/`profile`/`back_or_occluded`/`unknown`。重复 selector 按顺序去重，出现 `all` 时统一规范化为 `all`。非 MediaPipe provider 保持原有行为。Gazelle model 仍只消费 `"images"` tensor 和 `"bboxes"` list；wrapper 保留 `person_id`，而 confidence、state、keypoint、pose 和两条 reference ray 都只属于 sidecar metadata，不是 model input。

## 5. 支持的模型和媒体格式

| Model | Backbone | In/out score |
| --- | --- | --- |
| `gazelle_dinov2_vitb14` | `dinov2_vitb14` | 无；序列化为 `inout_score: null` |
| `gazelle_dinov2_vitl14` | `dinov2_vitl14` | 无；序列化为 `inout_score: null` |
| `gazelle_dinov2_vitb14_inout` | `dinov2_vitb14` | 有 |
| `gazelle_dinov2_vitl14_inout` | `dinov2_vitl14` | 有 |

支持图像：`.jpg`、`.jpeg`、`.png`、`.bmp`、`.webp`。支持视频：`.mp4`、`.avi`、`.mov`、`.mkv`、`.m4v`。渲染图像必须是以 `.png`、`.jpg` 或 `.jpeg` 结尾的 leaf filename；渲染视频必须是 leaf `.mp4` filename。

## 6. 完整 CLI 选项参考

| Option | Accepted/validation | Default | Scope | Behavior/activity |
| --- | --- | --- | --- | --- |
| `--help` | flag | `false` | CLI inspection | 打印帮助并退出；无下载、CUDA、推理或写入。 |
| `--list-models` | flag | `false` | CLI inspection | 列出四个注册模型并退出；不构造模型、不下载、不使用 CUDA、不写入。 |
| `--prepare-only` | flag | `false` | resource preparation | 准备/严格加载 Gazelle 和 DINOv2；MediaPipe source 还准备 task asset。可能访问网络，但不把模型放到 `--device`、不运行 CUDA inference、不写 media output。 |
| `--model` | 四个注册 model name 之一 | `gazelle_dinov2_vitb14_inout` | preparation and inference | 选择 model/checkpoint metadata；准备或首次可用推理可能下载/构造资源。 |
| `--input` | 推理时为存在且受支持的图像/视频 path | `None` | inference | 除 `--list-models`/`--prepare-only` 外必填；只读取输入，输出写入 `--output-dir`。 |
| `--output-dir` | path | `outputs` | image/video inference | 输出根目录；创建 `<input-stem>_gazelle` 并写 JSON/JSONL 和请求的 media。 |
| `--overwrite` | flag | `false` | image/video inference | 复用 same-stem 输出时 recursively deletes 已有 per-input `_gazelle` 目录；有 containment/suffix guard，但删除发生在 before provider/model/resource setup，same-stem 输入会 collide。 |
| `--head-source` | `none`、`static`、`json` 或 `mediapipe` | `none` | image/video inference | 选择 provider；`static` 需 `--bbox`，`json` 需 `--head-data`，`mediapipe` 可能下载 task asset。 |
| `--max-heads` | integer `1` 到 `10` | `1` | MediaPipe image/video | 限制融合的 MediaPipe head；不限制 `static`/`json` head。 |
| `--pose-model` | `lite`、`full` 或 `heavy` | `full` | MediaPipe image/video/preparation | 选择 pose landmarker，也决定可能下载哪个 pose task asset。 |
| `--head-track-max-gap-ms` | finite float，大于 `0` | `500.0` | MediaPipe video | 配置 short-occlusion bridge；图像不使用 tracking。 |
| `--save-face-landmarks` | flag | `false` | MediaPipe observation output | 有数据时加入 `face_landmarks`，增加大小/隐私暴露；`--face-mesh` 无须它即可渲染内存 landmarks。 |
| `--gazelle-head-mode` | 一个或多个：`eligible`、`observed`、`all`、`face_pose`、`face_only`、`pose_only`、`tracked_only`、`frontal`、`profile`、`back_or_occluded`、`unknown` | `eligible` | MediaPipe-to-Gazelle scheduling | 使用 OR 语义选择有序 perception 进行推理。`eligible` 是保守策略；`observed` 排除 bridged track；`all` 包含所有 active perception。仍执行 geometry validation 和 track expiry。 |
| `--bbox` | 四个 float `XMIN YMIN XMAX YMAX`；可重复 | `None` | `static` provider | `static` 至少需要一个；按 `--bbox-format` 解释、clipping/normalization 后必须非空。 |
| `--bbox-format` | `normalized` 或 `pixel` | `normalized` | `static` provider | 解释 CLI `--bbox`；JSON 使用 record/head 自己的 `bbox_format`，不使用此 option。 |
| `--person-id` | integer；可重复 | `None` | `static` provider | 若提供，数量必须等于重复 `--bbox` 数；否则 ID 为 `0, 1, ...`。 |
| `--head-data` | readable path；`.jsonl` 按行解析，其他所有 suffix 按一个 JSON document 解析 | `None` | `json` provider | `json` 必填；只读该文件，本身不联网、不使用 CUDA、不写输出。 |
| `--save-heatmaps` | flag | `false` | image inference only | 写每人 `heatmaps/person_<id>.pt`；video 在处理前拒绝此 option。 |
| `--save-rendered` | flag | `false` | image/video inference | 写 overlay image 或无音频 `.mp4`；未启用时 rendering control 不产生文件作用。 |
| `--rendered-name` | 非空 leaf filename，后缀 `.png`、`.jpg` 或 `.jpeg` | `rendered.png` | rendered image | 指定 per-image 输出目录内文件名；拒绝 path component。 |
| `--output-video-name` | 非空 leaf filename，后缀 `.mp4` | `rendered.mp4` | rendered video | 指定 per-video 目录内无音频视频名；拒绝 path component。 |
| `--video-codec` | `mp4v` 或 `avc1` | `mp4v` | rendered video | `mp4v` 由 OpenCV 直接写入；`avc1` 要求 `PATH` 中可用 FFmpeg，并以原子方式完成 H.264/AVC 输出。未启用 `--save-rendered` 时无作用。 |
| `--output-fps` | finite float，大于 `0` | `None` | video | 仅 source FPS 无效时使用，否则 source FPS 优先；解析后的 FPS 也用于 video tracking。 |
| `--max-frames` | integer，大于等于 `1` | `None` | video | 限制解码/写入帧、两个 JSONL 和可选 rendered video。 |
| `--frame-step` | integer，大于等于 `1` | `1` | video | 每个写入帧仍运行 perception；仅当 `frame_index % frame_step == 0` 运行 Gazelle，否则 status 为 `skipped`。 |
| `--heatmap-alpha` | finite float，范围 `[0, 1]` | `0.45` | rendering | `--save-rendered` 且 heatmap drawing 开启时设置 opacity。 |
| `--no-heatmap` | flag | `false` | rendering | 禁用 heatmap overlay；不停止 prediction 或 raw image heatmap 保存。 |
| `--head-box` | flag | `false` | prediction rendering | 非 null 时绘制独立 Gazelle prediction bbox；不控制 MediaPipe primary perception head box。 |
| `--face-box` | flag | `false` | MediaPipe rendering | 有数据时绘制辅助 MediaPipe face box；不影响 Gazelle input。 |
| `--face-keypoints` | flag | `false` | MediaPipe rendering | 绘制最多六个 detector keypoint；不影响序列化 Gazelle prediction。 |
| `--pose-head-points` | flag | `false` | MediaPipe rendering | 有数据时绘制 pose head/shoulder point。 |
| `--face-mesh` | flag | `false` | MediaPipe rendering | 绘制当前内存 face landmarks；独立于 `--save-face-landmarks`。 |
| `--no-track-state` | flag | `false` | MediaPipe rendering | track-state labels default on；此 flag 隐藏 person/state/confidence label，observation sidecar 仍保留 tracking state。 |
| `--face-pose-ray` | flag | `false` | MediaPipe rendering | 绘制蓝色、无相机标定的 2D face head-pose reference ray；近轴向姿态只显示 origin marker。 |
| `--pose-head-ray` | flag | `false` | MediaPipe rendering | 绘制橙色、由 Pose Landmarker nose/eye 或 nose/ear geometry 独立估计的 2D reference ray。 |
| `--reference-ray-length` | finite float，大于 `0` | `2.5` | MediaPipe perception/rendering | 两条 ray 的长度均为 normalized head-box diagonal 的倍数，再 clipping 到画面边界。 |
| `--gaze-inout-threshold` | finite float，范围 `[0, 1]` | `0.5` | Gazelle output classification | 将低于阈值的 in/out score 分类为 `out_of_frame`，同时保留 prediction metadata。渲染抑制由 `--gaze-render-mode` 独立控制。 |
| `--gaze-render-mode` | `valid-only` 或 `all-predictions` | `valid-only` | Gazelle rendering | `valid-only` 只为 `gaze_status=valid` 绘制 Gazelle geometry；`all-predictions` 也绘制真实 `out_of_frame` heatmap/contour/arrow/peak，但不修改状态或 JSON。 |
| `--no-gaze-peak` | flag | `false` | rendering | 只隐藏 gaze peak marker；prediction 不变。 |
| `--no-gaze-arrow` | flag | `false` | rendering | 隐藏 head-center-to-peak arrow；arrow 还要求非 null bbox。 |
| `--draw-heatmap-contour` | flag | `false` | rendering | 使用 quantile/width option 启用高响应 contour。 |
| `--heatmap-contour-quantile` | finite float，范围 `[0, 1]` | `0.9` | contour rendering | 设置 contour threshold；开启 contour 时相关。 |
| `--heatmap-contour-width` | integer，大于等于 `1`，或省略 | `None` | contour rendering | 开启 contour 时覆盖自动 line width。 |
| `--no-labels` | flag | `false` | rendering | 隐藏普通 person label；不从 JSON/JSONL 删除 ID。 |
| `--device` | `auto`、`cpu`、`cuda` 或 `cuda:<non-negative-index>` | `auto` | model construction/inference | 选择 PyTorch device；显式/auto CUDA 可使用 GPU，inspection-only action 不构造模型。 |
| `--cache-dir` | path | `None` | resources | 最高优先 cache root；随后为 `GAZELLE_CACHE_DIR`、`models`。准备/推理可能在此写 cache。 |
| `--checkpoint` | 已存在的 local file path | `None` | Gazelle resources | 绕过注册 Gazelle checkpoint 下载；DINOv2 和所选 MediaPipe asset 仍可能需要网络/cache 写入。 |
| `--force-download` | flag | `false` | registered Gazelle and selected MediaPipe resources | Gazelle checkpoint 经临时替换重新下载，但无 digest 验证；MediaPipe asset 暂存并 SHA-256 验证。给出 `--checkpoint` 时不作用于 Gazelle。 |

## 7. 头部输入 providers：`none`、`static`、`json` 和 `mediapipe`

`none` 提供 `HeadObservation(person_id=0, bbox=None, confidence=None)` 作为 Gazelle 单人无框回退。`static` 使用重复 CLI box：

```powershell
python main.py --input assets\the_office.png --output-dir outputs --overwrite `
  --head-source static `
  --bbox 0.10 0.12 0.22 0.30 `
  --bbox 0.45 0.10 0.58 0.31 `
  --bbox-format normalized `
  --person-id 10 `
  --person-id 11
```

`json` 加载第 11 节 record。`mediapipe` 准备官方 task asset、融合 face/pose evidence、返回确定的 image ID，并为 video 增加 ByteTrack 和 short-occlusion bridge。

## 8. 图像工作流

可运行的回退推理：

```powershell
python main.py --input assets\the_office.png --output-dir outputs --overwrite `
  --head-source none `
  --model gazelle_dinov2_vitb14_inout `
  --cache-dir models
```

可运行的 raw heatmap 和 image rendering：

```powershell
python main.py --input assets\the_office.png --output-dir outputs --overwrite `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --save-heatmaps `
  --save-rendered `
  --rendered-name rendered.jpg `
  --head-box
```

图像输出为 `head_observations.json`、`predictions.json`、`run_config.json`、可选 `heatmaps/person_<id>.pt` 和可选 rendered image。provider 无 head 时不构造 Gazelle model。

## 9. 离线视频工作流

仓库没有 tracked 的受支持 video fixture，因此每个 video 命令都是模板。将 `USER_INPUT_PATH` 替换为存在的 `.mp4`、`.avi`、`.mov`、`.mkv` 或 `.m4v` 文件。

Frame stepping/limit 模板：

```powershell
python main.py --input USER_INPUT_PATH --output-dir outputs --overwrite `
  --head-source static `
  --bbox 100 80 220 230 `
  --bbox-format pixel `
  --max-frames 100 `
  --frame-step 2 `
  --save-rendered `
  --head-box
```

每个写入帧都运行 perception。`frame_step` 只 gate Gazelle：未选帧即使无 head 也是 `skipped`；已选但无 head 才是 `no_head`。`max_frames` 限制两个 JSONL 和 rendering。raw video heatmap export 不支持。所有 rendered output 都是无音频视频。

默认 `--video-codec mp4v` 保持现有 OpenCV `VideoWriter` 直接写入路径，不需要 FFmpeg。如需更适合浏览器播放的 H.264/AVC，请安装 FFmpeg 并确保 `ffmpeg` 位于 `PATH`，然后运行：

```powershell
python main.py --input USER_INPUT_PATH --output-dir outputs --overwrite `
  --head-source mediapipe `
  --save-rendered `
  --video-codec avc1
```

`avc1` 路径先把 rendered frame 流式写入临时 `mp4v` source，并在 video/provider/model 构建前探测 FFmpeg；encoder 优先选择 `h264_nvenc`，如果 NVENC 在实际执行时不可用则重试 `libx264`。输出使用 `yuv420p`、`-movflags +faststart` 和 `-an`，只有编码成功后才原子替换正式文件。成功或失败都会清理临时 source/candidate。仅指定 `avc1` 而未启用 `--save-rendered` 时，不会探测或运行 FFmpeg。

## 10. 渲染控制

只有 `--save-rendered` 才写渲染。提供 MediaPipe perception 时，每个有 head box 的 person 都绘制 **MediaPipe primary perception head box**：当前 observation 为实线，`tracked_only` 为虚线/半透明。**track-state labels default on**；`--no-track-state` 只关闭 person/state/confidence label，不改变 JSON/JSONL。

`--head-box` 控制独立的 **Gazelle prediction bbox**，要求 prediction bbox 非 null。`--face-box`、`--face-keypoints`、`--pose-head-points`、`--face-mesh` 是辅助 MediaPipe opt-in。`--face-pose-ray` 绘制蓝色 Face Landmarker reference，`--pose-head-ray` 绘制橙色、独立计算的 Pose Landmarker reference。每条 reference ray 都是无相机标定的 2D head-direction diagnostic，不是真实 eye gaze，并以最终 fused head bbox 计算请求长度。face origin 优先使用双眼中点；仅在至少三个 finite current face keypoints 仍存在时才 fallback 到 face-box center。接近 camera axis 时只显示 origin ring，因为不存在可信的 image-plane line。heatmap、gaze peak、gaze arrow、普通 label 默认开启，对应 `--no-*` flag 关闭。默认 `--gaze-render-mode valid-only` 只为 `gaze_status=valid` 绘制 Gazelle heatmap、contour、arrow 和 peak；`out_of_frame` 仍可保留 bbox 和 status label。`--gaze-render-mode all-predictions` 也会绘制 `out_of_frame` 的实际 geometry，但不修改状态、分数或 JSON。`skipped`/`no_head`/`no_gaze` video frame 仍会写入并可保留 MediaPipe overlay。

## 11. JSON/JSONL 输入示例

只有 `.jsonl` suffix 选择 line-delimited parsing；其他任意 suffix 都作为一个 JSON document。单个 JSON object 可省略 `frame_index`，此时默认 `0`：

```json
{
  "bbox_format": "normalized",
  "heads": [
    {"person_id": 7, "bbox": [0.10, 0.12, 0.22, 0.30], "confidence": 0.98}
  ]
}
```

`bbox` 必须存在，但可在单 head no-box fallback 中为 `null`，例如 `{"heads":[{"bbox":null}]}`；multi-head inference 要求每个 bbox 都非 null。每个 head 可覆盖 record format，例如 `{"bbox_format":"pixel","bbox":[100,80,220,230]}`。`person_id` 默认为 head list index；`confidence` 可省略且必须 finite。

JSONL 每个非空行一个 object：

```json
{"frame_index":0,"timestamp_ms":0,"bbox_format":"pixel","heads":[{"person_id":7,"bbox":[100,80,220,230]}]}
{"frame_index":1,"heads":[]}
```

JSON list 也可用于 video。每个 JSON-list/JSONL record 必须含非负 integer `frame_index`，index 必须唯一，否则加载失败。每个 record 必须有 `heads` list，可含 finite `timestamp_ms`，`bbox_format` 默认 `normalized`。缺少某 frame record 时返回 no heads。

## 12. 输出目录和 record schemas

`assets\the_office.png` 写入 `outputs\the_office_gazelle`。没有 `--overwrite` 时，已有 per-input 目录会报错。启用后，清理虽有 containment 和 `_gazelle` suffix guard，但会在 before provider/model/resource setup 时 recursively deletes 已有目录。这是破坏性操作而非无条件安全保证；不同位置的 same-stem 输入共享该目录，可能 collide。

推理时，仅凭参数可判断的 static/json 错误会在任何覆盖删除前（before any `--overwrite` deletion）
以 usage error、退出码 2 拒绝。Static bbox 必须有四个有限实数（不能为 bool），坐标有序，
normalized clipping 后非空；提供 ID 时须为等量整数。pixel clipping 仍依赖图像尺寸。
校验保留 `run_config.json` 中的原始 bbox 值。JSON 路径必须是已有文件，但内容稍后才检查。
JSON 内容、MediaPipe 资源、checkpoint 和设备可用性失败仍可能发生在删除之后。
`--list-models` 与 `--prepare-only` 跳过这些仅用于推理的 provider 前提检查；
head-source/bbox-format 枚举检查始终执行。

下表中 **Required** 表示始终输出该 key，**Conditional** 表示仅在指定条件下输出，**Nullable** 表示 Required key 的值可为 JSON `null`。

### Observation frame records

图像向 `head_observations.json` 写一个 object；视频向 `head_observations.jsonl` 的每个已写帧写一行同结构 object。

| Field | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| `frame_index` | Required | integer，`>= 0` | 从零开始的 decoded frame index；图像为 `0`。 |
| `timestamp_ms` | Required | finite number | media timestamp，单位 ms；图像为 `0.0`。 |
| `status` | Required | enum string | `people` 非空时为 `ok`，否则为 `no_head`。 |
| `width`, `height` | Required | positive integer | source frame 的 pixel 尺寸。 |
| `provider` | Required | string | 所选 provider：`none`、`static`、`json` 或 `mediapipe`。 |
| `timings_ms` | Required | string 到 finite number 的 object | provider timing，单位 ms；可为空。 |
| `people` | Required | array | basic observation people 或 rich MediaPipe perception people。 |

`none`、`static`、`json` 的 basic people contract：

| Field | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| `person_id` | Required | integer | 该 record 中稳定的输入 identity。 |
| `head_bbox_normalized` | Required, Nullable | number `[4]` 或 `null` | `(xmin, ymin, xmax, ymax)`，clipping 到 `[0, 1]`；`null` 是单人 no-box fallback。 |
| `confidence` | Required, Nullable | finite number 或 `null` | provider-side observation confidence；is not model input。 |

MediaPipe rich people 保留以上 field，并增加：

| Field | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| `state` | Required | enum string | `face_pose`、`face_only`、`pose_only` 或 `tracked_only`。 |
| `view_state` | Required | enum string | `frontal`、`profile`、`back_or_occluded` 或 `unknown`。 |
| `observed` | Required | boolean | 当前帧有 evidence 时为 `true`；bridge track 为 `false`。 |
| `gaze_eligible` | Required | boolean | perception policy 给出的保守建议；要求 current face state 且 perception/face-ray confidence 均至少为 `0.50`。诊断 selector 不会修改它。 |
| `gazelle_selected` | Required | boolean | `--gazelle-head-mode` 做出的实际逐帧推理决定。被 `frame_step` 跳过的视频帧中始终为 `false`。 |
| `gaze_status` | Conditional | enum string | 推理前 rejection reason：`unavailable_occluded`、`tracked_no_gaze` 或 `rejected_low_quality`。 |
| `tracking` | Required | object | 包含 Required boolean `provisional`、Required integer `track_age_frames`、Required integer `missed_frames`、Required finite-number `missed_ms`。 |
| `face_bbox_normalized` | Conditional | number `[4]` | 当前 face bbox，顺序 `(xmin, ymin, xmax, ymax)`，clipping 到 `[0, 1]`。 |
| `face_keypoints` | Conditional | landmark array | 存在时的 face-detector keypoint。 |
| `pose_head_landmarks` | Conditional | landmark array | 存在时由 pose 得到的 head/shoulder landmark。 |
| `pose_head_keypoints` | Conditional | named landmark object | 可靠的 `nose`、eye、ear、mouth 和 shoulder point；不依赖 filtered landmark order。 |
| `facial_transformation_matrix` | Conditional | nested finite-number arrays | serializer preserves supplied row lengths。MediaPipe adapter 要求 at least three rows，且 at least three values in each of the first three rows；它 does not enforce rectangularity。 |
| `head_pose` | Conditional | object | finite degree 值 `yaw_deg`、`pitch_deg`、`roll_deg`；显示图像中正 yaw 向右、正 pitch 向下、正 roll 顺时针。 |
| `face_pose_reference_ray` | Conditional | reference-ray object | 含 `source`、normalized origin/direction/endpoint、confidence、projection status 的 face reference。 |
| `pose_head_reference_ray` | Conditional | reference-ray object | 使用相同 object shape 的独立 Pose Landmarker keypoint reference。 |
| `face_landmarks` | Conditional | landmark array | 仅在数据可用且设置 `--save-face-landmarks` 时输出完整 face mesh。 |

Landmark、matrix、head-pose value shape：

| Value | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| landmark `x`, `y` | Required | finite number | provider-normalized image coordinate；不做 clipping/range validation，因此不要假定在 `[0, 1]`。 |
| landmark `z` | Conditional | finite number | relative depth，没有保证范围。 |
| landmark `visibility`, `presence` | Conditional | finite number | 有值时输出 provider value；不强制 range。 |
| `facial_transformation_matrix` rows | Conditional | nested finite-number arrays | MediaPipe 通常提供 `4 x 4`，但 serializer preserves supplied row lengths；前三行之后的 row 可保留任意 supplied length。 |
| `head_pose.yaw_deg`, `pitch_deg`, `roll_deg` | Required inside Conditional `head_pose` | finite number | 单位 degree 的显示坐标角：`yaw_right`、`pitch_down`、`roll_clockwise`。 |

视频第 0 帧与每条新轨迹首帧立即输出实际观测头部，`tracking.provisional=true`、age 为 1。
两帧索引内的确认按 IoU 关联并沿用同一 `person_id`，age 从原 spawn 帧计算。
临时观测不创建或刷新桥接状态，因此一帧误检不会产生 stale 幽灵框。
图像模式、已确认观测和 `tracked_only` 始终为 `tracking.provisional=false`。
所有 `--max-heads` 都另做一次排除全部 provisional 的选择来决定保留哪些桥接，
一帧 spawn 在该帧至少有一个已确认感知，且包含 spawn 的候选数不超过候选池上限时，
不影响桥接修剪；不满足这两个条件时，不保证连续性。
人脸与姿态匹配先取至少 3 个候选。锚点规则要求姿态鼻点在面部派生头框内；无鼻点时，
至少两个可用头部关键点须在框内；不足两个时，头框中心须在双肩之间且高于肩部中点。
视频选择先保留仍被观测的同一身份，再保留有新观测的空间连续主体，再保留身份连续主体（含有效桥接），最后按原优先级补足。
同时观测且明显分开的头框（IoU 小于 0.05）记录共存关系，阻止空间接替，直到其中一个 ID
缺席超过桥接窗口。重叠候选可以接替，这不保证真实身份一致。空间配对按全局中心距排序，
不依赖上一帧选择顺序。选择记忆使用已确认的头部，仅在已确认的选择为空时使用正式输出。
桥接修剪适用于每个 `--max-heads` 值。
图像 ID 在选择后从 0 重新编号；视频 ID 不保证从 0 开始或连续。资格阈值与 CLI 选项不变。
临时头部可以进入 Gazelle：`--gazelle-head-mode all` 会选中只有姿态的头部，
保守模式也会选中具有有效面部射线的头部。仅出现一帧且未确认的 spawn 会增加不同
`person_id` 的数量；下游统计身份时应先排除 `tracking.provisional=true` 的行。

面部参考射线把矩阵前向向量以 `(r02, -r12)` 投影到图像坐标（x 向右、y 向下）。
正 yaw 向右、正 pitch 向下、正 roll 顺时针。序列化 roll 与面部射线垂直方向使用此约定，
消费早期相反符号的下游需同步调整。两条射线仍是未标定的 2D 头姿参考，不是眼睛视线测量或校准 3D 射线。

`track_age_frames` 是 track age；`missed_frames`、`missed_ms` 表示上次当前 observation 后连续 bridge reuse 的帧数和时间。因此 `tracked_only` 是 stale bridged box，不是 fresh detection。默认 `eligible` selector 会排除它；只有在 bridge track 仍 active 时，显式 `tracked_only` 或 `all` 诊断 selector 才能把它送入 Gazelle。bridge 后最多输出 `--max-heads` 个 identity，另一次仅含已确认感知的选择决定保留哪些桥接状态。

### Prediction records

每个 prediction person 都有：

| Field | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| `person_id` | Required | integer | wrapper 用它关联回有序 input observation。 |
| `bbox_normalized` | Required, Nullable | number `[4]` 或 `null` | `[0, 1]` 中的 `(xmin, ymin, xmax, ymax)`，或 no-box fallback。 |
| `gaze_peak_normalized` | Required, Nullable | number `[2]` 或 `null` | 有值时为 `[0, 1]` 中的 normalized gaze peak `[x, y]`。 |
| `heatmap_peak_value` | Required, Nullable | finite number 或 `null` | prediction heatmap 的 peak value。 |
| `inout_score` | Required, Nullable | finite number 或 `null` | 每种 model 都输出；非 in/out model 为 `null`。 |
| `gaze_status` | Required | enum string | 应用 `--gaze-inout-threshold` 后为 `valid` 或 `out_of_frame`；null in/out score 仍为 `valid`。 |
| `heatmap_path` | Conditional | string | 仅 image 且 `--save-heatmaps` 确实写入该 person tensor 时出现。 |

图像 `predictions.json` 是一个 object：

| Field | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| `input` | Required | string | source image path。 |
| `width`, `height` | Required | positive integer | source image pixel 尺寸。 |
| `model` | Required | string | 所选 registered Gazelle model name。 |
| `people` | Required | prediction-person array | provider 没有返回 head 时为空。 |

视频 `predictions.jsonl` 每个已写帧有一条 record：

| Field | Presence | Type/shape | 含义 |
| --- | --- | --- | --- |
| `frame_index`, `timestamp_ms` | Required | integer；finite number | 与已写 observation frame 一致。 |
| `status` | Required | enum string | `ok`、`no_head`、`no_gaze`、`skipped` 或 schema-supported `error`；`no_gaze` 表示有 head 但没有 head 匹配配置的 Gazelle selector，`frame_step` 排除 frame 时 `skipped` 优先。 |
| `width`, `height` | Required | positive integer | frame pixel 尺寸。 |
| `people` | Required | array | 除 `status` 为 `ok` 外均为空。 |
| `inference_ms` | Conditional | finite number | Gazelle inference 已运行时输出。 |
| `error` | Conditional | string | serializer 支持；当前 pipeline 会 raise，而不写 error row。 |

### Run configuration

`run_config.json` 先对已验证的 `RuntimeConfig` 执行 `dataclasses.asdict()`，因此 Python tuple 在 JSON 中成为 array。base object 始终含以下全部 47 个 key，包括值为 `null` 的 key。

#### Base RuntimeConfig fields

| Field | JSON type/shape and nullability | 含义/来源 |
| --- | --- | --- |
| `model` | string (non-null) | `--model` 选择的 registered Gazelle model。 |
| `list_models` | boolean (non-null) | 来自 `--list-models` 的 action flag；只有 inference 写 `run_config.json`，所以 emitted file 中为 `false`。 |
| `prepare_only` | boolean (non-null) | 来自 `--prepare-only` 的 action flag；只有 inference 写 `run_config.json`，所以 emitted file 中为 `false`。 |
| `input_path` | string or null (nullable) | 来自 `--input` 的 base config value；action validation 前可为 null，image/video output 随后用 non-null path override。 |
| `output_dir` | string (non-null) | 来自 `--output-dir` 的 output root。 |
| `overwrite` | boolean (non-null) | `--overwrite` 是否允许 guarded recursive replacement per-input directory。 |
| `head_source` | string (non-null) | 来自 `--head-source` 的 provider：`none`、`static`、`json` 或 `mediapipe`。 |
| `max_heads` | integer (non-null) | 来自 `--max-heads` 的已验证 MediaPipe limit，范围 `1` 到 `10`。 |
| `pose_model` | string (non-null) | 来自 `--pose-model` 的 MediaPipe pose asset：`lite`、`full` 或 `heavy`。 |
| `head_track_max_gap_ms` | number (non-null) | 来自 `--head-track-max-gap-ms` 的 positive finite bridge gap，单位 ms。 |
| `save_face_landmarks` | boolean (non-null) | `--save-face-landmarks` 是否启用 full face-landmark sidecar field。 |
| `bboxes` | array of number `[4]` arrays (non-null; may be empty) | 重复 `--bbox` 的值，坐标系由 `bbox_format` 指定。 |
| `bbox_format` | string (non-null) | 来自 `--bbox-format` 的 CLI static-box format：`normalized` 或 `pixel`。 |
| `person_ids` | array of integers or null (nullable) | 重复 `--person-id` 的值；自动生成 ID 时为 null。 |
| `head_data` | string or null (nullable) | 来自 `--head-data` 的 JSON/JSONL provider path。 |
| `save_heatmaps` | boolean (non-null) | `--save-heatmaps` 是否请求写 raw image heatmap tensor。 |
| `save_rendered` | boolean (non-null) | `--save-rendered` 是否请求 rendered image/video output。 |
| `rendered_name` | string (non-null) | 来自 `--rendered-name` 的已验证 rendered-image leaf filename。 |
| `heatmap_alpha` | number (non-null) | 来自 `--heatmap-alpha` 的 finite heatmap opacity，范围 `[0, 1]`。 |
| `draw_heatmap` | boolean (non-null) | 有效的 positive heatmap-overlay state；只有 `--no-heatmap` 使其为 false。 |
| `draw_head_box` | boolean (non-null) | 来自 `--head-box` 的有效 positive Gazelle prediction-bbox state。 |
| `draw_gaze_peak` | boolean (non-null) | 有效的 positive gaze-peak state；只有 `--no-gaze-peak` 使其为 false。 |
| `draw_gaze_arrow` | boolean (non-null) | 有效的 positive gaze-arrow state；只有 `--no-gaze-arrow` 使其为 false。 |
| `draw_heatmap_contour` | boolean (non-null) | 来自 `--draw-heatmap-contour` 的有效 positive contour state。 |
| `draw_labels` | boolean (non-null) | 有效的 positive general-label state；只有 `--no-labels` 使其为 false。 |
| `draw_face_box` | boolean (non-null) | 来自 `--face-box` 的有效 positive auxiliary face-box state。 |
| `draw_face_keypoints` | boolean (non-null) | 来自 `--face-keypoints` 的有效 positive detector-keypoint state。 |
| `draw_pose_head_points` | boolean (non-null) | 来自 `--pose-head-points` 的有效 positive pose-point state。 |
| `draw_face_mesh` | boolean (non-null) | 来自 `--face-mesh` 的有效 positive face-mesh state。 |
| `draw_track_state` | boolean (non-null) | 有效的 positive track-label state；只有 `--no-track-state` 使其为 false。 |
| `draw_face_pose_ray` | boolean (non-null) | 来自 `--face-pose-ray` 的有效 positive face reference-ray state。 |
| `draw_pose_head_ray` | boolean (non-null) | 来自 `--pose-head-ray` 的有效 positive pose reference-ray state。 |
| `reference_ray_length` | number (non-null) | 来自 `--reference-ray-length` 的 positive finite head-box diagonal multiplier。 |
| `gaze_inout_threshold` | number (non-null) | 来自 `--gaze-inout-threshold` 的 Gazelle in/out classification threshold，范围 `[0, 1]`。 |
| `gazelle_head_mode` | string array (non-null) | 来自 `--gazelle-head-mode` 的已验证、去重 selector sequence；默认 `["eligible"]`，输入包含 `all` 时规范化为 `["all"]`。 |
| `gaze_render_mode` | string (non-null) | 来自 `--gaze-render-mode` 的已验证 rendering mode：`valid-only` 或 `all-predictions`。 |
| `heatmap_contour_quantile` | number (non-null) | 来自 `--heatmap-contour-quantile` 的 finite contour threshold quantile，范围 `[0, 1]`。 |
| `heatmap_contour_width` | integer or null (nullable) | 来自 `--heatmap-contour-width` 的 positive contour width；自动 width 时为 null。 |
| `output_fps` | number or null (nullable) | 来自 `--output-fps` 的 positive finite fallback，未提供时为 null；video 会用 resolved writer/tracker FPS override。 |
| `max_frames` | integer or null (nullable) | 来自 `--max-frames` 的 positive frame limit；无显式 limit 时为 null。 |
| `frame_step` | integer (non-null) | 来自 `--frame-step` 的 positive Gazelle inference stride。 |
| `output_video_name` | string (non-null) | 来自 `--output-video-name` 的已验证 rendered-video leaf `.mp4` filename。 |
| `video_codec` | string (non-null) | 来自 `--video-codec` 的已验证 rendered-video codec：`mp4v` 或 `avc1`。 |
| `device` | string (non-null) | 来自 `--device` 的已验证 request：`auto`、`cpu`、`cuda` 或 indexed CUDA。 |
| `cache_dir` | string or null (nullable) | 来自 `--cache-dir` 的显式 cache root；使用 environment/default precedence 时为 null。 |
| `checkpoint` | string or null (nullable) | 来自 `--checkpoint` 的 local Gazelle checkpoint path；使用 registered resource 时为 null。 |
| `force_download` | boolean (non-null) | `--force-download` 是否请求刷新 eligible registered resource。 |

大多数 CLI name 通过把 hyphen 改为 underscore 得到 config name。显式 CLI-to-config rename 是 `--input` -> `input_path`、`--bbox` -> `bboxes`、`--person-id` -> `person_ids`。positive `draw_*` booleans 保存有效行为，而不是 negative flag 的拼写：`--no-heatmap` -> `draw_heatmap`、`--head-box` -> `draw_head_box`、`--no-gaze-peak` -> `draw_gaze_peak`、`--no-gaze-arrow` -> `draw_gaze_arrow`、`--draw-heatmap-contour` -> `draw_heatmap_contour`、`--no-labels` -> `draw_labels`、`--face-box` -> `draw_face_box`、`--face-keypoints` -> `draw_face_keypoints`、`--pose-head-points` -> `draw_pose_head_points`、`--face-mesh` -> `draw_face_mesh`、`--no-track-state` -> `draw_track_state`、`--face-pose-ray` -> `draw_face_pose_ray`、`--pose-head-ray` -> `draw_pose_head_ray`。`--no-*` mapping 会反转，因此 drawing 仍启用时 config value 为 `true`。

#### Image/video additions and overrides

| Run | Key | JSON type/shape and nullability | 含义/来源 |
| --- | --- | --- | --- |
| image | `input_path` | string (non-null) | 用 stringified source image path override nullable base value。 |
| image | `image_width` | integer (non-null) | 新增 source image width，单位 pixel。 |
| image | `image_height` | integer (non-null) | 新增 source image height，单位 pixel。 |
| video | `input_path` | string (non-null) | 用 stringified source video path override nullable base value。 |
| video | `width` | integer (non-null) | 新增 decoded video width，单位 pixel。 |
| video | `height` | integer (non-null) | 新增 decoded video height，单位 pixel。 |
| video | `source_fps` | number (non-null) | 新增 raw OpenCV source FPS；它可能是 invalid FPS value。 |
| video | `output_fps` | number (non-null) | 用 resolved positive finite writer/tracker FPS override nullable base value。 |
| video | `frames_read` | integer (non-null) | 新增 decoded frame 的 nonnegative read count。 |
| video | `frames_written` | integer (non-null) | 新增 observation/prediction record 和 output frame 的 nonnegative written count。 |
| video | `container_frame_count` | integer or null (nullable) | 正的容器估算帧数；未知时为 null。 |
| video | `frames_required` | integer or null (nullable) | 最少要求的解码帧数；未知时为 null。 |
| video | `decode_complete` | boolean or null (nullable) | 是否达到要求帧数；未检查时为 null。 |
| video | `timestamp_sources` | object (non-null) | `container`、`repaired`、`fps_fallback` 三类整数计数。 |

图像共有 49 个唯一键，视频共有 56 个唯一键。容器帧数为 N 时，
T = max(2, ceil(0.005 * N))。`--max-frames` 不超过 N - T 时必须读出全部请求帧数；
否则 `frames_required` 为 max(0, N - T)。未知帧数不检查。截断会以非零码退出，
保留部分 JSONL 和带有 `decode_complete: false` 的 `run_config.json`。启用渲染时，
`avc1` 跳过 H.264 终结，只留下这些文件；`mp4v` 还会留下不完整的 `rendered.mp4`。

## 13. 缓存、下载、device 选择和 xFormers 说明

Cache 优先级为 `--cache-dir`、`GAZELLE_CACHE_DIR`、`models`：

```text
models/
  checkpoints/
  mediapipe/
  torch_hub/
```

缺失 entry 可能联网获取注册 Gazelle checkpoint、DINOv2 repository/weight 和所选 MediaPipe asset。Gazelle checkpoint 下载在替换前使用临时目录，但没有 pinned digest check；`--prepare-only` 随后通过 strict load 验证 checkpoint structure/key/shape。MediaPipe cache/download asset 对 pinned SHA-256 校验并暂存后原子替换。`--checkpoint` 只绕过注册 Gazelle 下载。

Supply-chain boundary：首次 uncached DINOv2 construction 会对 unpinned `facebookresearch/dinov2` repository code 调用 `torch.hub.load`。它可能获取并执行 remote Python，而不只是 weight。请只使用 trusted network/environment；受控部署应使用 pre-reviewed cache。runtime 不声称 immutable repository pin，也不声称 Gazelle checkpoint weight-integrity verification。

当前 `Gazelle-next` 环境不安装 xFormers，DINOv2 使用 PyTorch 的 `scaled_dot_product_attention`。运行时保留对装有 xFormers 环境的兼容规则：CPU construction 和 `--prepare-only` 禁用它；CUDA 可在未设置 `XFORMERS_DISABLED` 时请求使用。可选 Triton 缺失且用户未设 override 时，`XFORMERS_FORCE_DISABLE_TRITON=1` 只跳过该探测，不禁用其他 xFormers operator，也不修改环境。strict load 时仍可能出现非致命的 xFormers-disabled/not-available 提示。DINOv2 缓存 backend 选择，因此 long-lived process 若要切换不兼容的 CPU/prepare-only 与启用 xFormers 的 CUDA mode，须启动新 process。

## 14. 常见错误和运行限制

不支持的 suffix、缺少 input/head-data/checkpoint、malformed/duplicate JSON record、无效 box/device、provider prerequisite 都会明确失败。static ID count 必须等于 bbox count。normalized/pixel box 必须 finite，normalization/clipping 后仍非空。output conflict 需另一个 root 或 `--overwrite`；cache/network failure 会停止准备或推理。

读取器保留有限、非负且取整后严格递增（strictly increase after rounding）的容器时间戳。重复、倒退或 sub-millisecond 冲突做最小整数毫秒修补。缺失时间戳指非有限值、负数，以及下标 2 起的零值，回退公式为 `max(prev_out + 1000 / fps, p + 1)`：取上一帧未取整输出加一个标称帧间隔、与上一帧取整后加 1 ms 两者中的较大值。首帧无效时间戳取零；下标 1 的零值现在记为 1 ms，不再按帧号推算。无法表示有限递增时间时明确报错。这些修补不实现多机同步。

**known runtime limitation：** source FPS 无效时，即使 `--output-fps` 控制不同的 writer/tracker FPS，reader timestamp fallback 仍是 30 FPS；两个 clock 可能偏离并影响 bridge timing。

AVI 空包可从仓库根目录执行以下无损重封装，替换输入、输出路径：

```powershell
ffmpeg -n -fflags +genpts -i "C:\path\to\read-only-source\input.avi" -map 0:v:0 -c:v copy -bsf:v "noise=drop=lt(size\,64)" "C:\path\outside-repository\remuxed.mp4"
```

此命令调用本地 FFmpeg，写入不含音频的新 MP4，保留原始输入；`-n` 保护已有输出。不执行推理、不使用 CUDA、不联网、不下载。

Perception quality 依赖 visible-face evidence。`pose_only` 使用近似 pose-only geometry；stale bridge box 在快速移动时最多可滞后 `--head-track-max-gap-ms`。极端 profile、遮挡、mask/glasses/helmet 等 PPE、motion blur、low resolution 都会降低 detection/pose quality。虽然 `--max-heads` 最多支持 10，当前系统仍只有 limited real multi-person validation。

没有 webcam/real-time mode、自动 ROI/process logic、Multi-Pose integration、audio remuxing、raw video heatmap export 或高性能 asynchronous inference。asset 缓存后 MediaPipe/tracking 在本地运行；rendered video 无音频。

## 15. 研究数据工具

接入范围为旧七次录制加 `20261016`、`20261023`；`20261030` 按单独契约接入。
源根目录为只读的 `E:\Gazelle_Workdata`。清单与重封装支持重复的 `--session` 参数，
保留未选录制的旧行；根目录有未知录制时不要全量扫描。共享清单追加前先备份。
带哈希的旧产物保留历史路径作为出处记录；迁移后的重封装输入按相对路径、大小与 SHA-256 核对。

可选 webcam `cam_w` 使用 `WIN_YYYYMMDD_HH_MM_SS_Pro.mp4` 文件名时间加原始 PTS
（`filename_clock`，斜率 1；电脑时间不带时区，按 UTC epoch 秒编码）。
它写在 `auxiliary_cameras`，必需的 `cameras` 仍为 A/B/E，重叠段只由三机决定。
W 沿用同一 5 Hz 校准方法与不确定区间规则，输出仅视频的 1280×720 `proxy_webcam.mp4` 与旁注；
A/B/E 仍为 1920×1080。W–B 沿用 A–B 残差门槛；W 失败仅将 W 标为不可用，不阻塞三机。
时钟抽查只做 A/B/E。这些工具在本机 CPU 解码/编码（重封装与代理调用 FFmpeg），不调用模型、CUDA 或下载。

已批准的新分层可用 `--no-pilot --cohort 2026-10` 与 `--worker-spans <worker_spans.json>` 抽样，
默认保留旧试标协议。每段按最大时间重叠确定 `span_id`，完全处于交接空档时归到最近片段；
相同时取较早片段，不因此重抽。抽样只读元数据与哈希并写新数据集，抽帧使用 CPU/OpenCV。
W 参考须有通过 W–B 检查且由 `proxies/manifest.json` 哈希绑定的验证结果。
每步另存 640×360 JPEG、SHA-256、缺口与 `sync_uncertain` 标记。
页面显示可收起的 W 参考及同步不确定提示；注视点仍标在原三视角拼图的 E 上。
保留已有数据集和标签；正式 `roi_r2_2026_10` 只在完整的已批准分层准备好后生成。

`sync_calibrate`、`proxies`、`sync_validate` 可用 `--inventory <inventory.json>` 解析迁移源文件：
有效的记录路径（包括重封装文件）继续使用；路径失效时，比对源 SHA 记录与文件大小，
再按清单根目录和相对路径仅在内存中解析，不重算整段源视频哈希，不改写旧映射路径。
细化切点须在 `adjacent_window_centers` 闭区间内；没有候选则保留粗切点并记 `refined=false`。
`--reuse-samples` 核对保存的样本后拟合到全新输出映射，不重新解码；生成代理时在
`session.json` 记录 `allow_internal_gaps` 与重叠范围。
清单重跑保留行序，所选根目录缺少已有源文件时拒绝。重封装即使不带 `--session` 也合并报告行，
刷新失败保留原有效行。W 文件名格式由 `tools/workdata/camera_roles.json` 统一定义。
W 事件帧失败时重做不含 W 的条图。W 验证证据缺失、迁移或过期时，新数据集 manifest
在 `webcam_unavailable` 中记录原因，A/B/E 抽样继续。
W 面板位于时间轴和类别按钮之后；加载时保留占位、隐藏旧图，不计已看步，W 失败不阻塞三视角标注。
拒绝 `review-only` 作业者文件，片段须在重叠范围内；文件头与交接行只接受许可字段。
可选文件头字段为 `clock`、`rule`、`precision_seconds`（5）、`handover_face_grace_seconds`（10）、
`status`（`approved`）与 `source_draft_sha256`；匿名规则和时钟的固定值见 `tools/workdata/workers.py`。


在现有 Gazelle-next 环境、仓库根目录运行。源目录只读，数据根放在仓库与源目录之外。
工具只使用 CPU 与磁盘，不构造模型、不使用 CUDA、不联网、不下载。
长时间任务以低优先级运行。参见[中文指南](../../tools/workdata/README_CN.md)。
重封装校验要求开头、中间各连续 30 帧；尾部窗口最多读取 120 帧，必须读到 EOF 且连续成功
不少于 30 帧。最后解码时间与最后一个包的 PTS 相差不得超过 `r_frame_rate` 的一个标称帧间隔。
报告包含 `last_pts`、实际窗口解码数与 `tail_eof`。

| 入口模块 | 读取 | 写入 | 外部工具 |
| --- | --- | --- | --- |
| `tools.workdata.inventory` | 原始 AVI/MP4、旧清单哈希缓存 | 原子清单 JSON、摄像机身份与包统计 | ffprobe |
| `tools.workdata.remux` | 清单与原始 AVI | 不含音频的 MP4、`remux_report.json` | ffprobe、FFmpeg、OpenCV 解码检查 |
| `tools.workdata.osd_clock` | 本地完整视频帧图片 | 标准输出中的识别时钟或 null | CPU/OpenCV；不调用 FFmpeg 可执行程序 |
| `tools.workdata.timemap` | 清单、原始 MP4、已验证的重封装视频 | 锚点缓存与各会话时间映射 | CPU/PyAV（FFmpeg 库），不调用 FFmpeg 可执行程序 |
| `tools.workdata.sync_check` | 时间映射与对应视频 | 运动能量缓存与互相关报告 | CPU/PyAV；不调用 FFmpeg 可执行程序 |
| `tools.workdata.sync_calibrate` | v2 基础映射与源视频 | 96×54 灰度样本、来源、校准映射 | CPU/PyAV；无模型、网络或 FFmpeg 可执行程序 |
| `tools.workdata.sync_validate` | 校准代理与已有时钟抽样索引 | 残差报告、时钟检查、事件条图 | CPU/OpenCV/Pillow；无模型、网络或 FFmpeg 可执行程序 |
| `tools.workdata.proxies` | 有效时间映射与对应视频 | 每会话三段 H.264 代理、逐帧旁注、源全长解码计数与 `session.json` | CPU/PyAV、FFmpeg/libx264、ffprobe |
| `tools.validation.extract_roi_candidates` | 清单、已校验的全局摄像机重封装视频 | 每会话 12 张 JPEG、`roi/candidates.json` | CPU OpenCV/Pillow；不调用 FFmpeg 可执行程序 |
| `tools.validation.roi_server` | 候选帧、可选已有区域 | 原子区域/草稿文件、备份；按需导出参考图与类别 | 仅 127.0.0.1 本机浏览器 |
| `tools.validation.roi_regions` | 区域定义 | 校验或派生类别 JSON | 仅 CPU |
| `tools.validation.sample_segments` | 代理会话/旁注、代理哈希、可选已完成区域 | 固定种子片段清单、类别与可选区域参考图 | CPU；不解码视频、不调用 FFmpeg 可执行程序 |
| `tools.validation.extract_frames` | manifest 与对应代理视频 | 带哈希的 1920×720 三视角 JPEG，或数据集校验 | CPU/OpenCV；不调用 FFmpeg 可执行程序 |
| `tools.validation.annotate_server` | 已抽帧数据集、可选已有标注 | 修改后原子写入标注与上一版备份 | 仅 127.0.0.1 本机浏览器 |
| `tools.validation.labels validate` | 数据集与标注 JSON | 严格覆盖/schema 校验 | CPU；不解码媒体、不调用 FFmpeg 可执行程序 |
| `tools.validation.render_roi_reference` | 区域与候选帧 | 参考 PNG、各会话叠加图、类别 JSON | Pillow、已有中文字体 |

```powershell
$raw = 'E:\Gazelle_Workdata'
$data = 'C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata'
python -m tools.workdata.inventory --root $raw --out "$data\inventory\inventory.json" --session 20261016 --session 20261023
python -m tools.workdata.remux --inventory "$data\inventory\inventory.json" --out-root "$data\remux" --session 20261016 --session 20261023
```

两个入口支持 `--ffprobe`，重封装另支持 `--ffmpeg` 覆盖 PATH 查找。已有有效重封装默认跳过；
`--force` 才重做，失败仍保留旧文件。通过包数、时长、PTS 和头中尾解码检查后才发布输出。
所有派生数据不得进入 Git。

区域工具不调用模型、GPU、FFmpeg 可执行程序或外部网络。编辑器只使用本机回环 HTTP，页面资源内联。
参见[区域指南](../../tools/validation/ROI_GUIDE_CN.md)，从仓库根目录运行：

```powershell
python -m tools.validation.extract_roi_candidates --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\roi"
python -m tools.validation.roi_server --candidates "$data\roi\candidates.json" --annotator local
python -m tools.validation.roi_regions validate "$data\roi\roi_regions.json"
python -m tools.validation.render_roi_reference --regions-path "$data\roi\roi_regions.json" --candidates "$data\roi\candidates.json" --out-root "$data\roi"
```

试用时加 `--regions-path "$data\roi\review_trial.json"`，其备份、草稿独立，导出写入 `review_trial_export`。
仅打开页面不会创建正式区域。选择参考帧、画多边形、核对各日期后导出参考图与类别。
无效或自相交多边形不能保存；续标请保留原候选清单。Ctrl+C 停止服务。
导出的类别保留目标区域颜色，固定类别颜色来自配置。
先画目标区域，最后画工作区。重叠处点击选中最小区域，所选顶点始终显示在所有多边形上方。
双击闭合不会增加重复顶点，自定义目标自动使用不同颜色。导出要求 1–5 个目标、恰好一个工作区，
且没有未闭合草稿。数字键按目标绘制顺序分配，之后为 `hands_object`、`cell_other`、`away`、`absent`（最多 1–9）；
`unknown` 为 0。删除后重画会改变顺序。自动保存不表示完成：成功导出才写入
`roi_regions.complete.json`（version 2、`completed_at`、`regions_sha256`、`export_root`，以及
`exports` 中 `roi_reference.png` 与 `classes.json` 的哈希）。后续修改使完成状态失效，
需重新导出。下游工具用 `roi_regions.completed_document()` 校验完成标记与全部文件哈希。
页面显示完成状态，面积小于画面 0.5% 的区域需确认；CLI 支持 `--confirm-small` 与可选 `--out-root`。
未给 `--out-root` 时，`roi_regions.json` 导出到文件旁，其他文件名导出到 `<stem>_export/`；
完成标记始终保存在区域 JSON 旁。

时钟工具在仓库根目录运行，沿用上面的外部 `$data`：

```powershell
python -m tools.workdata.osd_clock --image C:\path\outside-repository\clock.png
python -m tools.workdata.timemap --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\timemaps_v2_base" --session 20261016
python -m tools.workdata.sync_calibrate --timemaps "$data\timemaps_v2_base" --out-root "$data\timemaps_v3" --samples-root "$data\sync_samples_v2" --session 20260828
python -m tools.workdata.sync_check --timemaps "$data\timemaps_v2" --out-root "$data\sync_checks" --session 20260828
```

这些命令不使用 GPU、模型、网络或下载。视频命令自动设为低于正常优先级，通过 PyAV
流式读取原生 PTS。v2 基础映射每文件拟合一条稳健直线，只在实际解码 PTS 不连续时分段，
不跟随显示时钟跳变；覆盖从实际首帧开始。全部锚点残差保留，要求绝对残差中位数 ≤0.5 s，
且 ≥90% 位于 ±1.5 s。不可靠时钟读数保持缺失。

同步协议 r2 以前方摄像机 B 为基准。A/E 使用 5 Hz、96×54 灰度运动信号，跨全部滞后选择六格，
以 60 s 窗口和 ±10 s 搜索测量滞后。有效窗要求 r ≥0.5、突出度 ≥0.1、峰不在边界。
Theil–Sen 拟合要求 ≥10 窗、跨度 ≥30%、每段 ≥5 窗、MAD ≤0.08 s、超出 0.2 s 的残差不超过 10%。
始终搜索每段一刀/两刀（总计 ≤3）：L1 代价下降 ≥25%，每个台阶 ≥max(0.2 s, 4×候选 MAD)。
在切点 ±120 s 内用 20 s 窗/10 s 步长，以两侧 L1 最小细化。v3 用自身基础中心 b=t+L 拟合，
显式计算 `T(b) = b - L(b)`；含义是 B 的画面时钟轴，不是校准 UTC。
负台阶保留缺口；正台阶排除 T 不小于实际切点后首帧 T 的切点前帧，使可选时间严格递增。
切点不确定区间从切点前最近有效窗中心延伸到切点后最近有效窗中心，两端各加该窗长度的一半
（长窗 60 s、细化窗 20 s）。细化窗全无效时记 `localized: false`，保留整个证据空档。
这些区间与缺口/重叠范围在旁注标为 `sync_uncertain`，抽样与下游读取同一标记。
旧凭据缺少历史版本时明确写“采样时库版本未记录”，不把后来核验时的版本当作采样版本。
校准需要作业者有可见动作，无人或静止时段不能单独校准。无法校准的摄像机明确失败，不能生成校准代理。
可选旧诊断 `sync_check` 保留三个 120 s、10 Hz 窗，单独报告边界峰和不突出峰，要求有效峰且 |lag| ≤0.5 s；
它不替代 r2 残差验收。缓存绑定映射与采样实现哈希。
`timemap --sample-cache <旧-v2-root>` 把先前解码/OCR 证据重新拟合到不同的 `--out-root`。
源/媒体签名、摄像机身份与采样参数须匹配，保留旧样本哈希和实现指纹；
此模式不解码视频、不运行 OCR，也不把旧样本称为新测量。连续相等 PTS 不属于回退。
仅修复校准拟合时，可显式复用灰度证据并输出到新映射：

```powershell
python -m tools.workdata.sync_calibrate --timemaps "$data\timemaps_v2_base" --out-root "$data\timemaps_v2_refit" --samples-root "$data\sync_samples_v2" --session 20260828 --reuse-samples
```

此模式仅使用 CPU，比较实际采样实现哈希，并核对基础映射哈希、网格、源 size/mtime、像素 SHA-256、96×54 uint8 形状、
逐步来源与完整源解码记录，不解码源视频、不推理、不使用 GPU、FFmpeg 或网络。
输出映射须尚不存在；原样本只读，`sampling_evidence` 保留其原指纹与文件哈希，并另记当前拟合实现。
源关键帧扫描只解复用到 EOF，按源 SHA、大小、mtime 缓存（`--keyframes-root`）。
换源文件或存在 previous_pts < p ≤ current_pts 的关键帧时，运动步记缺失；缺口继续缺失。
验证另外屏蔽代理关键帧，报告各机屏蔽比例；96×54 灰度缩略图用 `INTER_AREA`，校准保留 PyAV reformat。
采样与拟合分开记录指纹；旧缓存须提供独立核实来源的 `--sampling-provenance` 凭据，绑定原旁注/像素 SHA
与相同采样哈希，不能放行哈希不一致。复用仅用于拟合修复，不用于采样变更。
旧 v2 读取保留两次迭代及方程残差 / `abs(1+c1)` 的保护。
详见[中文工具指南](../../tools/workdata/README_CN.md)。

代理生成沿用外部 `$data`：

```powershell
python -m tools.workdata.proxies --timemaps "$data\timemaps_v3" --out-root "$data\proxies_v3_pending" --session 20260828 --allow-internal-gaps
python -m tools.workdata.sync_validate --proxies "$data\proxies" --timemaps "$data\timemaps_v3" --keyframes-root "$data\keyframes_v3" --out-root "$data\sync_validation" --session 20260828 --clock-samples C:\path\outside-repository\check_proxy_clocks.json
```

默认 `--step-hz 5 --size 1920 1080`、CRF 20、yuv420p、恒定帧率、不含音频。
命令以低于正常优先级使用 CPU，实际调用 FFmpeg/ffprobe，不使用模型、GPU、网络或下载。
所有源文件流式解码到 EOF，记录容器与实际解码帧数（差异超过 0.5% 需复核）；
临时视频校验后发布。匹配且有效的输出可续跑跳过，`--force` 强制重建。已有输出校验失败或指纹不匹配时，
保留文件并要求显式 `--force` 才替换。
旁注记录最近源帧、原生 PTS、时间差；超过网格半步长的差异标记为缺口。

共同覆盖包含多个区间时默认拒绝；显式 `--allow-internal-gaps` 保留整体起止间
连续时钟网格，记录全部覆盖缺口与最近帧缺口标记，不压缩时间。新增录制保留旧七次的产物；已批准的替换批次全部通过前保留旧代理原路径，之后改名备份并切换。
`sync_validate` 复用已有固定 k，依次读代理 k、旁注记录的源帧，然后以相同次序读
k−1/k+1/k−2/k+2；首次识别即停止。源帧解码 PTS 必须与旁注完全相同。
每次记录来源与两帧 96×54 缩略图的平均绝对差；仍缺失记不可评估。
`delta_distribution` 按摄像机记录可评估/不可评估/通过计数、差值的有符号最小值/中位数/最大值和绝对值 p90。
超限差值照常纳入；没有可评估读数时统计值为 null。
每会话可评估比例须 ≥90%。时钟使用所选源帧自身基础映射，`d = base_X(pts) - reading`（整秒读数），
A/B −0.5 ≤ d <1.5 s，E −1.5 ≤ d <2.5 s。`reading_minus_grid_distribution` 另报读数减网格时间作为符号旁证。
残差检查 A–B、E–B、A–E：
有效窗 ≥90% 在 ±0.2 s 内、中位 |lag| ≤0.1 s、会话中点 |offset| ≤0.1 s、|drift| ≤0.1 s/小时。
所有失败保留，不删除窗口求通过。类别为通过、未通过、`insufficient_evidence`（<10 窗或覆盖 <30%）。
A–B/E–B 必须通过；A–E 可证据不足，但须报告闭合推算。逐窗/整体 (A−B)−(E−B)−(A−E) 与端点最大偏差只报告、不设新门槛。
每会话三张作业者运动 ±1 s 条图，每个切点 ±10 s 内另选一张；回读缩略图须与验证缓存逐像素相同。
已有代理逐会话比较 v3/v2 全时长滞后：所有机位差 ≤0.05 s 时保留 v2 代理及原 SHA，否则重建，并记录来源。
仅已批准的替换批次全通过后重建试用集和已完成 ROI 的正式集；含 `sync_uncertain` 的片段在同层重抽、逐次记录。
不自动生成正式 labels。正式标注等待同步独立验收。详见
[中文工具指南](../../tools/workdata/README_CN.md)。

三视角标注在仓库根目录、Gazelle-next 环境中运行：

```powershell
$dataset = 'C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial'
python -m tools.validation.sample_segments --proxies-root "$data\proxies" --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset --validate-only
python -m tools.validation.annotate_server --dataset-root $dataset --labels-path "$dataset\review_trial.json" --annotator reviewer
# 标注后关闭本机服务，再运行：
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json"
# 单独严格检查 pilot，其他段只检查结构：
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json" --segment 20260911_pilot
```

这些工具不使用模型、GPU、下载、外部网络或 FFmpeg 可执行程序；抽帧用 CPU OpenCV 流式处理，
优先级低于正常。默认种子 20261015，每会话四层（不足 45 分钟取两层），每段 60 秒、5 Hz。
缺口时间步合计超过两秒或与 pilot 重叠时最多重抽十次，记录每次尝试；固定 pilot 放在首位并排除于评估。
每会话独立使用 `seed + int(session)`；`--sessions` 默认值为
20260821 20260828 20260903 20260911 20260925 20261002 20261009。
其他会话打印提示后忽略，manifest 记录参与抽样的会话列表。
所有代理与抽出帧均绑定 SHA-256。

显式 `--regions-path` 要求有效完成标记与导出哈希，否则报错。类别和参考图只从标记指明的目录
读取，复制前核对哈希；省略该参数时使用默认类别的 `roi_r2_trial` 试用数据集。
区域就绪后新建 `roi_r2` 用于正式标注。已有目录默认拒绝覆盖；
显式 `--overwrite` 会将整个旧目录改名为带时间的备份并保留。正式标注默认写 `labels.json`，
审查用 `--labels-path` 指向独立文件。画面加载并显示后记录已看步、创建或保存标注；每次修改原子保存
并保留上一版 `.bak`，拒绝过期版本或外部修改冲突。重启定位首个未完成段，再依次找首个未看步、
首个 null 步，否则停在第 0 步。

界面支持播放、步进、数字键变化点、删除、撤销、彩色时间轴和他人入镜区间；当前画面加载完成后
才接受判断。标注 version 3 记录合并且只增不减的 `viewed_ranges`；未看步骤即使有类别仍叠加斜线。
全部看过、有类别且注视点规则满足后，点击“本段完成”才写入 `finished_at`；修改类别、点、跳过标记或他人区间会清空完成时间。
完成条件只认此前已保存的已看范围；同请求新增范围照常保存，但不能用于本次完成判断。
修改较长片段的类别后，确认完成前请回放检查，因为“已看”只表示显示过。
播放或未播放时逐步、跳转、定位变化点产生的已看变化，最多每秒保存一次；暂停正在进行的播放、换段、完成、隐藏或关闭前立即写入。
隐藏时按正常队列等待正在进行的保存；只有 pagehide/beforeunload 直接发送 `keepalive`，服务端仍检查 revision。
关闭或网络中断不保证请求送达，关闭前应等到已保存。类别、他人区间和备注不降频，保存失败即停止编辑。
`labels validate` 的结构错误（含顶层非对象的 JSON）也输出包含段号与原因的一行错误、退出码 1，不打印 traceback。
区域保存/导出状态以服务端为准，含无变化保存。
version 1、2 标注明确拒绝，需用新工具重新标注。严格校验要求全部完成条件同时满足；可重复给出 `--segment ID`
只对指定段严格检查，其余段检查结构。草稿中的未标注与主动选择 `unknown` 不同；`--allow-incomplete` 只检查草稿，
不代表完成。详见[中文标注指南](../../tools/validation/ANNOTATION_GUIDE_CN.md)。
判断依据为眼睛优先于头部、头部优先于手部。看手或手中物体时，`hands_object` 优先于它所在的固定区域。
注视落在某区域内的桌面或物体上时用该区域。默认点在片段的第一步，否则选目标最清楚的一步。
同一片段的点与跳过标记互斥；画面外代替点，只用于整个片段的目标都在全局画面外。
部分可见时只点可见部分，不标画面外；拿不准时整段跳过。S/O 删除本片段全部点并提示个数，撤销一并恢复；
加点前先取消标记。合并片段时保留点、清除冲突标记并提示，可撤销。
键盘撤销只用 Ctrl/Cmd+Z，且不带 Shift 或 Alt；工具没有重做。其他 Ctrl/Meta/Alt 组合键保留浏览器行为，
不作标注快捷键。按住 S/O/X/Delete/数字/空格或 Ctrl/Cmd+Z 只执行一次，并阻止重复事件的浏览器默认动作；
方向键可以重复。慢帧加载就绪后停留满一个步长再前进。`hands_object` 使用亮黄绿色 `#b6ff00`。
用鼠标操作过滑块或下拉框后，可以直接使用快捷键；鼠标点击按钮后也会释放焦点。
Tab 等键盘操作保留控件焦点，备注文本框始终保留输入焦点。
四个目标时键位为 1–4 目标、5 手部/手中物体、6 `cell_other`、7 `away`、8 `absent`、0 `unknown`。
单击全局视图添加/替换当前步的点；X 删除点，S 切换 `unsure` 跳过，O 切换 `out_of_view` 画面外（仅手部/其他）。
Delete 仍删除类别变化点。每个目标/手部/其他片段至少有一点或跳过，额外点在同一片段内至少相隔 5 步（1 秒）；
away/absent/unknown 不点。当前点高亮，同片段其他点淡色显示；时间轴显示点与缺点片段。
改类别自动清理不兼容的点和标记并提示，撤销一并恢复。合并片段后若点间隔冲突，保留较早的点。
version 3 新增 `points: [{step, x, y}]`，坐标为 1920×1080 全局代理帧的有限归一化值 [0, 1]，步号唯一；
`point_skips: [{step, reason}]` 的 step 为片段起点，reason 为 `unsure` 或 `out_of_view`。
完成判断还要求类别、点与跳过标记此前已保存。编辑器和标签校验在打开标签前要求 manifest `annotation_schema_version: 3`；
旧数据集须重新生成，或按 TASK-125 第 5 条更新类别与 manifest。
经授权重新导出时，在前述 `tools.validation.render_roi_reference` 命令追加 `--backup-existing`，
把旧类别、参考图、叠加图和完成标记改名到带日期的备份目录，再用本机 CPU/Pillow 和已有字体生成新导出。
区域 JSON 不变；不调用模型、GPU、FFmpeg 可执行程序或网络。
视频、帧和标注都保存在 Git 之外，不上传。

## 16. 验证命令

以下检查 offline 且不构造模型。默认测试会 mock FFmpeg capability probe/transcode，不会运行真实 FFmpeg process：

```powershell
conda activate Gazelle-next
python main.py --help
python main.py --list-models
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-docs-pycache"
python -m unittest tests.test_usage_docs -v
Remove-Item Env:PYTHONPYCACHEPREFIX
```
