# 项目使用指南

## 1. 范围和当前能力

Gazelle 对一张受支持图像或一个离线视频文件执行本地注视目标推理。头部输入可来自单人回退、重复静态框、JSON/JSONL record 或 MediaPipe face/pose 感知。运行时写出独立头部观测、Gazelle prediction、配置元数据和可选可视化；它不是 webcam/real-time 管线。

PowerShell 示例从仓库根目录运行。凡命令含字面量 `USER_INPUT_PATH`，它就是模板而不是可直接运行的命令：必须把每一个 `USER_INPUT_PATH` 替换为后缀受支持且确实存在的本地文件，不能原样输入 placeholder。

## 2. 环境安装和激活

`environment.yml` 是已验证的环境定义：

```powershell
conda env create -f environment.yml
conda activate Gazelle
pip install -e .
```

已有环境只运行 `conda activate Gazelle` 和 `pip install -e .`。

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
  --gaze-inout-threshold 0.5
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
  --head-box `
  --face-box `
  --face-keypoints `
  --pose-head-points `
  --face-mesh `
  --face-pose-ray `
  --pose-head-ray `
  --reference-ray-length 2.5 `
  --gaze-inout-threshold 0.5
```

```text
MediaPipe Face Detector / Face Landmarker / Pose Landmarker
  -> fusion + 两条独立 face/pose 2D reference ray
  -> ByteTrack and 500 ms short-occlusion bridge for video
  -> post-bridge max-head arbitration
  -> normalized HeadObservation + conservative gaze eligibility
  -> 仅 eligible head -> GazellePredictor
  -> gaze heatmap / peak / in-out score + final gaze_status
  -> head_observations.jsonl / predictions.jsonl / rendered.mp4
