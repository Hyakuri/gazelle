# 用户操作说明（最短版）

两个 agent 都从 `docs/collab/STATE.md` 读取当前阶段与下一步，你不需要粘贴任何文件。
进展与每个任务的报告汇总在 GitHub 上阶段分支的 draft PR 页面，编号见 STATE.md 控制块的 `pr`。
完整规则见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md)。

## Codex

### 一次性设置：让 Codex 在新目录中工作

旧目录 `C:\Users\yun\Documents\Codex\2026-06-25\hyakuri-gazelle` 的 Codex 会话只能写旧目录，不能继续用于本项目。

1. 在 Codex 中新开一个会话，工作区选择 `C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle`。询问是否信任该目录时，选择信任。
2. 打开 `C:\Users\yun\.codex\config.toml`。该文件目前有 `sandbox_mode = "workspace-write"`，但没有 `[sandbox_workspace_write]` 段。在文件末尾加上下面一段，保存后重启 Codex：

   ```toml
   [sandbox_workspace_write]
   writable_roots = [
     'C:\Users\yun\Documents\Claude_Code\gazelle_data',
     'C:\Users\yun\Documents\Claude_Code\gazelle_runs',
     'C:\Users\yun\Documents\Claude_Code\gazelle_validation',
   ]
   network_access = true
   ```

   - 三个目录已经建好，用来存放派生数据、运行输出与标注，都在仓库之外。
   - `network_access = true` 让 `git push` 与 `gh` 不必逐次批准。若你更希望每次推送都由你批准，可以删掉这一行，Codex 推送时会请求批准。
3. 在新会话里先说一次采用范式的话（见下一节），再说“继续”。Codex 会先做环境预检；如果还缺权限，它会列出缺哪一项，不会自行修改设置。

### 每个新会话说一次

```text
请采用 C:\Users\yun\OneDrive - 秋田大学\AsstProf\GPTs Prompts\主线程执行范式_v1_1\CURRENT_CHAT_PRESET.md 的 v1.1 范式，作用域为本对话。
工作目录是 C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle，按 docs/collab/STATE.md 的指示执行。
```

之所以需要这一句，是因为 v1.1 范式规定只在明确采用的对话中生效，且不得写入自动加载的规则文件。
建议为本项目一直使用同一个 Codex 会话，以后每次只说：

```text
继续
```

## Claude

在本项目的 Claude 会话里说：

```text
继续
```

## 怎么知道该找谁

打开 `docs/collab/STATE.md`，看控制块的 `next_actor`：

| `next_actor` | 你要做的事 |
| --- | --- |
| `codex` | 对 Codex 说“继续” |
| `claude` | 对 Claude 说“继续” |
| `user` | 看 STATE.md 的「给用户的说明」：做决策、画区域、标注，或在独立目录验收 |

`writer` 不是 `none` 时，说明有一方正在写入，等它结束再找另一方。

## 在独立目录验收

验收的对象是 STATE.md 控制块中的 `last_accepted` 提交，而不是分支的最新提交。在 `C:\Users\yun\Documents\GitHub\gazelle` 中执行：

```powershell
git fetch origin --prune
```

```powershell
git switch --detach <last_accepted 的 SHA>
```

```powershell
git rev-parse HEAD
```

确认输出与 `last_accepted` 一致后，运行 STATE.md 写明的验收命令，把结果告诉 Claude。验收结束后可以用 `git switch feature/stage2-correctness` 回到分支。第一次切换前，若该目录有未提交的改动，先告诉 Claude，不要强行覆盖。
