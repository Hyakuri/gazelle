# 全局摄像机区域标记指南

预计约 10 分钟。只标记固定区域，不标记逐时刻视线，也不显示模型预测。
在现有 Gazelle-next 环境、仓库根目录运行；输入是 TASK-132 的清单与有效重封装视频。
所有候选帧、区域定义、备份、参考图和类别都留在仓库外的数据根，不提交或上传。

```powershell
conda activate Gazelle-next
$data = 'C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata'
python -m tools.validation.extract_roi_candidates --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\roi"
python -m tools.validation.roi_server --candidates "$data\roi\candidates.json" --annotator local
```

抽帧每次录制取 12 个等间隔区间的中点，写 1920×1080 JPEG（质量 90）与候选清单。
使用本地 OpenCV、Pillow 和 CPU，不调用 FFmpeg 可执行程序、不运行模型、不使用 GPU、
不联网或下载。每次抽取使用新文件名，避免覆盖旧参考画面；续标请保留原候选清单。
服务只监听 `127.0.0.1`，默认端口 8765；页面资源均来自本机，不引用外部服务。
打开终端显示的本机地址。结束时回到终端按 Ctrl+C。

1. 选择桌面边界清楚、遮挡少的主参考帧。选择后会自动保存。
2. 选择区域类型，点“开始画区域”。单击加顶点；回车或双击闭合。
3. 依次画三个目标区域与一个工作区边界：
   - **取货台 / pick_right**：右侧桌面的取物范围。
   - **作业台 / work_front**：前方桌面上实际加工的范围，包括治具与工件。
   - **放置区 / place_left**：前方桌面左侧放置成品的范围。
   - **工作区 / work_cell**：包含两张桌面与作业者站立位置的整体边界。
4. 点击区域选中，拖动圆点调整顶点。重叠处选中最小区域，所选顶点始终显示在所有区域上方。
   选中顶点后可删除，至少保留三个；也可删除整个区域。
   撤销按钮或 Ctrl+Z 返回前一步；Esc 取消未闭合草稿。自定义区域填写中文名和 ASCII 英文键。
5. 查看跨日期核对图，确认各次录制中桌面与区域仍对齐。若机位移动，记录问题交给 Claude，
   不通过扭曲区域掩盖差异。切换主参考帧会保留归一化多边形，仍可撤销。
6. 顶部显示“草稿已自动保存”后，点“导出参考图与类别”。导出要求 1–6 个目标区域、
   恰好一个工作区，且没有未闭合草稿。输出为 `roi_regions.json`、`roi_reference.png`、
   `overlays/<session>.png`、`classes.json`；成功后另写 `roi_regions.complete.json` 完成标记。

自动保存使用原子替换，上一版为 `.json.bak`。未闭合草稿单独保存在 `.draft.json`，
重启同一命令后恢复。保存失败或自相交时顶部显示“未保存”，请修改或撤销，不要直接关闭。
区域文件只在用户开始操作后创建；仅打开页面不会生成区域。自动保存的文件仍是草稿，
只有成功导出后的完成标记才表示完成。标记包含版本、完成时间与区域文件 SHA-256；
后续修改或开始新草稿使完成状态失效，需重新导出。下游使用 `roi_regions.completed_document()`
检查完成状态。重复保存相同内容不轮换备份。

审查或试用请加 `--regions-path "$data\roi\review_trial.json" --annotator reviewer`。
该文件的草稿与备份同名派生，导出放到 `review_trial_export`，不覆盖正式区域和参考图。

也可单独校验和导出：

```powershell
python -m tools.validation.roi_regions validate "$data\roi\roi_regions.json"
python -m tools.validation.roi_regions classes "$data\roi\roi_regions.json" --out "$data\roi\classes.json"
python -m tools.validation.render_roi_reference --regions-path "$data\roi\roi_regions.json" --candidates "$data\roi\candidates.json" --out-root "$data\roi"
```

渲染使用本机已有中文字体；Windows 默认查找微软雅黑。其他环境可用 `--font` 指定已有 CJK 字体，
工具不安装字体。区域文件版本 1，摄像机固定为 cam_e；polygon 为 0–1 归一化坐标，
key 唯一、cell 至多一个，多边形不能自相交。目标颜色互不重复，也不与固定类别重复；
自定义目标自动从独立色板取色。类别按 target 绘制顺序分配数字键，之后为
cell_other、away、absent，最多占用 1–9；unknown 固定为 0。删除后重画会改变类别顺序。
`classes.json` 为 `{version: 1, classes: [{key: 数字, label: 英文标签, name_zh: 中文名, color: 颜色}]}`。
正式标记体验与区域边界仍需用户确认，工具检查不代表科研标签已经验收。