```

首次使用可能下载 Gazelle checkpoint、DINOv2 repository/weight 和 MediaPipe task asset；有效 cache entry 会被复用。图像 ID 从零开始，视频 ID 来自 ByteTrack。`GazellePredictor` 只接收有序且 eligible 的 `HeadObservation`，Gazelle model 仍只消费 `"images"` tensor 和 `"bboxes"` list。`tracked_only`、`pose_only`、背脸/遮挡及低质量 rejection 会保留在 observation/rendering 中，但不会运行 Gazelle。eligibility 要求 perception confidence 与 face-ray confidence 均至少为 `0.50`，model-boundary selector 会再次复核 state 与 quality。wrapper 保留 `person_id` 以关联结果；`confidence` 和两条 reference ray 都只属于 sidecar metadata，is not model input。

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
| `--bbox` | 四个 float `XMIN YMIN XMAX YMAX`；可重复 | `None` | `static` provider | `static` 至少需要一个；按 `--bbox-format` 解释、clipping/normalization 后必须非空。 |
| `--bbox-format` | `normalized` 或 `pixel` | `normalized` | `static` provider | 解释 CLI `--bbox`；JSON 使用 record/head 自己的 `bbox_format`，不使用此 option。 |
| `--person-id` | integer；可重复 | `None` | `static` provider | 若提供，数量必须等于重复 `--bbox` 数；否则 ID 为 `0, 1, ...`。 |
| `--head-data` | readable path；`.jsonl` 按行解析，其他所有 suffix 按一个 JSON document 解析 | `None` | `json` provider | `json` 必填；只读该文件，本身不联网、不使用 CUDA、不写输出。 |
| `--save-heatmaps` | flag | `false` | image inference only | 写每人 `heatmaps/person_<id>.pt`；video 在处理前拒绝此 option。 |
| `--save-rendered` | flag | `false` | image/video inference | 写 overlay image 或无音频 `.mp4`；未启用时 rendering control 不产生文件作用。 |
| `--rendered-name` | 非空 leaf filename，后缀 `.png`、`.jpg` 或 `.jpeg` | `rendered.png` | rendered image | 指定 per-image 输出目录内文件名；拒绝 path component。 |
| `--output-video-name` | 非空 leaf filename，后缀 `.mp4` | `rendered.mp4` | rendered video | 指定 per-video 目录内无音频视频名；拒绝 path component。 |
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
| `--gaze-inout-threshold` | finite float，范围 `[0, 1]` | `0.5` | Gazelle output/rendering | 低于阈值时标记 `out_of_frame` 并抑制 Gazelle heatmap/arrow/peak，但保留 prediction metadata 及可选 bbox/label。 |
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

每个写入帧都运行 perception。`frame_step` 只 gate Gazelle：未选帧即使无 head 也是 `skipped`；已选但无 head 才是 `no_head`。`max_frames` 限制两个 JSONL 和 rendering。raw video heatmap export 不支持。渲染 `mp4v` 不保留源音频。

## 10. 渲染控制

只有 `--save-rendered` 才写渲染。提供 MediaPipe perception 时，每个有 head box 的 person 都绘制 **MediaPipe primary perception head box**：当前 observation 为实线，`tracked_only` 为虚线/半透明。**track-state labels default on**；`--no-track-state` 只关闭 person/state/confidence label，不改变 JSON/JSONL。

`--head-box` 控制独立的 **Gazelle prediction bbox**，要求 prediction bbox 非 null。`--face-box`、`--face-keypoints`、`--pose-head-points`、`--face-mesh` 是辅助 MediaPipe opt-in。`--face-pose-ray` 绘制蓝色 Face Landmarker reference，`--pose-head-ray` 绘制橙色、独立计算的 Pose Landmarker reference。每条 reference ray 都是无相机标定的 2D head-direction diagnostic，不是真实 eye gaze，并以最终 fused head bbox 计算请求长度。face origin 优先使用双眼中点；仅在至少三个 finite current face keypoints 仍存在时才 fallback 到 face-box center。接近 camera axis 时只显示 origin ring，因为不存在可信的 image-plane line。heatmap、gaze peak、gaze arrow、普通 label 默认开启，对应 `--no-*` flag 关闭。只有 `gaze_status=valid` 才绘制 Gazelle heatmap、contour、arrow 和 peak；`out_of_frame` 仍可保留 bbox 和 status label。`skipped`/`no_head`/`no_gaze` video frame 仍会写入并可保留 MediaPipe overlay。

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
| `gaze_eligible` | Required | boolean | 当前 MediaPipe perception 是否允许送入 Gazelle；要求 current face state 且 perception/face-ray confidence 均至少为 `0.50`。 |
| `gaze_status` | Conditional | enum string | 推理前 rejection reason：`unavailable_occluded`、`tracked_no_gaze` 或 `rejected_low_quality`。 |
| `tracking` | Required | object | 包含 Required integer `track_age_frames`、Required integer `missed_frames`、Required finite-number `missed_ms`。 |
| `face_bbox_normalized` | Conditional | number `[4]` | 当前 face bbox，顺序 `(xmin, ymin, xmax, ymax)`，clipping 到 `[0, 1]`。 |
| `face_keypoints` | Conditional | landmark array | 存在时的 face-detector keypoint。 |
| `pose_head_landmarks` | Conditional | landmark array | 存在时由 pose 得到的 head/shoulder landmark。 |
| `pose_head_keypoints` | Conditional | named landmark object | 可靠的 `nose`、eye、ear、mouth 和 shoulder point；不依赖 filtered landmark order。 |
| `facial_transformation_matrix` | Conditional | nested finite-number arrays | serializer preserves supplied row lengths。MediaPipe adapter 要求 at least three rows，且 at least three values in each of the first three rows；它 does not enforce rectangularity。 |
| `head_pose` | Conditional | object | finite degree 值 `yaw_deg`、`pitch_deg`、`roll_deg`。 |
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
| `head_pose.yaw_deg`, `pitch_deg`, `roll_deg` | Required inside Conditional `head_pose` | finite number | 单位 degree 的 Euler-like head-pose angle。 |

`track_age_frames` 是 track age；`missed_frames`、`missed_ms` 表示上次当前 observation 后连续 bridge reuse 的帧数和时间。因此 `tracked_only` 是 stale bridged box，不是 fresh detection，并且绝不会送入 Gazelle。单人模式在 bridge 后最多保留一个 identity，并裁掉被新 observation 替换的 stale bridge state。

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
| `status` | Required | enum string | `ok`、`no_head`、`no_gaze`、`skipped` 或 schema-supported `error`；`no_gaze` 表示有 head 但没有 eligible head，`frame_step` 排除 frame 时 `skipped` 优先。 |
| `width`, `height` | Required | positive integer | frame pixel 尺寸。 |
| `people` | Required | array | 除 `status` 为 `ok` 外均为空。 |
| `inference_ms` | Conditional | finite number | Gazelle inference 已运行时输出。 |
| `error` | Conditional | string | serializer 支持；当前 pipeline 会 raise，而不写 error row。 |

### Run configuration

`run_config.json` 先对已验证的 `RuntimeConfig` 执行 `dataclasses.asdict()`，因此 Python tuple 在 JSON 中成为 array。base object 始终含以下全部 44 个 key，包括值为 `null` 的 key。

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
| `gaze_inout_threshold` | number (non-null) | 来自 `--gaze-inout-threshold` 的 final Gazelle in/out rendering threshold，范围 `[0, 1]`。 |
| `heatmap_contour_quantile` | number (non-null) | 来自 `--heatmap-contour-quantile` 的 finite contour threshold quantile，范围 `[0, 1]`。 |
| `heatmap_contour_width` | integer or null (nullable) | 来自 `--heatmap-contour-width` 的 positive contour width；自动 width 时为 null。 |
| `output_fps` | number or null (nullable) | 来自 `--output-fps` 的 positive finite fallback，未提供时为 null；video 会用 resolved writer/tracker FPS override。 |
| `max_frames` | integer or null (nullable) | 来自 `--max-frames` 的 positive frame limit；无显式 limit 时为 null。 |
| `frame_step` | integer (non-null) | 来自 `--frame-step` 的 positive Gazelle inference stride。 |
| `output_video_name` | string (non-null) | 来自 `--output-video-name` 的已验证 rendered-video leaf `.mp4` filename。 |
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

CPU construction 临时禁用 xFormers。只有 resolved device 是 CUDA 且没有 `XFORMERS_DISABLED` 时，CUDA construction 才请求 xFormers；是否可用仍取决于安装的 DINOv2/xFormers 环境。可选 Triton 缺失且用户未设 override 时，运行时临时设置 `XFORMERS_FORCE_DISABLE_TRITON=1`，但不禁用其他 xFormers operator。`--prepare-only` 为 strict load 强制关闭 xFormers，因此可能出现非致命 disabled/not-available 信息。long-lived process 不能在不兼容的已初始化 DINOv2 xFormers state 间切换；请启动新 process。

## 14. 常见错误和运行限制

不支持的 suffix、缺少 input/head-data/checkpoint、malformed/duplicate JSON record、无效 box/device、provider prerequisite 都会明确失败。static ID count 必须等于 bbox count。normalized/pixel box 必须 finite，normalization/clipping 后仍非空。output conflict 需另一个 root 或 `--overwrite`；cache/network failure 会停止准备或推理。

**known runtime limitation：** OpenCV video timestamp 会为 MediaPipe 四舍五入为 integer ms，并且 must strictly increase after rounding。重复 timestamp 或 sub-millisecond collision 可能使运行 abort。source FPS 无效时，即使 `--output-fps` 控制不同的 writer/tracker FPS，reader timestamp fallback 仍是 30 FPS；两个 clock 可能偏离并影响 bridge timing。这是当前行为，不是 desired behavior。

Perception quality 依赖 visible-face evidence。`pose_only` 使用近似 pose-only geometry；stale bridge box 在快速移动时最多可滞后 `--head-track-max-gap-ms`。极端 profile、遮挡、mask/glasses/helmet 等 PPE、motion blur、low resolution 都会降低 detection/pose quality。虽然 `--max-heads` 最多支持 10，当前系统仍只有 limited real multi-person validation。

没有 webcam/real-time mode、自动 ROI/process logic、Multi-Pose integration、audio remuxing、raw video heatmap export 或高性能 asynchronous inference。asset 缓存后 MediaPipe/tracking 在本地运行；rendered video 无音频。

## 15. 验证命令

以下检查 offline 且不构造模型：

```powershell
conda activate Gazelle
python main.py --help
python main.py --list-models
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-usage-docs-pycache"
python -m unittest tests.test_usage_docs -v
Remove-Item Env:PYTHONPYCACHEPREFIX
```
