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
python -m tools.validation.sample_segments --proxies-root "$data\proxies" --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset
python -m tools.validation.extract_frames --dataset-root $dataset --validate-only
```

正式区域必须有与当前文件 SHA-256 一致的完成标记，以及至少一个目标和恰好一个工作区。
工具通过 `roi_regions.completed_document()` 检查 version 2 完成标记，只从标记的 `export_root`
复制 `classes.json` 和 `roi_reference.png`，复制前核对二者 SHA-256。
省略 `--regions-path` 时使用 `default_classes.json`，数据集只供试用；显式给出未完成区域时直接报错。
正式区域和同步代理就绪后，把 `$dataset` 改为 `...\gazelle_validation\roi_r2`，抽样命令加
`--regions-path "$data\roi\roi_regions.json"` 重新生成；旧试用标注不会自动变成正式标注。

抽样只读取代理旁注、会话信息与哈希，不解码视频、不调用 FFmpeg。固定种子为 `20261015`，
各会话独立使用 `seed + int(session)`，等分四层，每层均匀随机取一个完整 60 秒片段；不足 45 分钟时取两层。
`--sessions` 默认只含 20260821 20260828 20260903 20260911 20260925 20261002 20261009；
其他会话打印提示后忽略。manifest 记录参与会话。自选会话列表仍需包含固定 pilot 所在会话。
若任一机位标记缺口的时间步合计超过 2 秒（同一步只计一次），在同层最多重抽 10 次，记录每次尝试；耗尽则失败，不降低标准。
另加入画面时钟 2026-09-07 22:20:00 的一分钟 pilot，置于列表最前，排除于正式评估。
正式片段与 pilot 重叠时在同层重抽，并在 attempts 中记录 `pilot_overlap`。
若任一机位的片段包含 `sync_uncertain`（切点两侧最近有效证据中心各外扩半个窗长，或时间缺口/重叠范围），也在同层重抽，
逐次记录 `sync_uncertain_steps`；沿用最多 10 次重抽，不放宽标准。固定 pilot 若相交则交协调者复核。
只有七会话同步验证全部通过后才备份、切换代理并重建数据集；正式标注等待独立同步验收。

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
后再关闭页面。终端 Ctrl+C 关闭服务，之后重新打开，会定位到首个未完成段的首个未看步；
全部看过时找首个 null 步，否则停在第 0 步。画面加载并显示后自动记录已看步并保存文件。
不同数据集或类别配置的标注不能混用，哈希不一致时拒绝续标。
标注 schema 为 version 3；旧 version 1、2 明确拒绝，需用新工具重新标注，没有自动迁移。
新数据集 manifest 记录 `annotation_schema_version: 3`。

审查或试用请用独立路径：

```powershell
python -m tools.validation.annotate_server --dataset-root $dataset --labels-path "$dataset\review_trial.json" --annotator reviewer
```

先完整试标 pilot，再开始其他片段。一个一分钟片段约需 6–7 分钟，26 段约三小时，可分多次。

## 3. 判断规则

标注作业者正在看什么。眼睛优先于头部，头部优先于手部；手部动作只作辅助。
看手或手中物体时，`hands_object` 优先于它所在的固定区域。
转头过程中，在新目标比旧目标更明确的第一步切换类别。证据不足选 `unknown`，不要猜。
第二个人入镜时另标 `other_people` 区间；若作业者正在看此人，注视类别为 `away`。

默认类别如下；正式区域可以改变目标名称、数量、颜色和数字键，以页面读取的 `classes.json` 为准。

| 键 | 类别 | 含义 |
| --- | --- | --- |
| 1 | `pick_right` | 右侧取货台 |
| 2 | `work_front` | 前方作业台上的工装、加工中的工件、使用中的工具 |
| 3 | `place_left` | 前方桌面左侧的成品放置区 |
| 4 | `hands_object` | 手部/手中物体，优先于所在固定区域 |
| 5 | `cell_other` | 工作区内其他工具、资料、屏幕或设备 |
| 6 | `away` | 工作区外：过道、他人、远处背景、天花板 |
| 7 | `absent` | 作业者不在工位 |
| 0 | `unknown` | 无法判断；这是一项有效标注 |

未标注在草稿内为 null，与主动选择 `unknown` 不同。斜线表示“尚未看过”，即使已有类别也保留。
`viewed_ranges` 记录实际完整显示过的步并合并区间，只增不减；跳过的步不会被记为已看。
正式四个目标时为 1–4 目标、5 手部/手中物体、6 `cell_other`、7 `away`、8 `absent`、0 `unknown`。
全部步已看过、有类别且注视点规则满足后，“本段完成”按钮才可用；点击才写入 `finished_at`。
随后修改类别、点、跳过标记或他人入镜区间会清除完成状态，需要再次确认。区域参考存在时可展开查看。
修改较长片段的类别后，确认完成前请回放检查，因为“已看”只表示显示过。
服务端只认此前已保存的已看范围、类别、点和跳过标记；同请求新增范围会保存，但不能用于本次完成判断。
播放和未播放时逐步、跳转产生的已看变化最多每秒保存一次；暂停正在进行的播放、换段、完成、隐藏和关闭前立即写入。
隐藏/关闭的 `keepalive` 不等待正在进行的保存，服务端仍检查 revision；类别、他人区间和备注立即保存。

## 4. 操作

- 每个目标区域、`hands_object` 或 `cell_other` 类别片段都需要至少一个注视点；拿不准可按 S 标为跳过。
  `away`、`absent`、`unknown` 不点。在右侧全局视图单击添加当前步的点，同一步再次点击替换。
  注视位置移动时可加额外点，同一类别片段内至少相隔 5 步（1 秒）。
- X 或“删除当前注视点”只删除当前步的点；S 切换“本片段跳过注视点”（`unsure`）。
  O 切换“本片段画面外”（`out_of_view`），仅用于 `hands_object` 和 `cell_other` 的目标在全局画面外时。
- 当前点高亮，同类别片段其他点淡色显示，时间轴标出点与缺点片段。改为不需要点的类别时自动清除点和标记并提示，
  撤销一并恢复。合并片段后若间隔冲突保留较早点；无效的旧起点标记也会清除并提示。

- 空格播放/暂停，可选 1× 或 0.5×；左右方向键或按钮移动 0.2 秒，另有 ±1 秒按钮。
- 注视目标改变时按数字键：从当前步开始标注，直到下一个已有变化点。也可点击类别按钮。
- 点击彩色时间轴、拖动滑块或点击变化点按钮定位。Delete 删除当前步的变化点；首步删除后恢复未标注。
- Ctrl+Z 或“撤销”恢复最近一次修改；撤销同样立即保存。刷新页面后撤销栈清空，已保存内容仍保留。
- “下一个未标注”只寻找尚未选择类别的位置；每段仍需看完全部步并点击“本段完成”，之后跳到下一未完成段。
- 在第二个人出现时点击“他人入镜开始”，最后可见的一步点击“结束（含当前步）”。相邻/重叠区间合并；
  点击已保存区间旁的 × 删除。尚未结束的起点只保留在当前页面，切换片段前必须结束或取消。
- 画面加载完成前类别按钮禁用，数字键和他人入镜标记也会等待；加载失败时暂停播放。
- 备注输入即保存。自动保存失败时停止继续修改，保留页面并检查终端，不要覆盖其他编辑器的修改。

## 5. 校验与交付

```powershell
python -m tools.validation.labels validate --dataset-root $dataset
# 试用文件：
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json"
# 只严格检查 pilot，其余段只检查结构；可重复给出 --segment：
python -m tools.validation.labels validate --dataset-root $dataset --labels-path "$dataset\review_trial.json" --segment 20260911_pilot
```

严格校验要求每个指定段有 `finished_at`、`viewed_ranges` 覆盖全部步、类别没有 null；
类别区间恰好覆盖一次、无重叠，相邻相同类别须合并，元数据与数据集一致。
`points` 为 `{step, x, y}` 列表，步号唯一且在段内，坐标是 1920×1080 全局代理帧的有限归一化值 [0, 1]；
`point_skips` 为 `{step, reason}` 列表，step 是类别片段起点，reason 只能为 `unsure` 或 `out_of_view`。
校验点的类别、5 步间隔、各必点片段的点或跳过覆盖，以及画面外标记的类别限制。不带 `--segment` 时检查全部段。
`--allow-incomplete` 仅检查草稿结构，不能代表标注完成。校验只读取 JSON，不解码视频、不调用 FFmpeg。
`labels.expand_runs()` 可将区间展开为逐步数组；数组不另存为正式标注。

后续一致性复标与评估协议由协调者安排；不要根据模型结果修改标签或自行删除困难片段。
