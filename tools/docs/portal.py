"""Build the project overview web page and its Markdown twin from the project documents.

Both views come from the same collected data, so they cannot drift apart. The rules are in
docs/rules/DOCS_SYSTEM_CN.md §9. Output is deterministic: it depends only on the source files and the archive index.
"""
from __future__ import annotations

import html
import posixpath
import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML

from . import records as R
from .portal_assets import CSS, FONTS_URL, JS, MERMAID_URL

REQUIRED_ANCHORS = {
    "GOALS": [("block", "goals")],
    "SYSTEM": [("block", "system-summary"), ("mermaid", "architecture"), ("table", "system-layers"),
               ("mermaid", "pipeline"), ("table", "components"), ("table", "products")],
    "STAGE3": [("table", "feasibility-cameras"), ("table", "feasibility-combined"), ("mermaid", "evidence"),
               ("mermaid", "stage3-tasks")],
    "DOCS": [("block", "rules-summary"), ("mermaid", "docs-architecture"), ("mermaid", "docs-workflow"),
             ("table", "folders"), ("table", "registry"), ("table", "mirrors")],
    "STATE": [("table", "control"), ("table", "queue"), ("block", "user-notes"), ("table", "questions")],
    "ROADMAP": [("table", "stages"), ("table", "goal-progress"), ("table", "tasks-stage2"), ("table", "tasks-stage3"),
                ("table", "gates"), ("table", "decisions")],
}
LIVING = {"STATE": R.STATE, "ROADMAP": R.ROADMAP}
TITLE = "Gazelle 项目总览"

DOC_CLASS = {"草案": "planned", "待确认": "attention", "已确认": "done", "已确认（协调者）": "done", "已取代": "muted"}
DECISION_CLASS = {"已批准": "done", "待你决定": "attention", "待决": "planned", "暂停": "paused", "已取代": "muted"}
QUESTION_CLASS = {"待用户": "attention", "待 Claude": "active", "待 Codex": "active", "已解决": "done"}
GATE_CLASS = {"未开始": "planned", "进行中": "active", "通过": "done", "未通过": "fix"}
MIRROR_LABEL = {"synced": ("已同步", "done"), "missing": ("待生成", "attention"), "stale": ("待同步", "attention"),
                "conflict": ("需合并", "fix"), "no-project": ("缺项目文件", "fix")}
TASK_LABEL = {"done": "已完成", "active": "进行中", "ready": "可执行", "fix": "需修复", "blocked": "等待前置",
              "paused": "暂停", "attention": "待你确认", "planned": "计划"}
GOAL_LABEL = {"done": "已满足", "active": "部分满足", "planned": "未开始"}
STAGE_LABEL = {"done": "已完成", "active": "进行中", "attention": "待你确认", "muted": "不纳入", "planned": "计划"}
ACTOR_NAME = {"user": "你（用户）", "codex": "Codex", "claude": "Claude", "none": "无"}

# Column roles decide widths: short identifiers stay on one line, prose keeps a readable minimum width, paths may
# break after separators, and any other column gets a moderate minimum so it can never collapse to a few characters.
NARROW_COLUMNS = {"编号", "决策", "关卡", "ID", "版本", "基线", "级别", "提出者", "规模", "日期", "阶段", "轮次", "层",
                  "类别", "主要组件", "物理编号", "决定", "归档", "快照", "同步", "Key", "Date", "Revision", "Row",
                  "Label"}
PATH_COLUMNS = {"位置", "实现", "文件", "路径", "证据", "依赖", "相关任务", "项目文件", "技能副本", "文件夹"}
TEXT_COLUMNS = {"任务", "要点", "变更摘要", "目标", "放什么", "做什么", "输入 → 输出", "当前状态", "文档版本", "指标",
                "与本项目的匹配", "回答的问题", "Content", "Definition", "Handling", "Condition"}
LONG_COLUMNS = {"内容", "说明", "处理记录", "当前值", "你的回答（2026-10-15）", "通过条件（提议，可由你调整）"}


# ---------------------------------------------------------------- status classification

def task_class(text: str) -> str:
    """Map a free-text task status from ROADMAP or STATE to a display class."""
    lowered = text.lower()
    if "待你" in lowered:
        return "attention"
    if "changes-requested" in lowered:
        return "fix"
    if any(word in lowered for word in ("实现通过", "进行中", "ready-for-review")):
        return "active"
    if "ready" in lowered:
        return "ready"
    if "blocked" in lowered:
        return "blocked"
    if "暂停" in lowered:
        return "paused"
    if any(word in lowered for word in ("accepted", "done", "部分通过", "完成", "已批准")):
        return "done"
    return "planned"


def stage_class(text: str) -> str:
    lowered = text.lower()
    if lowered.strip() == "done" or lowered.startswith("done"):
        return "done"
    if "进行中" in lowered:
        return "active"
    if "待你" in lowered or "批准" in lowered:
        return "attention"
    if "不纳入" in lowered:
        return "muted"
    return "planned"


def goal_class(text: str) -> str:
    if text.startswith("**已满足**") or text.startswith("已满足"):
        return "done"
    if "基本满足" in text or "部分" in text or "已实现" in text:
        return "active"
    return "planned"


def component_state(related: str, task_classes: dict) -> tuple:
    classes = [cls for task in re.findall(r"TASK-\d+", related) for cls in task_classes.get(task, [])]
    if not classes:
        return "未登记", "planned"
    if any(cls in ("fix", "active", "attention", "ready") for cls in classes):
        return "进行中", "active"
    if all(cls == "done" for cls in classes):
        return "已实现", "done"
    if any(cls == "done" for cls in classes):
        return "部分实现", "active"
    if "paused" in classes:
        return "暂停", "paused"
    return "计划", "planned"


