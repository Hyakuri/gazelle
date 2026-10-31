import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tools.docs import __main__ as cli
from tools.docs import portal as P
from tools.docs import records as R


def _doc(doc_id, version, status, body, rows=None):
    rows = rows or [(version, "2026-10-18", status, "首版", "Q-1", R.PENDING_ARCHIVE_CELL)]
    head = R.render_front_matter({"doc_id": doc_id, "title": doc_id, "version": version, "status": status,
                                  "updated": "2026-10-18", "owner": "Claude", "confirm_ref": "Q-1"})
    table = ["## 版本记录", "", "<!-- portal:versions -->", "| " + " | ".join(R.VERSION_HEADER) + " |",
             "| --- | --- | --- | --- | --- | --- |"] + ["| %s |" % " | ".join(row) for row in rows]
    return head + "\n# %s\n\n%s\n\n" % (doc_id, body.strip("\n")) + "\n".join(table) + "\n"


MERMAID = "```mermaid\nflowchart LR\n    A[\"起点\"] --> B[\"终点\"]\n```"

FILES = {
    "docs/rules/DOCS_SYSTEM_CN.md": _doc("DOCS", "1.0.0", "待确认", """
<!-- portal:block rules-summary -->
1. 单一来源，见 [目标](../goals.md)。
<!-- /portal:block -->

<!-- portal:mermaid docs-architecture -->
%s

<!-- portal:mermaid docs-workflow -->
%s

<!-- portal:table folders -->
| 文件夹 | 放什么 | 类别 | 版本方式 | 维护者 |
| --- | --- | --- | --- | --- |
| `docs/` | 目标 | 基线 | 受控 | Claude |

<!-- portal:table mirrors -->
| 项目文件 | 技能副本 | 说明 |
| --- | --- | --- |
| `docs/specs/system.md` | `docs/superpowers/specs/2026-10-18-system-design.md` | 受控文档 SYSTEM |

<!-- portal:table registry -->
| ID | 名称 | 路径 | 类别 | 确认方式 |
| --- | --- | --- | --- | --- |
| GOALS | 目标 | `docs/goals.md` | 基线 | 用户 |
| SYSTEM | 系统 | `docs/specs/system.md` | 基线 | 用户 |
| STAGE3 | 阶段 3 | `docs/specs/stage3.md` | 基线 | 用户 |
| DOCS | 规则 | `docs/rules/DOCS_SYSTEM_CN.md` | 规则 | 用户 |
""" % (MERMAID, MERMAID)),
    "docs/goals.md": _doc("GOALS", "1.0.0", "已确认", """
<!-- portal:block goals -->
1. 估计视线，见 [系统](specs/system.md)。
<!-- /portal:block -->

旧的正文。
"""),
    "docs/specs/system.md": _doc("SYSTEM", "1.0.0", "待确认", """
<!-- portal:block system-summary -->
- 输入三台摄像机，目标见 [目标](../goals.md)。
<!-- /portal:block -->

<!-- portal:mermaid architecture -->
%s

<!-- portal:table system-layers -->
| 层 | 做什么 | 主要组件 | 阶段 |
| --- | --- | --- | --- |
| L0 | 同步 | C01 | 2 |

<!-- portal:mermaid pipeline -->
%s

<!-- portal:table components -->
| 编号 | 环节 | 实现 | 输入 → 输出 | 阶段 | 相关任务 |
| --- | --- | --- | --- | --- | --- |
| C01 | 清单 | `tools/x.py` | 录像 → 清单 | 2 | TASK-131 |
| C02 | 视线 | 计划 | 人脸 → 视线 | 3 | TASK-303 |

<!-- portal:table products -->
| 产物 | 位置 | 生成者 | 说明 |
| --- | --- | --- | --- |
| 清单 | `inventory.json` | C01 | 指纹 |
""" % (MERMAID, MERMAID)),
    "docs/specs/stage3.md": _doc("STAGE3", "2.0.0", "待确认", """
<!-- portal:table feasibility-cameras -->
| 指标 | 前方 B | 右侧 A |
| --- | --- | --- |
| 虹膜 | 28.9 | 26.6 |

<!-- portal:table feasibility-combined -->
| 指标 | 数值 |
| --- | --- |
| 至少一台可用 | 62.0%% |

<!-- portal:mermaid evidence -->
%s

<!-- portal:mermaid stage3-tasks -->
%s
""" % (MERMAID, MERMAID)),
    "docs/collab/STATE.md": """# 状态

<!-- portal:table control -->
| 字段 | 当前值 |
| --- | --- |
| stage | 阶段 2 |
| writer | none |
| next_actor | user |
| current_task | 等待确认 |
| 更新 | 2026-10-18 |

<!-- portal:table queue -->
| 轮次 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| 5 | TASK-140 第 2 轮 | ready | 第一项 |

<!-- portal:block user-notes -->
- 请看 [路线图](ROADMAP.md)。
<!-- /portal:block -->

<!-- portal:table questions -->
| 编号 | 级别 | 提出者 | 内容 | 位置 | 状态 | 处理记录 |
| --- | --- | --- | --- | --- | --- | --- |
| Q-001 | B | Codex | 旧问题：已经处理 | 任务 | 已解决 | 已决定 |
| Q-002 | C | Claude | 确认设计：细节 | 设计 | 待用户 | 待确认 |
""",
    "docs/collab/ROADMAP.md": """# 路线图

<!-- portal:table stages -->
| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 1 | 迁移 | done |
| 2 | 数据 | 进行中 |

<!-- portal:table goal-progress -->
| 编号 | 目标 | 当前状态 |
| --- | --- | --- |
| G1 | 数据接入 | **已满足** |

<!-- portal:table tasks-stage2 -->
| 轮次 | 任务 | 状态 | 问题 | 规模 | 真实运行 |
| --- | --- | --- | --- | --- | --- |
| 1 | [TASK-131](tasks/TASK-131.md) 读取器 | accepted | GZ-07 | M | 否 |

<!-- portal:table tasks-stage3 -->
| 任务 | 内容 | 阶段 | 状态 | 关卡 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| TASK-303 | 视线候选 | 3.0 | proposed（待 D22） | GA | — |

<!-- portal:table gates -->
| 关卡 | 内容 | 任务 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| G0 | 虹膜大小 | 实测 | 通过 | 设计 |

<!-- portal:table decisions -->
| 决策 | 内容 | 状态 | 说明 |
| --- | --- | --- | --- |
| D1 | 关联 | 已批准 | TASK-101 |
| D22 | 设计：细节 | 待你决定 | Q-002 |
""",
}


class DocsRecordsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for rel, text in FILES.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cli.main(["--root", str(self.root)] + list(args))
        return code, out.getvalue()

    def release_all(self, note="初始"):
        return self.run_cli("release", "--doc", "GOALS", "--doc", "SYSTEM", "--doc", "STAGE3", "--doc", "DOCS",
                            "--note", note, "--date", "2026-10-18")

    def bump(self, rel, doc_id, version, status="待确认", summary="修订", body_edit=None):
        path = self.root / rel
        text = R.read_text(path)
        fields, body = R.split_front_matter(text)
        content, section = R.split_version_section(body)
        if body_edit:
            content = body_edit(content)
        fields["version"] = version
        fields["status"] = status
        lines = section.split("\n")
        header = lines.index("| " + " | ".join(R.VERSION_HEADER) + " |")
        lines.insert(header + 2, "| %s | 2026-10-18 | %s | %s | Q-1 | %s |" % (version, status, summary,
                                                                            R.PENDING_ARCHIVE_CELL))
        path.write_text(R.render_front_matter(fields) + content + "\n".join(lines), encoding="utf-8")

    def test_split_row_keeps_code_spans_and_escaped_pipes(self):
        self.assertEqual(R.split_row("| a | `x | y` | b \\| c |"), ["a", "`x | y`", "b | c"])

    def test_front_matter_problems_report_bad_version_and_status(self):
        problems = R.front_matter_problems({"doc_id": "A", "title": "t", "version": "1.0", "status": "完成",
                                            "updated": "2026-10-18", "owner": "o", "confirm_ref": "c"})
        self.assertTrue(any("版本号" in item for item in problems))
        self.assertTrue(any("词表" in item for item in problems))

    def test_release_archives_documents_and_creates_baseline(self):
        code, output = self.release_all()
        self.assertEqual(code, 0, output)
        index = R.load_index(self.root)
        self.assertEqual(sorted(entry["doc_id"] for entry in index["documents"]), ["DOCS", "GOALS", "STAGE3", "SYSTEM"])
        self.assertEqual([baseline["id"] for baseline in index["baselines"]], ["B001"])
        for rel in ("docs/archive/baselines/B001/index.html", "docs/archive/baselines/B001/README.md",
                    R.PORTAL_HTML, R.OVERVIEW_MD, "docs/archive/GOALS/GOALS_v1.0.0.md"):
            self.assertTrue((self.root / rel).exists(), rel)
        top = R.version_rows(R.read_text(self.root / "docs/goals.md"))[0]
        self.assertEqual(top.archive, "[v1.0.0](archive/GOALS/GOALS_v1.0.0.md)")
        self.assertEqual(P.check(self.root), [])
        page = R.read_text(self.root / R.PORTAL_HTML)
        self.assertIn("B001", page)
        self.assertIn('href="#doc-SYSTEM"', page)
        self.assertIn('<pre class="mermaid">', page)

    def test_unreleased_edit_is_reported(self):
        self.assertEqual(self.release_all()[0], 0)
        path = self.root / "docs/goals.md"
        path.write_text(R.read_text(path).replace("旧的正文。", "新的正文。"), encoding="utf-8")
        self.assertTrue(any("尚未发布" in item for item in R.check_records(self.root)))

    def test_release_without_new_version_is_refused(self):
        self.assertEqual(self.release_all()[0], 0)
        code, output = self.run_cli("release", "--doc", "GOALS", "--note", "重复", "--date", "2026-10-18")
        self.assertEqual(code, 2, output)
        self.assertEqual(len(R.load_index(self.root)["baselines"]), 1)

    def test_bump_release_and_restore_old_version(self):
        self.assertEqual(self.release_all()[0], 0)
        self.bump("docs/goals.md", "GOALS", "1.1.0", body_edit=lambda text: text.replace("旧的正文。", "新的正文。"))
        code, output = self.run_cli("release", "--doc", "GOALS", "--note", "改正文", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        code, output = self.run_cli("restore", "--doc", "GOALS", "--from", "1.0.0", "--to", "1.2.0", "--status", "待确认",
                                    "--summary", "回档到 1.0.0", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        text = R.read_text(self.root / "docs/goals.md")
        self.assertIn("旧的正文。", text)
        self.assertNotIn("新的正文。", text)
        self.assertEqual([row.version for row in R.version_rows(text)], ["1.2.0", "1.1.0", "1.0.0"])
        code, output = self.run_cli("release", "--doc", "GOALS", "--note", "回档", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        self.assertEqual([baseline["id"] for baseline in R.load_index(self.root)["baselines"]], ["B001", "B002", "B003"])
        self.assertEqual(P.check(self.root), [])

    def test_state_change_makes_views_stale_until_rebuilt(self):
        self.assertEqual(self.release_all()[0], 0)
        state = self.root / R.STATE
        state.write_text(R.read_text(state).replace("| next_actor | user |", "| next_actor | codex |"), encoding="utf-8")
        self.assertTrue(any("视图未同步" in item for item in P.check(self.root)))
        self.assertEqual(self.run_cli("build")[0], 0)
        self.assertEqual(P.check(self.root), [])
        latest, changed = P.baseline_status(P.collect(self.root))
        self.assertEqual((latest["id"], changed), ("B001", [R.STATE]))

    def test_tampered_archive_is_reported(self):
        self.assertEqual(self.release_all()[0], 0)
        archived = self.root / "docs/archive/GOALS/GOALS_v1.0.0.md"
        archived.write_text(R.read_text(archived) + "改动\n", encoding="utf-8")
        self.assertTrue(any("归档文件被改动" in item for item in R.check_records(self.root)))

    def test_snapshot_refuses_unreleased_changes(self):
        self.assertEqual(self.release_all()[0], 0)
        path = self.root / "docs/specs/system.md"
        path.write_text(R.read_text(path).replace("输入三台摄像机", "输入两台摄像机"), encoding="utf-8")
        code, output = self.run_cli("snapshot", "--note", "第 5 轮结束", "--date", "2026-10-18")
        self.assertEqual(code, 1, output)

    def test_views_are_deterministic(self):
        self.assertEqual(P.render_views(self.root), P.render_views(self.root))

    def test_task_classes_and_component_state(self):
        self.assertEqual(P.task_class("accepted（第 4 轮修复后）"), "done")
        self.assertEqual(P.task_class("部分通过（余项由 TASK-140 完成）"), "done")
        self.assertEqual(P.task_class("实现通过；第 2 轮 ready"), "active")
        self.assertEqual(P.task_class("changes-requested（第 2 轮）"), "fix")
        self.assertEqual(P.task_class("proposed（待 D22）"), "planned")
        self.assertEqual(P.task_class("待你确认"), "attention")
        classes = {"TASK-1": ["done"], "TASK-2": ["active"], "TASK-3": ["planned"]}
        self.assertEqual(P.component_state("TASK-1", classes), ("已实现", "done"))
        self.assertEqual(P.component_state("TASK-1、TASK-2", classes), ("进行中", "active"))
        self.assertEqual(P.component_state("TASK-1、TASK-3", classes), ("部分实现", "active"))
        self.assertEqual(P.component_state("TASK-3", classes), ("计划", "planned"))
        self.assertEqual(P.component_state("TASK-9", classes), ("未登记", "planned"))

    MIRROR = "docs/superpowers/specs/2026-10-18-system-design.md"

    def test_skill_copy_is_created_with_rebased_links(self):
        self.assertEqual(self.release_all()[0], 0)
        mirror = R.read_text(self.root / self.MIRROR)
        self.assertIn("[目标](../../goals.md)", mirror)
        self.assertIn("[目标](../goals.md)", R.read_text(self.root / "docs/specs/system.md"))
        self.assertEqual([state for _, state in R.mirror_states(self.root)], ["synced"])

    def test_released_new_version_refreshes_stale_skill_copy(self):
        self.assertEqual(self.release_all()[0], 0)
        self.bump("docs/specs/system.md", "SYSTEM", "1.0.1", body_edit=lambda text: text.replace("三台", "3 台"))
        code, output = self.run_cli("release", "--doc", "SYSTEM", "--note", "改写", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        self.assertIn("3 台", R.read_text(self.root / self.MIRROR))
        self.assertEqual(P.check(self.root), [])

    def test_build_between_edits_does_not_create_false_conflicts(self):
        self.assertEqual(self.release_all()[0], 0)
        self.bump("docs/specs/system.md", "SYSTEM", "1.0.1", body_edit=lambda text: text.replace("三台", "3 台"))
        self.assertEqual(self.run_cli("build")[0], 0)
        path = self.root / "docs/specs/system.md"
        path.write_text(R.read_text(path).replace("3 台", "三 台"), encoding="utf-8")
        self.assertEqual(self.run_cli("build")[0], 0)
        code, output = self.run_cli("release", "--doc", "SYSTEM", "--note", "两次修改", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        self.assertIn("三 台", R.read_text(self.root / self.MIRROR))
        self.assertEqual(P.check(self.root), [])

    def test_skill_edit_is_reported_and_adopted(self):
        self.assertEqual(self.release_all()[0], 0)
        mirror = self.root / self.MIRROR
        mirror.write_text(R.read_text(mirror).replace("输入三台摄像机", "技能改写的内容"), encoding="utf-8")
        self.assertTrue(any("需合并" in item or "不一致" in item for item in P.check(self.root)))
        code, output = self.run_cli("build")
        self.assertEqual(code, 1, output)
        self.assertIn("技能改写的内容", R.read_text(mirror))
        code, output = self.run_cli("adopt", "--mirror", self.MIRROR)
        self.assertEqual(code, 0, output)
        project = R.read_text(self.root / "docs/specs/system.md")
        self.assertIn("技能改写的内容", project)
        self.assertIn("[目标](../goals.md)", project)
        self.bump("docs/specs/system.md", "SYSTEM", "1.1.0")
        code, output = self.run_cli("release", "--doc", "SYSTEM", "--note", "并入技能修改", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        self.assertEqual(P.check(self.root), [])

    def test_hand_merged_skill_edit_can_be_marked_as_handled(self):
        self.assertEqual(self.release_all()[0], 0)
        mirror = self.root / self.MIRROR
        mirror.write_text(R.read_text(mirror).replace("输入三台摄像机", "技能改写的内容"), encoding="utf-8")
        self.bump("docs/specs/system.md", "SYSTEM", "1.1.0",
                  body_edit=lambda text: text.replace("输入三台摄像机", "手工合并后的内容"))
        code, output = self.run_cli("adopt", "--mirror", self.MIRROR, "--merged")
        self.assertEqual(code, 0, output)
        self.assertIn("手工合并后的内容", R.read_text(self.root / "docs/specs/system.md"))
        code, output = self.run_cli("release", "--doc", "SYSTEM", "--note", "手工合并", "--date", "2026-10-18")
        self.assertEqual(code, 0, output)
        self.assertIn("手工合并后的内容", R.read_text(mirror))
        self.assertEqual(P.check(self.root), [])

    def test_adopt_refuses_when_project_file_has_unreleased_edits(self):
        self.assertEqual(self.release_all()[0], 0)
        project = self.root / "docs/specs/system.md"
        project.write_text(R.read_text(project).replace("输入三台摄像机", "未发布的修改"), encoding="utf-8")
        code, output = self.run_cli("adopt", "--mirror", self.MIRROR)
        self.assertEqual(code, 2, output)
        self.assertIn("未发布的修改", R.read_text(project))

    def test_unregistered_skill_file_is_reported(self):
        self.assertEqual(self.release_all()[0], 0)
        extra = self.root / "docs/superpowers/plans/2026-10-19-new-plan.md"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text("# 新计划\n", encoding="utf-8")
        (self.root / "docs/superpowers/README_CN.md").write_text("# 说明\n", encoding="utf-8")
        problems = R.check_records(self.root)
        self.assertEqual([item for item in problems if "未登记" in item],
                         ["技能目录中有未登记的文件 docs/superpowers/plans/2026-10-19-new-plan.md：在项目文件夹建立对应文档，并在技能副本对照表登记"])

    def test_rebase_links_round_trip(self):
        text = "见 [A](../a.md#x)、[B](https://example.org)、[C](#c)。"
        moved = R.rebase_links(text, "docs/design/x.md", "docs/superpowers/specs/x.md")
        self.assertEqual(moved, "见 [A](../../a.md#x)、[B](https://example.org)、[C](#c)。")
        self.assertEqual(R.rebase_links(moved, "docs/superpowers/specs/x.md", "docs/design/x.md"), text)

    def test_rebase_links_leaves_code_alone(self):
        text = "[A](a.md)\n`[B](b.md)`\n```\n[C](c.md)\n```\n[D](d.md)"
        moved = R.rebase_links(text, "docs/design/x.md", "docs/superpowers/specs/x.md")
        self.assertEqual(moved, "[A](../../design/a.md)\n`[B](b.md)`\n```\n[C](c.md)\n```\n[D](../../design/d.md)")

    def test_column_roles(self):
        self.assertEqual(P.column_class("内容"), "c-long")
        self.assertEqual(P.column_class("位置"), "c-path")
        self.assertEqual(P.column_class("编号"), "c-narrow")
        self.assertEqual(P.column_class("状态"), "c-status")
        self.assertEqual(P.column_class("未知列"), "c-mid")

    def test_questions_table_marks_wide_content_column(self):
        self.assertEqual(self.release_all()[0], 0)
        page = R.read_text(self.root / R.PORTAL_HTML)
        self.assertIn('<th class="c-long">内容</th>', page)
        self.assertIn('<th class="c-path">位置</th>', page)
        self.assertNotIn("table.wide", page)

    def test_links_are_rewritten_for_each_view(self):
        embedded = {"docs/collab/STATE.md": "STATE"}
        self.assertEqual(P.rewrite_target("STATE.md", "docs/collab/ROADMAP.md", R.PORTAL_HTML, embedded), "#doc-STATE")
        self.assertEqual(P.rewrite_target("tasks/T.md#x", "docs/collab/ROADMAP.md", R.PORTAL_HTML, embedded),
                         "../collab/tasks/T.md#x")
        self.assertEqual(P.rewrite_target("tasks/T.md", "docs/collab/ROADMAP.md", R.OVERVIEW_MD, embedded),
                         "collab/tasks/T.md")
        self.assertEqual(P.rewrite_target("https://example.org", "docs/a.md", R.PORTAL_HTML, embedded),
                         "https://example.org")


if __name__ == "__main__":
    unittest.main()
