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

- 接手核对：
- 提交与推送（SHA）：
- 变更文件：
- 命令、退出码、测试数、warnings 与 skips：
- 证据类型：
- 真实 smoke 结果：
- 外部活动：
- 反证式复核（v1.1 §9）：
- 未运行的检查、限制、阻塞：
- 状态标签（v1.1 §12）：

## 3. 审查结论（Claude 追加）

- 审查目标（SHA 范围）：
- 独立复跑结果：
- 发现：
- 结论：

## 4. 验收记录（用户反馈后由 Claude 填写）

- 用户验收环境与结果：