def column_class(name: str) -> str:
    if name == "状态":
        return "c-status"
    if name in NARROW_COLUMNS:
        return "c-narrow"
    if name in PATH_COLUMNS:
        return "c-path"
    if name in LONG_COLUMNS:
        return "c-long"
    if name in TEXT_COLUMNS:
        return "c-text"
    return "c-mid"


# ---------------------------------------------------------------- collection

def _strip_comment_lines(text: str) -> str:
    return re.sub(r"(?m)^[ \t]*<!--.*?-->[ \t]*\n", "", text)


def collect(root: Path) -> dict:
    root = Path(root)
    registry = R.load_registry(root)
    sources = {entry.doc_id: entry.path for entry in registry}
    sources.update(LIVING)
    texts = {doc_id: R.read_text(root / path) for doc_id, path in sources.items()}
    for doc_id, anchors in REQUIRED_ANCHORS.items():
        if doc_id not in texts:
            raise R.RecordError("缺少来源 %s" % doc_id)
        for kind, name in anchors:
            R.find_anchor(texts[doc_id], kind, name)
    docs = []
    for entry in registry:
        fields, _ = R.split_front_matter(texts[entry.doc_id])
        docs.append({"id": entry.doc_id, "name": entry.name, "path": entry.path, "category": entry.category,
                     "confirmation": entry.confirmation, "fields": fields,
                     "versions": R.version_rows(texts[entry.doc_id])})
    roadmap, state, rules = texts["ROADMAP"], texts["STATE"], texts["DOCS"]
    data = {
        "docs": docs,
        "sources": sources,
        "texts": texts,
        "control": {row[0]: row[1] for row in R.anchored_table(state, "control").rows},
        "queue": R.anchored_table(state, "queue"),
        "questions": R.anchored_table(state, "questions"),
        "user_notes": R.anchored_block(state, "user-notes"),
        "stages": R.anchored_table(roadmap, "stages"),
        "goal_progress": R.anchored_table(roadmap, "goal-progress"),
        "tasks2": R.anchored_table(roadmap, "tasks-stage2"),
        "tasks3": R.anchored_table(roadmap, "tasks-stage3"),
        "gates": R.anchored_table(roadmap, "gates"),
        "decisions": R.anchored_table(roadmap, "decisions"),
        "goals": R.anchored_block(texts["GOALS"], "goals"),
        "system_summary": R.anchored_block(texts["SYSTEM"], "system-summary"),
        "architecture": R.anchored_mermaid(texts["SYSTEM"], "architecture"),
        "system_layers": R.anchored_table(texts["SYSTEM"], "system-layers"),
        "pipeline": R.anchored_mermaid(texts["SYSTEM"], "pipeline"),
        "components": R.anchored_table(texts["SYSTEM"], "components"),
        "products": R.anchored_table(texts["SYSTEM"], "products"),
        "feasibility_cameras": R.anchored_table(texts["STAGE3"], "feasibility-cameras"),
        "feasibility_combined": R.anchored_table(texts["STAGE3"], "feasibility-combined"),
        "evidence": R.anchored_mermaid(texts["STAGE3"], "evidence"),
        "stage3_tasks": R.anchored_mermaid(texts["STAGE3"], "stage3-tasks"),
        "rules": R.anchored_block(rules, "rules-summary"),
        "docs_architecture": R.anchored_mermaid(rules, "docs-architecture"),
        "docs_workflow": R.anchored_mermaid(rules, "docs-workflow"),
        "folders": R.anchored_table(rules, "folders"),
        "mirrors": R.anchored_table(rules, "mirrors"),
        "mirror_states": {pair.mirror: state_name for pair, state_name in R.mirror_states(root)},
        "index": R.load_index(root),
        "source_hashes": R.source_hashes(root),
    }
    _check_columns(data)
    task_classes = {}
    for table in (data["tasks2"], data["tasks3"]):
        for row in table.dicts():
            for task in re.findall(r"TASK-\d+", row.get("任务", "")):
                task_classes.setdefault(task, []).append(task_class(row["状态"]))
    data["task_classes"] = task_classes
    return data


def _check_columns(data: dict) -> None:
    expected = {
        "queue": ["轮次", "任务", "状态", "说明"],
        "questions": ["编号", "级别", "提出者", "内容", "位置", "状态", "处理记录"],
        "stages": ["阶段", "目标", "状态"],
        "goal_progress": ["编号", "目标", "当前状态"],
        "tasks2": ["轮次", "任务", "状态", "问题", "规模", "真实运行"],
        "tasks3": ["任务", "内容", "阶段", "状态", "关卡", "依赖"],
        "gates": ["关卡", "内容", "任务", "状态", "证据"],
        "decisions": ["决策", "内容", "状态", "说明"],
        "components": ["编号", "环节", "实现", "输入 → 输出", "阶段", "相关任务"],
        "folders": ["文件夹", "放什么", "类别", "版本方式", "维护者"],
        "mirrors": R.MIRROR_HEADER,
    }
    for key, header in expected.items():
        if data[key].header != header:
            raise R.RecordError("表格 %s 的表头应为 %s，实际为 %s" % (key, " | ".join(header), " | ".join(data[key].header)))
    vocab = (("decisions", "状态", DECISION_CLASS), ("questions", "状态", QUESTION_CLASS), ("gates", "状态", GATE_CLASS))
    for key, column, allowed in vocab:
        for row in data[key].dicts():
            if row[column] not in allowed:
                raise R.RecordError("表格 %s 的状态 %r 不在词表 %s 中" % (key, row[column], "、".join(allowed)))


