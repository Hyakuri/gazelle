# 用户操作说明（最短版）

两个 agent 都从 `docs/collab/STATE.md` 读取当前阶段与下一步，你不需要粘贴任何文件。
完整规则见 [COLLABORATION_PLAN_CN.md](COLLABORATION_PLAN_CN.md)。

## Codex

**新开一个 Codex 对话时，只说一次：**

```text
请采用 C:\Users\yun\OneDrive - 秋田大学\AsstProf\GPTs Prompts\主线程执行范式_v1_1\CURRENT_CHAT_PRESET.md 的 v1.1 范式，作用域为本对话。
工作目录是 C:\Users\yun\Documents\Claude_Code\hyakuri-gazelle，按 docs/collab/STATE.md 的指示执行。
```

之所以需要这一句，是因为 v1.1 范式规定只在明确采用的对话中生效，且不得写入自动加载的规则文件。
建议为本项目一直使用同一个 Codex 对话，以后每次只说：

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
| `user` | 看 STATE.md 的「给用户的说明」：做决策，或在独立目录验收 |

`writer` 不是 `none` 时，说明有一方正在写入，等它结束再找另一方。

## 在独立目录验收

当 STATE.md 写明阶段已验收时，在 `C:\Users\yun\Documents\GitHub\gazelle` 中执行：

```powershell
git fetch origin --prune
```

```powershell
git switch feature/stage2-correctness
```

```powershell
git pull --ff-only
```

然后运行 STATE.md 写明的验收命令，把结果告诉 Claude。第一次切换前，若该目录有未提交的改动，先告诉 Claude，不要强行覆盖。
