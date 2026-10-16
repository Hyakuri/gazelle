# 多视角注视区域标注指南

在仓库根目录、现有 `Gazelle-next` 环境中运行。原始视频只读；代理、拼接帧、区域文件和标注
都保存在仓库外，不提交到 Git，不上传。工具不显示模型预测，不调用模型、GPU、下载或外部服务。

## 1. 准备数据集

先完成作业数据工具的时间映射、同步检查与代理生成，见[作业数据指南](../workdata/README_CN.md)。
画面时钟相同并不保证物理事件已同步；同步检查失败的会话须经协调者复核，不能直接作为正式同步验证证据。

```powershell
conda activate Gazelle-next
$data = 'C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata'
$dataset = 'C:\Users\yun\Documents\Claude_Code\gazelle_validation\roi_r2_trial'
python -m tools.validation.sample_segments --proxies-root "$data\proxies" --dataset-root $dataset --regions-path "$data\roi\roi_regions.json"
python -m tools.validation.extract_frames --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset --validate-only
```

正式区域必须有与当前文件 SHA-256 一致的完成标记，以及至少一个目标和恰好一个工作区。
工具通过 `roi_regions.completed_document()` 检查后，从区域生成类别并复制 `roi_reference.png`。
区域尚未完成时使用 `default_classes.json`，数据集只供试用。正式区域就绪后把 `$dataset`
改为 `...\gazelle_validation\roi_r2` 重新生成；旧试用标注不会自动变成正式标注。

抽样只读取代理旁注、会话信息与哈希，不解码视频、不调用 FFmpeg。固定种子为 `20261015`，
每会话等分四层，每层均匀随机取一个完整 60 秒片段；不足 45 分钟时取两层。
若任一机位标记缺口的时间步合计超过 2 秒（同一步只计一次），在同层最多重抽 10 次，记录每次尝试；耗尽则失败，不降低标准。
另加入画面时钟 2026-09-07 22:20:00 的一分钟 pilot，置于列表最前，排除于正式评估。

目标目录已存在时拒绝覆盖。显式 `--overwrite` 会把旧目录整体改名为带时间的 `.backup-...`
再创建新数据集，保留旧帧和标注。不要把数据集根设为仓库、代理根或其上级。

抽帧使用 CPU/OpenCV，不启动 FFmpeg 可执行程序，每段生成 300 张 JPEG（默认 5 Hz、质量 85）。
前方 `cam_b` 在左上、右侧 `cam_a` 在左下，均为 640×360；全局 `cam_e` 在右侧，为 1280×720。
总尺寸 1920×720，左上角标有角色。manifest 记录每个代理及每张拼接图的 SHA-256。
可中断后重跑抽帧命令；已完成片段必须通过哈希核对才跳过。

## 2. 启动与续标

```powershell
python -m tools.validation.annotate_server --dataset-root $dataset --annotator yun
```

浏览器打开终端显示的 `127.0.0.1` 地址，默认端口 8766。页面资源内联，无外部 URL；服务只绑定本机。
默认写入 `$dataset\labels.json`。每次修改自动保存，上一版保存在 `labels.json.bak`；看到“已保存到本机”
后再关闭页面。终端 Ctrl+C 关闭服务，之后用同一命令重新打开，会定位到首个未标注步。
仅加载页面不会创建正式标注文件。不同数据集或类别配置的标注不能混用，哈希不一致时拒绝续标。

审查或试用请用独立路径：

```powershell
python -m tools.validation.annotate_server --dataset-root $dataset --labels-path "$dataset\review_trial.json" --annotator reviewer
```

先完整试标 pilot，再开始其他片段。一个一分钟片段约需 4–5 分钟，26 段约两小时，可分多次。

## 3. 判断规则

标注作业者正在看什么。优先依据头部方向和可见的眼睛，手部动作只作辅助；手与头/眼不一致时，
遵循头和眼。转头过程中，在新目标比旧目标更明确的第一步切换类别。证据不足选 `unknown`，不要猜。
第二个人入镜时另标 `other_people` 区间；若作业者正在看此人，注视类别为 `away`。

默认类别如下；正式区域可以改变目标名称、数量、颜色和数字键，以页面读取的 `classes.json` 为准。

| 键 | 类别 | 含义 |
| --- | --- | --- |
| 1 | `pick_right` | 右侧取货台 |
| 2 | `work_front` | 前方作业台上的工装、加工中的工件、使用中的工具 |
| 3 | `place_left` | 前方桌面左侧的成品放置区 |
| 4 | `cell_other` | 工作区内其他工具、资料、屏幕或设备 |
| 5 | `away` | 工作区外：过道、他人、远处背景、天花板 |
| 6 | `absent` | 作业者不在工位 |
| 0 | `unknown` | 无法判断；这是一项有效标注 |

灰色斜线是“尚未标注”（草稿内为 null），与主动选择 `unknown` 不同。只有每步都已选择类别，
片段才有完成时间。区域参考存在时可展开查看；没有参考图时显示文字定义。

## 4. 操作

- 空格播放/暂停，可选 1× 或 0.5×；左右方向键或按钮移动 0.2 秒，另有 ±1 秒按钮。
- 注视目标改变时按数字键：从当前步开始标注，直到下一个已有变化点。也可点击类别按钮。
- 点击彩色时间轴、拖动滑块或点击变化点按钮定位。Delete 删除当前步的变化点；首步删除后恢复未标注。
- Ctrl+Z 或“撤销”恢复最近一次修改；撤销同样立即保存。刷新页面后撤销栈清空，已保存内容仍保留。
- “下一个未标注”寻找尚未选择类别的位置；完成所有片段后运行严格校验。
- 在第二个人出现时点击“他人入镜开始”，最后可见的一步点击“结束（含当前步）”。相邻/重叠区间合并；
  点击已保存区间旁的 × 删除。尚未结束的起点只保留在当前页面，切换片段前必须结束或取消。
- 画面加载完成前类别按钮禁用，数字键和他人入镜标记也会等待；加载失败时暂停播放。
- 备注输入即保存。自动保存失败时停止继续修改，保留页面并检查终端，不要覆盖其他编辑器的修改。

## 5. 校验与交付

```powershell
python -m tools.validation.labels validate --dataset-root $dataset
# 试用文件：
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json"
```

严格校验要求每个 manifest 片段的所有步骤由合法类别区间恰好覆盖一次、无重叠，元数据与数据集一致。
`--allow-incomplete` 仅检查草稿结构，不能代表标注完成。校验只读取 JSON，不解码视频、不调用 FFmpeg。
`labels.expand_runs()` 可将区间展开为逐步数组；数组不另存为正式标注。

后续一致性复标与评估协议由协调者安排；不要根据模型结果修改标签或自行删除困难片段。
