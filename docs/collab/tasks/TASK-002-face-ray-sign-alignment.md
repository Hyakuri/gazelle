# TASK-002：面部参考射线与 roll 符号对齐已批准规范

状态：ready
创建：2026-10-15（Asia/Tokyo）　协调者：Claude　实现者：Codex　验收：用户（独立 checkout）
问题来源：GZ-02（登记表 C001，主线程复现），见 [分析报告 §5](../analysis/2026-10-14-codebase-analysis.md)。
依据：已批准规范 `docs/superpowers/specs/2026-07-21-mediapipe-head-perception-design.md` §14。AGENTS.md 的来源优先级中，已批准规范高于现有代码，因此本任务修正代码，不修改规范。

## 1. 契约

### 目标

序列化的头姿角与面部参考射线都符合规范 §14 的显示坐标约定：正 yaw 转向图像右侧，正 pitch 转向图像下方，正 roll 在图像中顺时针。面部射线方向等于人脸前向向量在图像平面上的投影。

### 背景与推导

MediaPipe 的 facial transformation matrix 位于 Y 向上、Z 朝向摄像机的右手 metric 空间。设分解为 `R = Rz(r)·Ry(ψ)·Rx(θ)`，人脸前向向量是第三列 `(r02, r12, r22)`。在显示图像（x 向右、y 向下）中的正确投影方向是 `(r02, -r12)`。

- 当前 `_matrix_to_head_pose` 输出的 yaw 与 pitch 符号已符合规范；roll 输出的是 metric 空间角 `r`，正值在显示图像中为逆时针，与规范相反。
- 当前 `estimate_face_pose_reference_ray` 用 `vertical = -sin(pitch)`，等价于把 `(r02, r12)` 直接当图像方向，垂直分量反了。
- 修正后：序列化 roll 取 `ρ = -r`；射线取 `h = sin ψ·cos θ`、`v = sin θ`，再按 `ρ` 在 y 向下坐标中旋转：`(cos ρ·h − sin ρ·v, sin ρ·h + cos ρ·v)`。这与 `(r02, -r12)` 逐项相等。

### 必须实现

1. `gazelle/runtime/perception/mediapipe_backend.py` 的 `_matrix_to_head_pose`：序列化 roll 取 metric roll 的相反数，含奇异分支。yaw、pitch 不变。
2. `gazelle/runtime/perception/reference_rays.py` 的 `estimate_face_pose_reference_ray`：垂直分量改为 `+sin(pitch)`，旋转公式保持不变（它在新 roll 定义下正好是显示坐标中的顺时针旋转）。
3. 在两个函数旁用一两行注释说明坐标约定与依据的规范章节。
4. 测试：
   - 性质测试：对若干固定旋转矩阵（含 yaw、pitch、roll 均非零的组合），`_matrix_to_head_pose` 的结果送入射线函数后，方向与 `(r02, -r12)` 归一化后一致（容差 1e-6）。
   - 符号测试：pitch = +30° 时方向 y > 0；pitch = −30° 时 y < 0；yaw = +30° 时 x > 0；yaw = +30° 且 roll = +90° 时方向约为 (0, 1)。
   - 更新 `tests/test_mediapipe_backend.py` 中固定欧拉角符号的用例，使 roll 符号符合规范。
   - 同一头姿下，面部射线与姿态射线的垂直方向符号一致（姿态射线用鼻点低于双眼中点的构造）。
5. 四份用户文档在 `head_pose` 与参考射线说明处写明符号约定；`tests/test_usage_docs.py` 锁定该说明的 token。

### 非目标

- 不改 yaw、pitch 的序列化符号；不改姿态射线；不改射线置信度、AXIAL 判定、长度与裁剪规则。
- 不改 eligibility 或任何门控。
- 不改 JSON 字段名与结构。

### 依据材料

- 代码：`gazelle/runtime/perception/mediapipe_backend.py:222-260`、`gazelle/runtime/perception/reference_rays.py:91-182`、`gazelle/runtime/perception/fusion.py:116-123`（只用 |yaw|，不受影响）。
- 测试：`tests/test_reference_rays.py`、`tests/test_mediapipe_backend.py:406-431`、`tests/test_head_fusion.py:139-195`、`tests/test_usage_docs.py`。
- 文档：`docs/USAGE.md` 第 12 节 `head_pose` 行（约 `:343`）及中文同行、README 相应段落。

### 不可变约束

AGENTS.md 全部不变量；射线仍是未标定的 2D 参考，不是视线测量；默认测试隔离规则。

