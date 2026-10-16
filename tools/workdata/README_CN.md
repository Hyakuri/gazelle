# 作业数据工具

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

## 画面时钟与同步检查

```powershell
python -m tools.workdata.osd_clock --image C:\path\outside-repository\clock.png
python -m tools.workdata.timemap --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\timemaps"
python -m tools.workdata.sync_check --timemaps "$data\timemaps" --out-root "$data\sync_checks"
```

时钟图片入口只读本地完整视频帧（不能只传裁下的时钟），输出识别结果或 null。视频入口使用 PyAV/FFmpeg 库进行 CPU
解码，不启动 FFmpeg 可执行程序、不使用 GPU 或模型、不联网。它们自动设置低于正常优先级，
支持 `--session 20260828`。原始 MP4 直接读取，AVI 必须有已验证的重封装结果。

版式配置按 3840×2160 缩放，数字模板只含 0–9 点阵。E 支持明暗两种字形极性并核对星期。
缩小的代理帧另使用适应压缩后对比度的二值化候选；模板误差上限与候选差距要求保持相同。
当前字母样本支持 Mon/Tue/Wed/Sat/Sun；未覆盖的星期返回缺失，不猜测。
识别不可靠时不造读数。每约 10 秒顺序读取一个 2.25 秒短窗口，以秒位增加后的第一帧为锚点，
记录原生 PTS，另存普通识别读数。文件身份必须由版式独立确认并与清单一致。

每个文件稳健拟合 `wall = a + b × pts`，记录内点残差中位数、p95、最大值、离群锚点与漂移 ppm；
相差超过 1 秒的残差簇触发分段。按时钟排序各分段并保留缺口，计算三机共同覆盖区间。
这里的 epoch 秒数只是画面本地时钟的数值编码，不表示已经校准的 UTC。
锚点缓存绑定源清单 SHA、媒体大小/修改时间、实现版本与采样参数；`--force` 才强制重采样。

同步检查在共同覆盖中均匀选择三个 120 秒窗口，使用 10 Hz、192×108 灰度帧差能量，
比较 A/E 与 B/E 的 ±10 秒互相关。符号定义为 `corr(camera[t + lag], E[t])`；
要求 `abs(lag) <= 0.5` 且 `r >= 0.3`。失败仍保存窗口、r、滞后与缺口数并非零退出，
交协调者复核；不会靠修改映射或阈值使检查通过。运动缓存绑定映射和检查实现的哈希。
