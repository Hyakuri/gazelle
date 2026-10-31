# 目标机器验收证据（Gate A / B / C）— 2026-10-14 Asia/Tokyo

执行者：Claude（协调者）。宿主：Windows 10.0.19045，RTX 4080 SUPER 16 GB（driver 617.14），
解释器 `C:\Users\yun\anaconda3\envs\Gazelle\python.exe`（Python 3.11.15，torch 2.6.0+cu126），
FFmpeg `C:\Users\yun\ffmpeg\bin\ffmpeg.exe`（2025-03-31 gyan full build，含 h264_nvenc / libx264）。
所有 smoke 输出写在仓库外；仓库工作区在验收前后 `git status --short` 一致。
状态标签：以下全部为「已实际运行」，除非另注。

## Gate A 源码身份（已实际运行）

| 项目 | 结果 |
| --- | --- |
| zip SHA-256 | `54ac2309…31ac5bdf`，与交付的 `.sha256` 一致 |
| `Restore-Handoff.ps1 -VerifyOnly` | Verified 99 payload files |
| 恢复方式 | 脚本恢复到临时同级目录后整体移入 `C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle` |
| 分支 / HEAD | `feature/mediapipe-head-tracking` / `bbec05653c9c0d4dc8046aff26b9e159b51889d7`，与 `origin` 一致 |
| 工作区 overlay | 5 个 tracked 修改 + 7 个新文件，12 个文件 SHA-256 全部与 MANIFEST 一致 |
| PR #5 | OPEN，非 draft，MERGEABLE，base `feature/enhanced-gaze-rendering`，head 与本地 HEAD 一致（`gh pr view` 只读） |
| 模型缓存 | 从旧 checkout 复制 212 文件 / 1,619,401,663 B，逐文件 SHA-256 一致；清单 `C:\Users\yun\Documents\Claude_Code\_handoff_archive\models-cache-transfer-20261014.json` |

## Gate B 离线验收（已实际运行）

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'gazelle-claude-gateB-pycache'
python -m pip check                       # No broken requirements found. exit 0
python -m compileall main.py gazelle tests # exit 0
python -m unittest discover -s tests -v    # Ran 531 tests in 3.078s  OK  (0 fail, 0 error, 0 skip)  exit 0
python main.py --help                      # exit 0
python main.py --list-models               # 4 models listed  exit 0
git diff --check                           # exit 0（有 LF→CRLF 提示，见备注）
git status --short                         # 与 Gate A 一致
```

备注：overlay 文件为 LF，checkout 其余文件为 CRLF（系统级 autocrlf），内容级 diff 正常
（AGENTS.md +158/−70，其余四个文档各 +2）。

## Gate C 真实 smoke（已实际运行；CUDA、MediaPipe、FFmpeg 均真实执行；无网络下载）

测试媒体：`assets/the_office.png`（仓库自带，770×433）；`assets/Sunny_1.gif` 经本机 FFmpeg 转为
640×360 / 30 fps / 181 帧的 `sunny.mp4`。全部资源来自 `models/` 缓存，日志出现
`Using cache found in models\torch_hub\facebookresearch_dinov2_main`，无 `Downloading`。

| 运行 | 命令要点 | 结果 |
| --- | --- | --- |
| prepare-only | `--prepare-only --head-source mediapipe --pose-model full --model gazelle_dinov2_vitb14_inout --cache-dir models` | exit 0，25 s；`strict_load=yes`，checkpoint sha256 `451f76e5…2ac00e`；MediaPipe 三资产就绪 |
| image 保守 | the_office.png，mediapipe，max-heads 3，`eligible` / `valid-only`，CUDA | exit 0，7 s；检出 2 头，均 `rejected_low_quality`；**0 预测** |
| image 诊断 | 同上 + `--gazelle-head-mode all --gaze-render-mode all-predictions --save-face-landmarks` | exit 0；2 预测均 valid（inout 0.85 / 0.95）；两头 `face_landmarks=0`、无 `facial_transformation_matrix` |
| image 静态 | `--head-source static` + 三个已知人脸 bbox | exit 0；3 预测均 valid（inout 0.83 / 0.74 / 0.85），峰值与上游 README 示例一致 |
| video A 保守 | sunny.mp4，max-heads 1，30 帧，`avc1`，双参考射线 | exit 0，22 s；head/pred 各 30 行，索引连续、时间戳一致且严格递增；pred 状态 ok 14 / no_gaze 15 / no_head 1；预测 valid 3 / out_of_frame 11；推理首帧 645 ms，稳态 ≈23 ms；rendered.mp4 h264 yuv420p 30 帧 |
| video B 诊断 | max-heads 2，`all` / `all-predictions`，`mp4v` | exit 0，24 s；各 30 行一致；ok 29 / no_head 1；57 个感知全部 selected；预测 valid 36 / out_of_frame 21；rendered.mp4 mpeg4 30 帧 |

### 观察（事实）与解释（推断）分开

- 事实：the_office.png 上 BlazeFace full-range 只检出 2 个候选，其中 id=1 的 face bbox 落在手部区域（conf 0.76），
  Pose 头部关键点也落在同一区域；Dwight 与中间人物的正脸未被检出。两个裁剪上的 Face Landmarker 返回空。
- 推断：保守门控在该图“全部拒绝”的直接原因是 `head_pose is None`（无 landmarker 结果 → 无 face ray →
  `_meets_face_gaze_quality` 失败）。这与交接文档开放问题 #1“保守门控可能抑制过多”一致，但根因在感知前端
  （检测器/landmarker 在该分辨率与裁剪上的失败），不是 Gazelle 本身。
- 事实：Sunny 视频上 landmarker 正常（有 `head_pose`、yaw ≈ 3.9°），保守模式产生真实预测。

产物副本：`C:\Users\yun\Documents\Claude_Code\_handoff_archive\smoke-20261014\`（含日志、JSONL、渲染图/视频、抽帧）。

## 未执行 / 限制

- 未做任何正式精度实验；smoke 不证明视线精度。
- 未运行 ViT-L 模型；未测试 `--frame-step`、`--output-fps` 失效源 FPS 路径、异常中断残留。
- Gate D（Codex 接手演练）待首个任务。