### 允许动作

修改上述代码、测试与四份文档；按协作方案 §4 提交并推送；运行离线验证与下方真实 smoke（仅缓存资源，输出写到仓库外）。可只读使用作业数据补充真实 smoke：TASK-131 合入后，用 FFmpeg 流复制从 MP4 分段或 TASK-134 的代理视频截取 15 秒片段到 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\` 再运行，不写入 `E:\Gazelle_Workdata\`。sample1 只作冒烟输入；sample2 不属于目标场景，不再使用。运行任何 GPU 推理前按协作方案 §5 检查空闲显存。

### 禁止

新建分支或 PR、合并、force push；修改环境；下载；修改其他文件；写入或修改用户独立目录或 `E:\Gazelle_Workdata\` 中的任何文件。

### 验收标准

1. 上述性质测试与符号测试全部通过；旧用例按规范更新后通过。
2. 完整离线门通过，无失败，无新增 skip。
3. 真实 smoke，使用 `assets/Sunny_1.gif`：
   - 第 15 帧男孩看向左下方的女孩，面部射线方向 x < 0 且 y > 0。
   - 取一个近正脸帧（例如第 22 帧），用 PIL 顺时针旋转 20°（`Image.rotate(-20, expand=False)`）和逆时针旋转 20°，分别以图像模式运行。`head_pose.roll_deg` 分别约为 +20° 与 −20°（容差 ±8°），射线方向随之顺时针或逆时针偏转。
   - 在实施报告中列出命令、数值与截图路径（截图放在仓库外）。
4. 四份文档写明符号约定。

### 验证命令

```powershell
$py = "C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "gazelle-task-002-pycache"
& $py -m unittest tests.test_reference_rays tests.test_mediapipe_backend tests.test_head_fusion tests.test_usage_docs -v
& $py -m compileall main.py gazelle tests
& $py -m unittest discover -s tests -v
& $py main.py --help
& $py main.py --list-models
git diff --check
git status --short
```

### 其他

- 需独立审查：是（坐标约定变化）。
- 需真实 smoke：是。
- 文档同步：需要。
- 风险与回退：已消费旧 `face_pose_reference_ray` 方向或 `roll_deg` 的下游需知悉符号变化。回退方式是 `git revert` 本任务的提交。
- 依赖：无。可在 TASK-102 之后执行；作业数据补充 smoke 需要 TASK-131 已合入。

## 2. 实施报告（Codex 追加，不要修改上文）

### 2026-10-17 实施与验证

- 接续 TASK-102；TASK-139 CPU 扫描仍在后台运行，主线程 Inline Execution，没有子代理。STATE 的 writer/next_actor 均为 codex。
- 实现提交 `b24dd67` — `Align face reference rays with display coordinate signs`。两处计算、两组单测、usage 文档测试与四份用户文档，共 9 文件。roll 取反，vertical 改为 `+sin(pitch)`；yaw、pitch、pose ray、门控、置信度与裁剪规则不变。
- 组合旋转与 ±90° 奇异分支的性质测试直接比较矩阵第三列的 `(r02,-r12)`；补充四个符号和两类射线同向检查。文档标出 `yaw_right`、`pitch_down`、`roll_clockwise` 及旧结果的兼容性变化。

#### 命令与结果

解释器 `C:\Users\yun\anaconda3\envs\Gazelle-next\python.exe`；字节码 `%TEMP%\gazelle-task-002-pycache`；所有证据在 `C:\Users\yun\Documents\Claude_Code\gazelle_runs\task-002\`。

| 命令/检查 | 结果 |
| --- | --- |
| 新 reference ray 测试在修改前运行 | exit 1，11 tests，8 failures（含组合矩阵 subtests），复现垂直/roll 符号问题 |
| `python -m unittest tests.test_reference_rays tests.test_mediapipe_backend tests.test_head_fusion tests.test_usage_docs -v` | exit 0，49 tests / 0.037s / 0 skip |
| `python -m compileall main.py gazelle tests` | exit 0 |
| `python -m unittest discover -s tests -v` | exit 0，637 tests / 17.562s / 0 skip；包含当前 TASK-139 实现与 refit 修复 |
| `python main.py --help`、`python main.py --list-models`、`git diff --check` | 全部通过 |
| `python ...\task-002\smoke.py`、`python ...\task-002\extra_smoke.py`，另一次未旋转 frame22 图像运行 | 均 exit 0；累计 1 次 30 帧视频、7 次图像运行 |

非致命日志包括坏 MP4 单测的 `moov atom not found`、xFormers 不可用和 MediaPipe 日志初始化提示。无新增 skip；进程 exit 0 不代表下列真实验收条件全部通过。

#### 真实 smoke：通过项与未满足项

公共参数：`python ...\task-136\smoke.py cli <repo> --input <input> --output-dir <external> --cache-dir <repo>\models --device cuda --head-source mediapipe --max-heads 2 --save-rendered --face-pose-ray --pose-head-ray --head-box --face-box --gazelle-head-mode all --gaze-render-mode all-predictions`。视频另加 `--max-frames 30 --video-codec mp4v`。完整 argv 和退出码在 `commands.json`、`extra-commands.json`；单独未旋转 frame22 使用相同公共参数，输入 `frame22.png`，输出 `frame22-output`，日志 `frame22.log`。

先复用 TASK-102 从 Sunny_1.gif 转出的 `sunny.mp4`。30/30 prediction 行除 inference_ms 外与 TASK-102 B-after 完全相同，未改变 Gazelle 结果。视频帧 15 的男孩 `head_pose=null`、`face_pose_reference_ray=null`，同帧女孩也无 face ray；不能确认要求的 x<0、y>0。保留截图 `video-frame15-rendered.png`。帧 16 男孩方向为 `(-0.875627, +0.482988)`，仅作相邻帧补充证据，**不替代帧 15 的验收**。

从该视频提取近正脸帧 22，以 PIL `rotate(-20, expand=False)` / `rotate(20, expand=False)` 分别旋转，结果如下。方向角为显示坐标 atan2(y,x)，增加表示顺时针。

| 输入 | roll_deg | ray (x,y) | 方向角 |
| --- | ---: | --- | ---: |
| 未旋转 | -5.573736 | (0.967677, 0.252194) | 14.607353° |
| 顺时针 20° | +14.550630 | (0.848284, 0.529542) | 31.974518° |
| 逆时针 20° | -26.660848 | (0.992832, 0.119518) | 6.864307° |

两张旋转图的 roll 均在目标 ±20° 的 ±8° 容差内，射线方向相对未旋转图分别向顺/逆时针变化。结果 `rotation-angle-check.json`；已目视检查 `clockwise\clockwise_gazelle\rendered.png` 与 `counterclockwise\counterclockwise_gazelle\rendered.png`。

为排除转码与帧编号差异，再用 PIL 直接提取原始 GIF 的零基帧 15、22：帧 15 仍无 head-pose；帧 22 未旋转时可得到 roll=-5.220733°，但其顺时针图只检出女孩、逆时针图未检出人物。因此**原始 GIF 旋转组未满足验收**，没有降低检测阈值或换环境重试。详见 `extra-comparison.json` 与 `gif-*-output` 下渲染结果。

#### 复核、活动与待审查

- 反证式复核：修改前性质测试确实失败；包括非零复合旋转与奇异分支；真实视频 prediction 数据不变；未把原图自带的绿色视线标注误认为本实现 face ray。
- 真实 CUDA 推理与 MediaPipe CPU 执行；每次启动前检查显存/利用率。复用缓存，Python audit 阻断 Torch Hub 请求后缓存回退，无下载、安装或 Conda 修改。原生 MediaPipe 遥测不受 Python audit 覆盖。原始 3 次与补充 4 次运行的缓存 size/mtime 差异均为空；最后 frame22 使用同一缓存。视频读写使用 OpenCV，旋转使用 PIL；本任务没有另外调用 FFmpeg 可执行文件，转码素材沿用 TASK-102。
- A 级：保留相同编码视频进行前后 prediction 比较，并增加原始 GIF 直接提取检查以识别输入差异；所有失败原样保留。
- 范围外改动：无。四份用户文档同步，既有 schema 字段名不变。
- B 级（Q-011）：Gazelle-next 下帧 15 没有可用 face head-pose，原始 GIF 旋转图也漏检；历史 2026-10-14 Gazelle 结果不能当作本次证据。推荐 Claude 在稳定版本/同一素材上独立复跑，决定是否修订真实样例；当前保留原验收标准，未暂定替换帧或放宽标准。视频转码旋转组通过、原始图组未通过，必须分别审查。
- C 级：无。未运行可选作业视频 smoke；独立审查与用户独立 checkout 验收未运行。

**已实施、已静态检查、已实际运行；真实验收部分未满足，待 Claude 判断与独立复核。**

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