# ---------------------------------------------------------------- links and markdown

def rewrite_target(target: str, source: str, output: str, embedded: dict) -> str:
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return target
    path, _, fragment = target.partition("#")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if output.endswith(".html") and resolved in embedded:
        return "#doc-" + embedded[resolved]
    rel = posixpath.relpath(resolved, posixpath.dirname(output))
    return rel + ("#" + fragment if fragment else "")


def rewrite_markdown_links(text: str, source: str, output: str) -> str:
    return R.rebase_links(text, source, output)


def soft_breaks(fragment: str) -> str:
    """Allow line breaks after path separators inside inline code."""
    return re.sub(r"(<code>)(.*?)(</code>)",
                  lambda m: m.group(1) + re.sub(r"([/_.\\-])", r"\1<wbr>", m.group(2)) + m.group(3),
                  fragment, flags=re.S)


def _classify_tables(tokens) -> None:
    """Give rendered Markdown tables the same column classes as generated tables."""
    index = 0
    while index < len(tokens):
        if tokens[index].type != "table_open":
            index += 1
            continue
        headers, scan = [], index
        while tokens[scan].type != "thead_close":
            if tokens[scan].type == "th_open":
                headers.append(tokens[scan + 1].content.strip())
            scan += 1
        classes = [column_class(name) for name in headers]
        column = 0
        while tokens[index].type != "table_close":
            token = tokens[index]
            if token.type == "tr_open":
                column = 0
            elif token.type in ("th_open", "td_open"):
                if column < len(classes) and classes[column]:
                    token.attrJoin("class", classes[column])
                column += 1
            index += 1


class Renderer:
    def __init__(self, output: str, embedded: dict):
        self.output = output
        self.embedded = embedded
        self.md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
        self.md.add_render_rule("fence", self._fence)

    @staticmethod
    def _fence(self, tokens, idx, options, env):
        token = tokens[idx]
        if token.info.strip() == "mermaid":
            return '<div class="diagram"><pre class="mermaid">%s</pre></div>\n' % html.escape(token.content)
        return RendererHTML.fence(self, tokens, idx, options, env)

    def _relink(self, tokens, source):
        for token in tokens:
            for child in (token.children or []):
                if child.type == "link_open":
                    child.attrSet("href", rewrite_target(child.attrGet("href") or "", source, self.output, self.embedded))

    def block(self, text: str, source: str) -> str:
        tokens = self.md.parse(_strip_comment_lines(text))
        self._relink(tokens, source)
        _classify_tables(tokens)
        rendered = self.md.renderer.render(tokens, self.md.options, {})
        rendered = re.sub(r'(<td[^>]*class="c-path"[^>]*>)(.*?)(</td>)',
                          lambda m: m.group(1) + soft_breaks(m.group(2)) + m.group(3), rendered, flags=re.S)
        return rendered.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

    def inline(self, text: str, source: str) -> str:
        tokens = self.md.parseInline(text)
        self._relink(tokens, source)
        return self.md.renderer.render(tokens, self.md.options, {})


def chip(label: str, cls: str) -> str:
    return '<span class="chip %s">%s</span>' % (cls, html.escape(label))


FOLD_COLUMNS = {"处理记录", "说明"}
FOLD_LENGTH = 140


