# superpowers 技能工作区

这个文件夹属于 superpowers 技能，例如 brainstorming、writing-plans。它们按自己的约定：
- 把规格写到 `specs/`；
- 把实施计划写到 `plans/`。

项目文档的权威版本不在这里，而在分类文件夹中：
- 设计在 `docs/design/`；
- 旧设计与实施计划在 `docs/design/history/`。

完整规则见[文档记录体系与版本规则](../rules/DOCS_SYSTEM_CN.md) §4。

- **这里的文件是什么**：项目文件的技能副本，由 `python -m tools.docs build` 自动同步。对照表在规则文件 §4。
- **技能改了这里的文件**：
  1. 运行 `python -m tools.docs adopt --mirror <副本路径>`，把修改并入项目文件；
  2. 受控文档再升版本号并运行 `release`。
- **技能写了新文件**：在对应的分类文件夹建立项目文件，并在对照表登记。
- **只改这里不会生效**：`python -m tools.docs check` 会报告不一致与未登记的文件。
