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
python -m tools.workdata.timemap --inventory "$data\inventory\inventory.json" --remux-root "$data\remux" --out-root "$data\timemaps_v2_base"
python -m tools.workdata.sync_calibrate --timemaps "$data\timemaps_v2_base" --out-root "$data\timemaps_v2" --samples-root "$data\sync_samples_v2" --session 20260828
python -m tools.workdata.sync_check --timemaps "$data\timemaps_v2" --out-root "$data\sync_checks" --session 20260828
```

时钟图片入口只读本地完整视频帧（不能只传裁下的时钟），输出识别结果或 null。视频入口使用 PyAV/FFmpeg 库进行 CPU
解码，不启动 FFmpeg 可执行程序、不使用 GPU 或模型、不联网。它们自动设置低于正常优先级，
支持 `--session 20260828`。原始 MP4 直接读取，AVI 必须有已验证的重封装结果。

版式配置按 3840×2160 缩放，数字模板只含 0–9 点阵。E 支持明暗两种字形极性并核对星期。
缩小的代理帧另使用适应压缩后对比度的二值化候选；模板误差上限与候选差距要求保持相同。
当前字母样本支持 Mon/Tue/Wed/Sat/Sun；未覆盖的星期返回缺失，不猜测。
识别不可靠时不造读数。全文件顺序解码，同时每约 10 秒在 2.25 秒短窗口内读取时钟，
以秒位增加后的第一帧为锚点，记录原生 PTS 与帧号，另存普通识别读数。
文件身份必须由版式独立确认并与清单一致。

v2 每个文件用 Theil–Sen 初值及降权最小二乘稳健拟合 `wall = a + b × pts`。
所有锚点的残差分布、离群锚点与漂移 ppm 均记录；要求绝对残差中位数 ≤0.5 s、≥90% 在 ±1.5 s 内。
只在相邻实际解码 PTS 回退或间隔超过 1 s 时分段，不按显示时钟残差切段。
分段使用实际帧端点和帧号；重复 PTS 必须带帧号以消除歧义。覆盖从实际首帧开始。
这里的 epoch 秒数只是画面本地时钟的数值编码，不表示已经校准的 UTC。
锚点缓存绑定源清单 SHA、媒体大小/修改时间、实现版本与采样参数；`--force` 才强制重采样。

同步 r2 以前方 B 为基准：5 Hz 最近帧采样保存 96×54 灰度缩略图与来源，
6×12 格帧差均值取 log1p，缺口保留缺失。B 用整帧信号，A/E 选与 B 在任意滞后下相关最高的六格。
60 s 窗、60 s 步长、±10 s 搜索，`corr(B[t], X[t+L])` 的正 L 表示 X 同一事件晚出现。
抛物线插值给出亚步滞后；有效窗 r ≥0.5、突出度 ≥0.1 且不在搜索边界。
Theil–Sen 拟合偏移和漂移，要求 ≥10 窗、跨度 ≥30%、MAD ≤0.08 s；最多三个台阶，
分割后 MAD 至少减半、两侧各 ≥5 窗，再用附近 20 s 窗/10 s 步长细化。
最终 `t = base_X(pts) - L(t)` 用两次不动点迭代，未在 1 ms 内收敛即失败。
无人或静止时段不能提供校准窗；不能校准时记录原因，不能生成 v2 代理。

旧 `sync_check` 仅作三个 120 s / 10 Hz 窗的诊断，保留相反的历史符号
`corr(camera[t + lag], E[t])`，单列边界峰、不突出峰等原因；有效峰且 |lag| ≤0.5 s 才通过。
它不替代 r2 验收。缓存键包含映射、采样及映射应用实现哈希。

## 5 Hz 代理视频

```powershell
python -m tools.workdata.proxies --timemaps "$data\timemaps_v2" --out-root "$data\proxies" --session 20260828 --allow-internal-gaps
python -m tools.workdata.sync_validate --proxies "$data\proxies" --out-root "$data\sync_validation" --session 20260828 --clock-samples C:\path\outside-repository\check_proxy_clocks.json
```

默认 `--step-hz 5 --size 1920 1080`，三个角色文件为 `proxy_front.mp4`（cam_b）、
`proxy_right.mp4`（cam_a）、`proxy_overview.mp4`（cam_e）。同会话具有相同 N；
每个网格时刻取最近源帧，超过半步长的时间差记为缺口。网格是 B 的画面时钟轴；仍需残差和人工事件验收。

使用 CPU PyAV 顺序解码、FFmpeg libx264/CRF20/yuv420p/CFR 编码，不含音频；
进程低于正常优先级，无模型、GPU、网络或下载。逐帧旁注记录 k、时钟、源文件、PTS、
时间差与缺口。所有源文件完整解码到 EOF，记录 OpenCV 容器计数与实际解码计数，
相差超过 0.5% 或计数不可用时标为需复核。临时输出经 ffprobe 完整帧数、格式、时长检查后
原子替换，并绑定 SHA-256。`session.json` 记录网格、角色、映射与实现哈希、真实代码提交及工作树状态。

已有匹配输出经哈希、旁注与完整解码验证后跳过；`--force` 强制重建。参数或实现变化会使旧指纹失效，
旧输出会保留并报错，只有显式 `--force` 才替换；校验失败或视频/旁注不成对时同样处理。
可用 `--ffmpeg`、`--ffprobe` 指定已有程序；不安装任何依赖。

共同覆盖有内部缺口时默认报错。r2 流程显式加 `--allow-internal-gaps`：
保留总体起止的固定网格，记录 `coverage_gaps` 与 `gap_policy=nearest_with_gap_flag_provisional`，
沿用最近帧规则，不丢弃区间或拼接压缩时间。重新生成前将旧代理和试用集改名为日期备份，保留到验收。

`sync_validate` 在新代理上测 A–B/E–B/A–E：有效窗 ≥90% 的 |L| ≤0.2 s，中位 |L| ≤0.1 s，
会话中点 |c0| ≤0.1 s、|c1| ≤0.1 s/小时。时钟抽查复用 TASK-134 已保存的固定 k，
缺读依次试 k−1/k+1/k−2/k+2；仍缺失记不可评估，可评估比例须 ≥90%，A/B ±1 s、E ±2 s。
报告保留失败与各类非测量窗，不能靠删窗口通过。每会话自动选三个联合运动起点，导出 ±1 s、
逐 0.2 s 的 B/A/E 条图供人工复核。输出仅在数据根，不上传人物图像。
校准代理存在后重建 `roi_r2_trial`，正式 ROI 已完成则同时生成 `roi_r2`；正式标注等待独立同步验收。
