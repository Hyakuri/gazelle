# 作业数据清单与重封装

在已存在的 Gazelle-next 环境、仓库根目录运行。源目录只读，数据根必须在源目录和仓库之外。
工具只进行本地 CPU 与磁盘操作，不调用模型、不使用 CUDA、不联网、不下载或安装依赖。
长时间任务请以低优先级运行。

```powershell
conda activate Gazelle-next
$raw = 'E:\Gazelle_Workdata\秋田大学様解析用動画'
$data = 'C:\Users\yun\Documents\Claude_Code\gazelle_data\workdata'
python -m tools.workdata.inventory --root $raw --out "$data\inventory\inventory.json"
python -m tools.workdata.remux --inventory "$data\inventory\inventory.json" --out-root "$data\remux"
```

清单调用 ffprobe，记录文件指纹、视频流信息、音轨存在性和前 60 秒的小包比例。
SHA-256 仅在同一源根、相对路径、文件大小与修改时间匹配时复用；其余信息重新探测。
摄像机识别规则来自 [camera_roles.json](camera_roles.json)，20260903 的编号互换由配置纠正。
物理编号 cam_a 为右侧，cam_b 为前方，cam_e 为全局。

重封装调用 FFmpeg，只复制首个视频流，丢弃小于 64 字节的包，不包含音频、不重新编码。
输出保留会话目录，AVI 后缀改为 MP4。发布前检查包数、0.5% 时长容差、PTS 严格递增、
OpenCV 开头和中间各 30 帧；尾部从估计末尾前 60 帧定位，最多读 120 帧，必须以 EOF 结束且
连续成功不少于 30 帧，最后解码时间与最后包 PTS 相差不超过 `r_frame_rate` 的一个标称帧间隔。
报告包含 `last_pts`、实际窗口解码数、`tail_eof` 与时间差检查。源文件始终保留。
有效旧输出默认跳过；`--force` 重新生成，
但失败仍保留旧输出。只删除本次生成的临时文件。逐文件结果写入 `remux_report.json`，
存在失败时命令退出码为 1，不能据此声称该文件已可用。

两个入口支持 `--ffprobe <路径>`，重封装另支持 `--ffmpeg <路径>`。
清单 JSON、报告 JSON 和所有视频只保留在数据根，不提交到 Git 或上传。
