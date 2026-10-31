# 多视角注视区域标注指南

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
其他会话打印提示后忽略。manifest 记录参与会话；不加 `--no-pilot` 时，自选会话列表须包含固定 pilot 所在会话。
若任一机位标记缺口的时间步合计超过 2 秒（同一步只计一次），在同层最多重抽 10 次，记录每次尝试；耗尽则失败，不降低标准。
另加入画面时钟 2026-09-07 22:20:00 的一分钟 pilot，置于列表最前，排除于正式评估。
正式片段与 pilot 重叠时在同层重抽，并在 attempts 中记录 `pilot_overlap`。
若任一机位的片段包含 `sync_uncertain`（切点两侧最近有效证据中心各外扩半个窗长，或时间缺口/重叠范围），也在同层重抽，
逐次记录 `sync_uncertain_steps`；沿用最多 10 次重抽，不放宽标准。固定 pilot 若相交则交协调者复核。
新增录制保留旧七次产物与数据集。只有已批准的替换批次同步验证全部通过后才备份、切换代理并重建数据集；正式标注等待独立同步验收。

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
隐藏时按正常队列保存，等待正在进行的保存；只有关闭时的 `keepalive` 直接发送，服务端仍检查 revision。
关闭或网络中断不保证请求送达，关闭前应等到已保存。类别、他人区间和备注立即保存。

## 4. 操作

注视落在某区域内的桌面或物体上时用该区域。默认点在片段的第一步，否则选目标最清楚的一步。
同一片段的点与跳过标记互斥；画面外代替点，只用于整个片段的目标都在全局画面外。
部分可见时只点可见部分，不标画面外；拿不准时整段跳过。S/O 删除本片段全部点并提示个数，撤销一并恢复；
加点前先取消标记。合并片段时保留点、清除冲突标记并提示，可撤销。
键盘撤销只用 Ctrl/Cmd+Z，且不带 Shift 或 Alt；工具没有重做。其他 Ctrl/Meta/Alt 组合键保留浏览器行为，
不作标注快捷键。按住 S/O/X/Delete/数字/空格或 Ctrl/Cmd+Z 只执行一次，并阻止重复事件的浏览器默认动作；
方向键可以重复。慢帧加载就绪后停留满一个步长再前进。`hands_object` 使用亮黄绿色 `#b6ff00`。
用鼠标操作过滑块或下拉框后，可以直接使用快捷键；鼠标点击按钮后也会释放焦点。
Tab 等键盘操作保留控件焦点，备注文本框始终保留输入焦点。
编辑器和标签校验在打开标签前要求 manifest `annotation_schema_version: 3`；
旧数据集须重新生成，或按 TASK-125 第 5 条更新类别与 manifest。

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
- Ctrl/Cmd+Z 或“撤销”恢复最近一次修改；撤销同样立即保存。刷新页面后撤销栈清空，已保存内容仍保留。
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
校验点的类别、5 步间隔、各必点片段的点或跳过覆盖，以及画面外标记的类别限制；同一类别片段内注视点与标记互斥。
不带 `--segment` 时检查全部段。
`--allow-incomplete` 仅检查草稿结构，不能代表标注完成。校验只读取 JSON，不解码视频、不调用 FFmpeg。
`labels.expand_runs()` 可将区间展开为逐步数组；数组不另存为正式标注。

后续一致性复标与评估协议由协调者安排；不要根据模型结果修改标签或自行删除困难片段。

## 同步复核与迁移保护

`sync_calibrate` 与 `sync_validate` 提供默认关闭的 `--second-look`，仅用于
20261016 起的录制。同一信号采用 120 秒窗口、60 秒步长复核，不改变拟合系数和原门槛证据。
A/E 拟合仅在 `residual_tail_exceeds_0_2` 时复核；A–B/E–B 仅在
`fraction_within_0_2 < 0.9` 时复核。四项条件为占比 ≥0.9、中位绝对残差 ≤0.1 秒、
中点偏差绝对值 ≤0.1 秒、漂移绝对值 ≤0.1 秒/小时。A–E 原判定为失败时复核，
中位绝对残差与中点偏差绝对值均 ≤0.15 秒、漂移绝对值 ≤0.15 秒/小时，不设占比条件。
每项复核至少 10 个有效窗、覆盖率至少 30%；W–B 不复核，也不影响录制等级。
原 A–E 的 `insufficient_evidence` 仍可放行。验证文件的 `sync_grade` 为：原门槛通过
`official`，用过任一获准复核为 `second_look`，同步失败为 null。新索引必须有成功等级，
旧七次缺字段视为 `official`。`valid_second_look` 映射必须带 `--second-look` 验证，
不会自动重跑已有录制。已通过审查的 20261016 验证文件保持原样，仅补索引等级。
复核使用 CPU，映射与验证写到仓库外，不运行模型、CUDA、网络或下载；代理验证会解码
媒体并读取精确来源帧。W 异常记录 `error_type`，抽样另存 `webcam_error_type` 与原因。
正式 `approved` 作业者文件必须含全部文件头，`span_id` 为 `<录制>_worker_<n>`。

`sync_calibrate`、`proxies`、`sync_validate` 可传 `--inventory <inventory.json>`，在内存中
解析失效的源路径，核对 SHA 记录、大小和清单 `mtime_ns` / 映射 `media_mtime_ns` / 磁盘修改时间。
`needs_remux=true` 的失效路径拒绝解析，原始文件保持只读。细化切点限于
`adjacent_window_centers` 闭区间，无候选保留粗切点并记 `refined=false`。
W 不可用原因保存在 `webcam_unavailable`，不阻塞 A/B/E。拒绝 `review-only` 作业者表；
文件头包括 `clock`、`rule`、`precision_seconds`、`handover_face_grace_seconds`、`status`、
`source_draft_sha256`，格式定义在 `tools/workdata/workers.py`。代理保留 `allow_internal_gaps`。
W 文件名共用 `camera_roles.json`。新录制验证写到 `sync_validation_r5`，旧七次产物不变。