def plain_text(markdown: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    return re.sub(r"[*`]", "", text).strip()


def folded(cell_html: str, markdown: str) -> str:
    """Show the opening of a long cell with a toggle for the full text, so one long record cannot stretch a row."""
    text = plain_text(markdown)
    if len(text) <= FOLD_LENGTH:
        return cell_html
    preview = html.escape(text[:72].rstrip("，。；、 ")) + "…"
    return ('<details class="cell-more"><summary><span class="preview">%s</span><span class="toggle"></span></summary>'
            '<div class="full">%s</div></details>' % (preview, cell_html))


def mermaid_html(source: str) -> str:
    return '<div class="diagram"><pre class="mermaid">%s</pre></div>' % html.escape(source)


def status_html(render: Renderer, value: str, kind: str, source: str) -> str:
    """A chip with a short label; the original wording follows when it says more than the label."""
    if kind == "task":
        cls = task_class(value)
        label = TASK_LABEL[cls]
        bare = value.strip("*` ").lower()
        detail = "" if bare in ("accepted", "done", "ready", "proposed", "完成", "进行中", "changes-requested") else value
    elif kind == "goal":
        cls = goal_class(value)
        label, detail = GOAL_LABEL[cls], value
    else:
        mapping = {"decision": DECISION_CLASS, "question": QUESTION_CLASS, "gate": GATE_CLASS, "doc": DOC_CLASS}[kind]
        cls, label, detail = mapping.get(value, "planned"), value, ""
    small = '<div class="small">%s</div>' % render.inline(detail, source) if detail else ""
    return chip(label, cls) + small


def table_html(render: Renderer, table: R.Table, source: str, *, status=None, tags=None, row_id=None, extra=None,
               roles=None) -> str:
    """Render a parsed table. status=(column, kind) turns that column into chips; extra adds computed columns."""
    roles = roles or {}
    header = list(table.header) + [name for name, _ in (extra or [])]
    classes = [roles.get(name, column_class(name)) for name in header]
    out = ['<div class="table-wrap"><table><thead><tr>']
    out.extend('<th class="%s">%s</th>' % (cls, html.escape(name)) if cls else "<th>%s</th>" % html.escape(name)
               for name, cls in zip(header, classes))
    out.append("</tr></thead><tbody>")
    for row in table.dicts():
        attrs = ""
        if tags:
            attrs += ' data-tags="%s"' % html.escape(tags(row))
        if row_id:
            attrs += ' id="%s"' % html.escape(row_id(row))
        out.append("<tr%s>" % attrs)
        for position, name in enumerate(table.header):
            value = row[name]
            cls = classes[position]
            if status and name == status[0]:
                cell = status_html(render, value, status[1], source)
            else:
                cell = render.inline(value, source)
                if cls == "c-path":
                    cell = soft_breaks(cell)
                elif name in FOLD_COLUMNS:
                    cell = folded(cell, value)
            if position == 0:
                cls = (cls + " id").strip()
            out.append('<td class="%s">%s</td>' % (cls, cell) if cls else "<td>%s</td>" % cell)
        for (name, function), cls in zip(extra or [], classes[len(table.header):]):
            out.append('<td class="%s">%s</td>' % (cls, function(row)) if cls else "<td>%s</td>" % function(row))
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def simple_table(header: list, rows: list) -> str:
    """A table from already-rendered HTML cells, with the same column roles."""
    classes = [column_class(name) for name in header]
    out = ['<div class="table-wrap"><table><thead><tr>']
    out.extend('<th class="%s">%s</th>' % (cls, html.escape(name)) for name, cls in zip(header, classes))
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>%s</tr>" % "".join('<td class="%s">%s</td>' % (cls, cell) for cls, cell in zip(classes, row)))
    out.append("</tbody></table></div>")
    return "".join(out)


# ---------------------------------------------------------------- baseline status and pending items

def baseline_status(data: dict) -> tuple:
    baselines = data["index"]["baselines"]
    if not baselines:
        return None, []
    latest = baselines[-1]
    changed = sorted(rel for rel, digest in data["source_hashes"].items() if latest["sources"].get(rel) != digest)
    return latest, changed


def short_title(text: str) -> str:
    """The clause before the first colon, which in the question and decision tables names the item."""
    head = re.split(r"[：:]", text, maxsplit=1)[0].strip()
    return head if len(head) <= 60 else head[:59] + "…"


def pending(data: dict) -> dict:
    """What waits for the user: open questions, undecided decisions, documents awaiting confirmation."""
    return {
        "questions": [row for row in data["questions"].dicts() if row["状态"] == "待用户"],
        "decisions": [row for row in data["decisions"].dicts() if row["状态"] == "待你决定"],
        "docs": [doc for doc in data["docs"] if doc["fields"].get("status") == "待确认"],
    }


# ---------------------------------------------------------------- HTML

def build_html(data: dict, output: str, *, variant: str = "full") -> str:
    embedded = {path: doc_id for doc_id, path in data["sources"].items()}
    render = Renderer(output, embedded)
    src = data["sources"]
    control = data["control"]
    latest, changed = baseline_status(data)
    out_dir = posixpath.dirname(output)
    parts = []
    baseline_label = "%s · %s" % (latest["id"], latest["date"]) if latest else "尚无基线"
    if variant == "full":
        parts.append('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
                     '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
    parts.append("<title>%s</title>\n" % TITLE)
    parts.append('<meta name="claude:viewport-fit-sides" content="cover">\n')
    parts.append('<link rel="stylesheet" href="%s">\n' % html.escape(FONTS_URL))
    parts.append("<style>%s</style>\n" % CSS)
    if variant == "full":
        parts.append("</head>\n<body>\n")
    parts.append('<header class="topbar"><div class="brand"><span class="mark">Gazelle</span>'
                 '<span class="sub">工位视线与注意力项目总览</span></div>'
                 '<span class="osd">基线 %s</span>'
                 '<button class="theme-btn" id="theme-toggle" type="button">深色</button></header>'
                 '<div class="heatbar" aria-hidden="true"></div>\n' % html.escape(baseline_label))
    nav = [("overview", "总览"), ("design", "系统设计"), ("pipeline", "数据流程"), ("progress", "开发进展"),
           ("decisions", "决策与待确认"), ("documents", "文档与版本"), ("reader", "文档原文")]
    parts.append('<div class="layout"><nav class="rail" aria-label="目录">%s</nav><main>\n' % "".join(
        '<a href="#%s">%s</a>' % (anchor, label) for anchor, label in nav))

    # overview
    actor = control.get("next_actor", "").strip("`")
    parts.append('<section id="overview"><h2>总览</h2><p class="lede">项目当前在哪里、轮到谁、需要你处理什么。'
                 '内容由仓库中的文档自动生成。</p>')
    readouts = [("当前阶段", render.inline(control.get("stage", ""), src["STATE"])),
                ("轮到", html.escape(ACTOR_NAME.get(actor, actor))),
                ("当前任务", render.inline(control.get("current_task", ""), src["STATE"])),
                ("最近更新", render.inline(control.get("更新", ""), src["STATE"]))]
    parts.append('<div class="readouts">%s</div>' % "".join(
        '<div class="readout"><div class="label">%s</div><div class="value">%s</div></div>' % (label, value)
        for label, value in readouts))
    waiting = pending(data)
    if any(waiting.values()):
        lines = ['<li>%s<div><a class="id mono" href="#q-%s">%s</a> %s</div></li>' % (
            chip("问题", "attention"), html.escape(row["编号"]), html.escape(row["编号"]),
            render.inline(short_title(row["内容"]), src["STATE"])) for row in waiting["questions"]]
        if waiting["decisions"]:
            lines.append('<li>%s<div>%s</div></li>' % (chip("决策", "attention"), "、".join(
                '<a class="mono" href="#d-%s">%s</a> %s' % (html.escape(row["决策"]), html.escape(row["决策"]),
                                                            render.inline(short_title(row["内容"]), src["ROADMAP"]))
                for row in waiting["decisions"])))
        if waiting["docs"]:
            lines.append('<li>%s<div>%s</div></li>' % (chip("文档", "attention"), "、".join(
                '<a href="#doc-%s">%s v%s</a>' % (doc["id"], html.escape(doc["name"]), html.escape(doc["fields"]["version"]))
                for doc in waiting["docs"])))
        title = "开发暂停中，等待你确认" if actor == "user" else "需要你处理的事项"
        parts.append('<div class="banner" style="margin-top:16px"><strong>%s</strong><ul class="todo">%s</ul></div>' % (
            title, "".join(lines)))
    parts.append("<h3>阶段</h3><ol class=\"stages\">")
    for row in data["stages"].dicts():
        cls = stage_class(row["状态"])
        detail = row["状态"] if row["状态"].strip("*` ").lower() not in ("done", "进行中", "proposed", "未开始") else ""
        parts.append('<li class="%s"><div class="num">阶段 %s</div><div class="goal">%s</div>%s%s</li>' % (
            cls, html.escape(row["阶段"]), render.inline(row["目标"], src["ROADMAP"]), chip(STAGE_LABEL[cls], cls),
            '<div class="small">%s</div>' % render.inline(detail, src["ROADMAP"]) if detail else ""))
    parts.append("</ol>")
    parts.append('<div class="grid-2" style="margin-top:16px"><div class="panel prose"><h3 style="margin-top:0">项目目标</h3>%s</div>'
                 '<div class="panel"><h3 style="margin-top:0">目标进展</h3>%s</div></div>' % (
                     render.block(data["goals"], src["GOALS"]),
                     table_html(render, data["goal_progress"], src["ROADMAP"], status=("当前状态", "goal"),
                                roles={"当前状态": "c-status c-text"})))
    parts.append('<details class="history" style="margin-top:16px"><summary><span class="title">给你的说明（来自 STATE）</span>'
                 '</summary><div class="inner prose">%s</div></details>' % render.block(data["user_notes"], src["STATE"]))
    parts.append("</section>\n")

    # design
    parts.append('<section id="design"><h2>系统设计</h2><p class="lede">系统由哪些层组成、各自做什么。'
                 '详见<a href="#doc-SYSTEM">系统总体设计</a>与<a href="#doc-STAGE3">阶段 3 设计</a>。</p>')
    parts.append('<div class="panel prose">%s</div>' % render.block(data["system_summary"], src["SYSTEM"]))
    parts.append("<h3>总体架构</h3>" + mermaid_html(data["architecture"]))
    parts.append("<h3>分层</h3>" + table_html(render, data["system_layers"], src["SYSTEM"]))
    parts.append("<h3>视线证据的降级层级（阶段 3）</h3>" + mermaid_html(data["evidence"]))
    parts.append("<h3>可行性实测（2026-10-18，只读）</h3>" + table_html(render, data["feasibility_cameras"], src["STAGE3"]))
    parts.append('<div style="margin-top:12px">%s</div>' % table_html(render, data["feasibility_combined"], src["STAGE3"]))
    parts.append("</section>\n")

    # pipeline
    def component_cell(row):
        label, cls = component_state(row["相关任务"], data["task_classes"])
        return chip(label, cls)
    parts.append('<section id="pipeline"><h2>数据流程</h2><p class="lede">从原始录像到注视位置的每个环节。'
                 '“完成情况”由 ROADMAP 中相关任务的状态推算。</p>')
    parts.append(mermaid_html(data["pipeline"]))
    parts.append("<h3>环节</h3>" + table_html(render, data["components"], src["SYSTEM"],
                                             extra=[("完成情况", component_cell)], roles={"完成情况": "c-status"}))
    parts.append("<h3>数据产物与位置</h3>" + table_html(render, data["products"], src["SYSTEM"],
                                                   roles={"位置": "c-path c-wide"}))
    parts.append("</section>\n")

    # progress
    parts.append('<section id="progress"><h2>开发进展</h2><p class="lede">本轮与下一轮的任务、各阶段任务、可行性关卡。'
                 '来源：STATE 与 ROADMAP。</p>')
    parts.append("<h3>本轮与下一轮</h3>" + table_html(render, data["queue"], src["STATE"], status=("状态", "task")))
    parts.append("<h3>阶段 2 任务</h3>" + table_html(render, data["tasks2"], src["ROADMAP"], status=("状态", "task"),
                                                  roles={"问题": "c-narrow"}))
    parts.append("<h3>阶段 3 任务（提议）</h3>" + table_html(render, data["tasks3"], src["ROADMAP"], status=("状态", "task"),
                                                       roles={"任务": "c-narrow", "依赖": "c-text"}))
    parts.append(mermaid_html(data["stage3_tasks"]))
    parts.append("<h3>可行性关卡</h3>" + table_html(render, data["gates"], src["ROADMAP"], status=("状态", "gate"),
                                                 roles={"任务": "c-narrow"}))
    parts.append("</section>\n")

    # decisions
    parts.append('<section id="decisions"><h2>决策与待确认</h2><p class="lede">已经确认的决定与仍需回答的问题。</p>')
    parts.append('<div class="filters" data-filter-group="#decisions tr[data-tags]" role="group" aria-label="筛选">'
                 '<button type="button" data-filter="all" aria-pressed="true">全部</button>'
                 '<button type="button" data-filter="attention" aria-pressed="false">待你处理</button>'
                 '<button type="button" data-filter="active" aria-pressed="false">处理中</button>'
                 '<button type="button" data-filter="done" aria-pressed="false">已确认或已解决</button>'
                 '<button type="button" data-filter="other" aria-pressed="false">暂停、待决、已取代</button></div>')

    def tag_of(mapping):
        def tags(row):
            cls = mapping[row["状态"]]
            return cls if cls in ("attention", "active", "done") else "other"
        return tags
    parts.append("<h3>决策</h3>" + table_html(render, data["decisions"], src["ROADMAP"], status=("状态", "decision"),
                                            tags=tag_of(DECISION_CLASS), row_id=lambda row: "d-" + row["决策"]))
    parts.append("<h3>待决问题</h3>" + table_html(render, data["questions"], src["STATE"], status=("状态", "question"),
                                              tags=tag_of(QUESTION_CLASS), row_id=lambda row: "q-" + row["编号"]))
    parts.append("</section>\n")

    # documents and versions
    parts.append('<section id="documents"><h2>文档与版本</h2><p class="lede">文档按文件夹分类管理；设计与规则有版本号与归档。'
                 '规则见<a href="#doc-DOCS">文档记录体系与版本规则</a>。</p>')
    parts.append('<div class="panel prose">%s</div>' % render.block(data["rules"], src["DOCS"]))
    parts.append("<h3>文档管理架构</h3>" + mermaid_html(data["docs_architecture"]))
    parts.append("<h3>修改与发布流程</h3>" + mermaid_html(data["docs_workflow"]))
    parts.append("<h3>文件夹</h3>" + table_html(render, data["folders"], src["DOCS"], roles={"文件夹": "c-narrow"}))
    rows = []
    for doc in data["docs"]:
        fields = doc["fields"]
        rows.append(['<span class="mono">%s</span>' % doc["id"], html.escape(doc["name"]),
                     '<span class="mono">v%s</span>' % html.escape(fields.get("version", "")),
                     status_html(render, fields.get("status", ""), "doc", doc["path"]),
                     '<span class="mono">%s</span>' % html.escape(fields.get("updated", "")),
                     html.escape(fields.get("confirm_ref", "")),
                     '<a href="#doc-%s">阅读</a> · <a href="%s">%s</a>' % (
                         doc["id"], html.escape(posixpath.relpath(doc["path"], out_dir)),
                         soft_breaks("<code>%s</code>" % html.escape(doc["path"])))])
    parts.append("<h3>受控文档</h3>" + simple_table(["ID", "名称", "版本", "状态", "日期", "确认", "文件"], rows))
    parts.append("<h3>版本历史</h3>")
    for doc in data["docs"]:
        history = []
        for row in doc["versions"]:
            archive = R.archive_path(doc["id"], row.version)
            history.append(['<span class="mono">v%s</span>' % html.escape(row.version),
                            '<span class="mono">%s</span>' % html.escape(row.date),
                            status_html(render, row.status, "doc", doc["path"]),
                            render.inline(row.summary, doc["path"]), render.inline(row.confirm, doc["path"]),
                            '<a href="%s">快照</a>' % html.escape(posixpath.relpath(archive, out_dir))])
        parts.append('<details class="history"><summary><span class="mono">%s</span><span class="title">%s</span>%s'
                     '<span class="small">共 %d 个版本</span></summary><div class="inner">%s</div></details>' % (
                         doc["id"], html.escape(doc["name"]), chip("v" + doc["fields"].get("version", ""), "active"),
                         len(doc["versions"]),
                         simple_table(["版本", "日期", "状态", "变更摘要", "确认", "快照"], history)))
    parts.append("<h3>基线快照</h3>")
    baselines = data["index"]["baselines"]
    if baselines:
        rows = []
        for baseline in reversed(baselines):
            versions = "、".join("%s v%s" % item for item in sorted(baseline["documents"].items()))
            page = "%s/%s/index.html" % (R.BASELINE_ROOT, baseline["id"])
            rows.append(['<span class="mono">%s</span>' % baseline["id"],
                         '<span class="mono">%s</span>' % html.escape(baseline["date"]), html.escape(baseline["note"]),
                         '<span class="small">%s</span>' % html.escape(versions),
                         '<a href="%s">打开网页</a>' % html.escape(posixpath.relpath(page, out_dir))])
        parts.append(simple_table(["基线", "日期", "说明", "文档版本", "快照"], rows))
        if changed:
            parts.append('<p class="small">%s 之后有更新的来源：%s。下次建立基线时留档。</p>' % (
                latest["id"], "、".join("<code>%s</code>" % html.escape(item) for item in changed)))
    else:
        parts.append('<p class="small">尚无基线。</p>')

    def mirror_cell(row):
        label, cls = MIRROR_LABEL[data["mirror_states"].get(R.strip_code(row["技能副本"]), "missing")]
        return chip(label, cls)
    parts.append('<h3>技能副本（superpowers）</h3><p class="small">superpowers 技能在 <code>docs/superpowers/</code> 下工作。'
                 '项目文件是权威版本，技能副本由工具自动同步。</p>')
    parts.append(table_html(render, data["mirrors"], src["DOCS"], extra=[("同步", mirror_cell)],
                            roles={"同步": "c-status"}))
    parts.append("</section>\n")

    # reader
    parts.append('<section id="reader"><h2>文档原文</h2><p class="lede">受控文档与 STATE、ROADMAP 的全文，'
                 '与仓库中的 Markdown 同步生成。</p>')
    reader = [(doc["id"], doc["name"], doc["path"], doc["fields"]) for doc in data["docs"]]
    reader += [("STATE", "协同状态（STATE）", src["STATE"], {}), ("ROADMAP", "开发路线图（ROADMAP）", src["ROADMAP"], {})]
    for doc_id, name, path, fields in reader:
        _, body = R.split_front_matter(data["texts"][doc_id])
        badge = chip("v" + fields["version"], "active") + chip(fields["status"], DOC_CLASS.get(fields["status"], "planned")) \
            if fields else chip("活文档", "planned")
        parts.append('<details class="doc" id="doc-%s"><summary><span class="mono">%s</span><span class="title">%s</span>%s'
                     '<span class="small">%s</span></summary><div class="inner prose">%s</div></details>' % (
                         doc_id, doc_id, html.escape(name), badge, html.escape(path), render.block(body, path)))
    parts.append("</section>\n</main></div>\n")
    digest = R.sha256_text("".join(sorted(data["source_hashes"].values())))[:12]
    parts.append('<footer><div class="inner">本页由 <code>python -m tools.docs build</code> 从 %d 个来源文件生成，'
                 '不要手改。来源指纹 <span class="mono">%s</span>。流程图打开时从 jsDelivr 加载 Mermaid；'
                 '离线时显示流程图源码。</div></footer>\n' % (len(data["source_hashes"]), digest))
    if variant == "full":
        parts.append('<script src="%s"></script>\n' % MERMAID_URL)
    parts.append("<script>%s</script>\n" % JS)
    if variant == "full":
        parts.append("</body>\n</html>\n")
    return "".join(parts)


# ---------------------------------------------------------------- Markdown overview

def _md_table(table: R.Table, source: str, output: str, extra=None) -> str:
    header = list(table.header) + [name for name, _ in (extra or [])]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for row in table.dicts():
        cells = [rewrite_markdown_links(row[name], source, output) for name in table.header]
        cells += [function(row) for _, function in (extra or [])]
        lines.append("| " + " | ".join(cell.replace("\n", " ") for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def _mermaid_md(source: str) -> list:
    return ["```mermaid", source.rstrip("\n"), "```", ""]


def build_markdown(data: dict, output: str) -> str:
    src = data["sources"]
    control = data["control"]
    latest, changed = baseline_status(data)
    out_dir = posixpath.dirname(output)
    out = ["# Gazelle 项目总览", "",
           "> 本文件由 `python -m tools.docs build` 自动生成，与 [总览网页](%s) 内容相同，不要手改。"
           "规则见 [文档记录体系与版本规则](%s)。" % (posixpath.relpath(R.PORTAL_HTML, out_dir),
                                                posixpath.relpath(src["DOCS"], out_dir)), ""]
    if latest:
        note = "；其后有更新的来源：%s" % "、".join("`%s`" % item for item in changed) if changed else ""
        out += ["当前基线：**%s**（%s）%s。" % (latest["id"], latest["date"], note), ""]
    out += ["## 1. 总览", "", "| 项目 | 内容 |", "| --- | --- |"]
    actor = control.get("next_actor", "").strip("`")
    for label, key in (("当前阶段", "stage"), ("当前任务", "current_task"), ("最近更新", "更新")):
        out.append("| %s | %s |" % (label, rewrite_markdown_links(control.get(key, ""), src["STATE"], output)))
    out.insert(len(out) - 1, "| 轮到 | %s |" % ACTOR_NAME.get(actor, actor))
    out.append("")
    waiting = pending(data)
    if any(waiting.values()):
        out += ["### 需要你处理", ""]
        for row in waiting["questions"]:
            out.append("- **问题 %s**：%s" % (row["编号"], rewrite_markdown_links(short_title(row["内容"]), src["STATE"], output)))
        if waiting["decisions"]:
            out.append("- **决策**：%s" % "；".join("%s %s" % (row["决策"], short_title(row["内容"]))
                                                for row in waiting["decisions"]))
        if waiting["docs"]:
            out.append("- **待确认文档**：%s" % "、".join("%s v%s" % (doc["name"], doc["fields"]["version"])
                                                     for doc in waiting["docs"]))
        out.append("")
    out += ["### 阶段", "", _md_table(data["stages"], src["ROADMAP"], output)]
    out += ["### 项目目标", "", rewrite_markdown_links(data["goals"], src["GOALS"], output)]
    out += ["### 目标进展", "", _md_table(data["goal_progress"], src["ROADMAP"], output)]
    out += ["## 2. 系统设计", "", rewrite_markdown_links(data["system_summary"], src["SYSTEM"], output),
            "### 总体架构", ""] + _mermaid_md(data["architecture"]) + \
           ["### 分层", "", _md_table(data["system_layers"], src["SYSTEM"], output),
            "### 视线证据的降级层级（阶段 3）", ""] + _mermaid_md(data["evidence"]) + \
           ["### 可行性实测（2026-10-18，只读）", "", _md_table(data["feasibility_cameras"], src["STAGE3"], output),
            _md_table(data["feasibility_combined"], src["STAGE3"], output)]

    def component_cell(row):
        return component_state(row["相关任务"], data["task_classes"])[0]
    out += ["## 3. 数据流程", ""] + _mermaid_md(data["pipeline"]) + \
           ["完成情况由 ROADMAP 中相关任务的状态推算。", "",
            _md_table(data["components"], src["SYSTEM"], output, extra=[("完成情况", component_cell)]),
            "### 数据产物与位置", "", _md_table(data["products"], src["SYSTEM"], output)]
    out += ["## 4. 开发进展", "", "### 本轮与下一轮", "", _md_table(data["queue"], src["STATE"], output),
            "### 阶段 2 任务", "", _md_table(data["tasks2"], src["ROADMAP"], output),
            "### 阶段 3 任务（提议）", "", _md_table(data["tasks3"], src["ROADMAP"], output)] + \
        _mermaid_md(data["stage3_tasks"]) + \
           ["### 可行性关卡", "", _md_table(data["gates"], src["ROADMAP"], output)]
    out += ["## 5. 决策与待确认", "", "### 决策", "", _md_table(data["decisions"], src["ROADMAP"], output),
            "### 待决问题", "", _md_table(data["questions"], src["STATE"], output)]
    out += ["## 6. 文档与版本", "", rewrite_markdown_links(data["rules"], src["DOCS"], output),
            "### 文档管理架构", ""] + _mermaid_md(data["docs_architecture"]) + \
           ["### 修改与发布流程", ""] + _mermaid_md(data["docs_workflow"]) + \
           ["### 文件夹", "", _md_table(data["folders"], src["DOCS"], output),
            "### 受控文档", "", "| ID | 名称 | 版本 | 状态 | 日期 | 确认 | 文件 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for doc in data["docs"]:
        fields = doc["fields"]
        out.append("| %s | %s | v%s | %s | %s | %s | [%s](%s) |" % (
            doc["id"], doc["name"], fields.get("version", ""), fields.get("status", ""), fields.get("updated", ""),
            fields.get("confirm_ref", ""), posixpath.basename(doc["path"]), posixpath.relpath(doc["path"], out_dir)))
    out.append("")
    out += ["### 版本历史", ""]
    for doc in data["docs"]:
        out += ["#### %s %s" % (doc["id"], doc["name"]), "", "| 版本 | 日期 | 状态 | 变更摘要 | 确认 | 快照 |",
                "| --- | --- | --- | --- | --- | --- |"]
        for row in doc["versions"]:
            archive = posixpath.relpath(R.archive_path(doc["id"], row.version), out_dir)
            out.append("| v%s | %s | %s | %s | %s | [快照](%s) |" % (
                row.version, row.date, row.status, rewrite_markdown_links(row.summary, doc["path"], output),
                rewrite_markdown_links(row.confirm, doc["path"], output), archive))
        out.append("")
    out += ["### 基线快照", ""]
    baselines = data["index"]["baselines"]
    if baselines:
        out += ["| 基线 | 日期 | 说明 | 文档版本 | 快照 |", "| --- | --- | --- | --- | --- |"]
        for baseline in reversed(baselines):
            versions = "、".join("%s v%s" % item for item in sorted(baseline["documents"].items()))
            page = posixpath.relpath("%s/%s/index.html" % (R.BASELINE_ROOT, baseline["id"]), out_dir)
            out.append("| %s | %s | %s | %s | [网页](%s) |" % (baseline["id"], baseline["date"], baseline["note"],
                                                               versions, page))
        out.append("")
    else:
        out += ["尚无基线。", ""]

    def mirror_cell(row):
        return MIRROR_LABEL[data["mirror_states"].get(R.strip_code(row["技能副本"]), "missing")][0]
    out += ["### 技能副本（superpowers）", "", "项目文件是权威版本，技能副本由工具自动同步。", "",
            _md_table(data["mirrors"], src["DOCS"], output, extra=[("同步", mirror_cell)])]
    return "\n".join(out).rstrip("\n") + "\n"


# ---------------------------------------------------------------- build and check

def render_views(root: Path, output_dir: str = None) -> dict:
    """Return {relative path: text} for the two views; output_dir places them elsewhere (baseline snapshots)."""
    data = collect(root)
    html_path = (output_dir + "/index.html") if output_dir else R.PORTAL_HTML
    md_path = (output_dir + "/README.md") if output_dir else R.OVERVIEW_MD
    return {html_path: build_html(data, html_path), md_path: build_markdown(data, md_path)}


def build(root: Path) -> list:
    changed = []
    for rel, text in render_views(root).items():
        if R.write_text(Path(root) / rel, text):
            changed.append(rel)
    return changed


def stale_views(root: Path) -> list:
    stale = []
    for rel, text in render_views(root).items():
        target = Path(root) / rel
        if not target.exists() or R.read_text(target) != R.normalize(text):
            stale.append(rel)
    return stale


def check(root: Path) -> list:
    problems = R.check_records(root)
    try:
        stale = stale_views(root)
    except R.RecordError as error:
        return problems + ["生成视图失败：%s" % error]
    problems.extend("视图未同步：%s（运行 python -m tools.docs build）" % rel for rel in stale)
    return problems


def make_baseline(root: Path, index: dict, *, date: str, note: str) -> dict:
    """Record a new baseline, write the live views and an immutable snapshot of them, and save the index."""
    root = Path(root)
    if not R.is_date(date):
        raise R.RecordError("日期必须是 YYYY-MM-DD")
    baseline_id = R.next_baseline_id(index)
    snapshot_dir = "%s/%s" % (R.BASELINE_ROOT, baseline_id)
    if (root / snapshot_dir).exists():
        raise R.RecordError("基线目录已存在：%s" % snapshot_dir)
    baseline = R.record_baseline(root, index, baseline_id, date=date, note=note, files={})
    written = []
    try:
        R.save_index(root, index)
        live = render_views(root)
        snapshot = render_views(root, snapshot_dir)
        for rel, text in live.items():
            R.write_text(root / rel, text)
        for rel, text in snapshot.items():
            R.write_text(root / rel, text)
            written.append(root / rel)
    except Exception:
        index["baselines"].remove(baseline)
        R.save_index(root, index)
        for path in written:
            path.unlink()
        raise
    baseline["files"] = {rel: R.sha256_text(text) for rel, text in sorted(snapshot.items())}
    R.save_index(root, index)
    return baseline
