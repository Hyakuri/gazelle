"""Controlled documents: front matter, version logs, archive snapshots and baselines.

The rules are in docs/rules/DOCS_SYSTEM_CN.md. Text is compared and hashed with LF line endings so that
CRLF and LF checkouts agree. Archive files and the archive index are append-only.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DOCS_SYSTEM = "docs/rules/DOCS_SYSTEM_CN.md"
STATE = "docs/collab/STATE.md"
ROADMAP = "docs/collab/ROADMAP.md"
OVERVIEW_MD = "docs/README.md"
PORTAL_HTML = "docs/portal/index.html"
ARCHIVE_ROOT = "docs/archive"
ARCHIVE_INDEX = "docs/archive/ARCHIVE_INDEX.json"
BASELINE_ROOT = "docs/archive/baselines"
SKILL_ROOT = "docs/superpowers"
MIRROR_HEADER = ["项目文件", "技能副本", "说明"]
UNSYNCED_MIRROR = "技能副本未同步"

DOC_STATUSES = ("草案", "待确认", "已确认", "已确认（协调者）", "已取代")
FRONT_KEYS = ("doc_id", "title", "version", "status", "updated", "owner", "confirm_ref")
VERSION_HEADER = ["版本", "日期", "状态", "变更摘要", "确认", "归档"]
VERSION_HEADING = "## 版本记录"
PENDING_ARCHIVE_CELL = "由工具填写"

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ANCHOR_RE = re.compile(r"^<!-- portal:(table|block|mermaid) ([a-z0-9-]+) -->$")


class RecordError(Exception):
    """A record operation was refused; the message says why."""


# ---------------------------------------------------------------- text helpers

def normalize(text: str) -> str:
    return text.replace("\r\n", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return normalize(Path(path).read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> bool:
    """Write LF text, keeping CRLF when the existing file uses it. Returns True if the file changed."""
    path = Path(path)
    text = normalize(text)
    newline = "\n"
    if path.exists():
        raw = path.read_bytes()
        if normalize(raw.decode("utf-8")) == text:
            return False
        if b"\r\n" in raw:
            newline = "\r\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return True


# ---------------------------------------------------------------- versions

def parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.match(str(value).strip())
    if not match:
        raise RecordError("版本号必须是 主版本.次版本.修订号，例如 1.0.0：%r" % (value,))
    return tuple(int(part) for part in match.groups())


def is_date(value: str) -> bool:
    return bool(_DATE_RE.match(str(value)))


# ---------------------------------------------------------------- front matter

def split_front_matter(text: str) -> tuple[dict, str]:
    """Return (fields, body). Fields are strings; a file without front matter returns ({}, text)."""
    text = normalize(text)
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise RecordError("文件头缺少结束行 ---")
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise RecordError("文件头不是键值对")
    fields = {str(key): ("" if value is None else str(value)) for key, value in data.items()}
    return fields, text[end + len("\n---\n"):]


def front_matter_problems(fields: dict) -> list[str]:
    problems = []
    for key in FRONT_KEYS:
        if not fields.get(key, "").strip():
            problems.append("文件头缺少 %s" % key)
    if fields.get("version"):
        try:
            parse_version(fields["version"])
        except RecordError as error:
            problems.append(str(error))
    if fields.get("status") and fields["status"] not in DOC_STATUSES:
        problems.append("状态 %r 不在词表 %s 中" % (fields["status"], "、".join(DOC_STATUSES)))
    if fields.get("updated") and not is_date(fields["updated"]):
        problems.append("updated 必须是 YYYY-MM-DD：%r" % fields["updated"])
    return problems


def render_front_matter(fields: dict) -> str:
    lines = ["---"]
    for key in FRONT_KEYS:
        lines.append("%s: %s" % (key, fields[key]))
    for key, value in fields.items():
        if key not in FRONT_KEYS:
            lines.append("%s: %s" % (key, value))
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- tables and anchors

def split_row(line: str) -> list[str]:
    """Split a Markdown table row, honouring code spans and escaped pipes."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells, current, in_code, index = [], [], False, 0
    while index < len(stripped):
        char = stripped[index]
        if char == "\\" and index + 1 < len(stripped) and stripped[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "`":
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


@dataclass
class Table:
    header: list
    rows: list
    start: int  # line index of the header
    end: int  # line index after the last row

    def dicts(self) -> list:
        return [dict(zip(self.header, row)) for row in self.rows]


def _table_at(lines: list, index: int, label: str) -> Table:
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].lstrip().startswith("|"):
        raise RecordError("%s 之后没有表格" % label)
    start = index
    header = split_row(lines[index])
    if index + 1 >= len(lines) or not re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
        raise RecordError("%s 的表格缺少分隔行" % label)
    index += 2
    rows = []
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        cells = split_row(lines[index])
        if len(cells) != len(header):
            raise RecordError("%s 的表格第 %d 行有 %d 列，表头有 %d 列" % (label, index + 1, len(cells), len(header)))
        rows.append(cells)
        index += 1
    return Table(header, rows, start, index)


def find_anchor(text: str, kind: str, name: str) -> int:
    marker = "<!-- portal:%s %s -->" % (kind, name)
    hits = [i for i, line in enumerate(normalize(text).split("\n")) if line.strip() == marker]
    if len(hits) != 1:
        raise RecordError("标记 %s 应出现一次，实际 %d 次" % (marker, len(hits)))
    return hits[0]


def anchored_table(text: str, name: str) -> Table:
    lines = normalize(text).split("\n")
    return _table_at(lines, find_anchor(text, "table", name) + 1, "portal:table " + name)


def anchored_block(text: str, name: str) -> str:
    lines = normalize(text).split("\n")
    start = find_anchor(text, "block", name)
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "<!-- /portal:block -->":
            return "\n".join(lines[start + 1:index]).strip("\n") + "\n"
    raise RecordError("portal:block %s 缺少结束标记 <!-- /portal:block -->" % name)


def anchored_mermaid(text: str, name: str) -> str:
    lines = normalize(text).split("\n")
    index = find_anchor(text, "mermaid", name) + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or lines[index].strip() != "```mermaid":
        raise RecordError("portal:mermaid %s 之后不是 ```mermaid 代码块" % name)
    for end in range(index + 1, len(lines)):
        if lines[end].strip() == "```":
            return "\n".join(lines[index + 1:end]) + "\n"
    raise RecordError("portal:mermaid %s 的代码块没有结束" % name)


def anchors_in(text: str) -> list:
    found = []
    for line in normalize(text).split("\n"):
        match = _ANCHOR_RE.match(line.strip())
        if match:
            found.append(match.groups())
    return found


# ---------------------------------------------------------------- version log

@dataclass
class VersionRow:
    version: str
    date: str
    status: str
    summary: str
    confirm: str
    archive: str


def version_table(text: str) -> Table:
    lines = normalize(text).split("\n")
    hits = [i for i, line in enumerate(lines) if line.strip() == "<!-- portal:versions -->"]
    if len(hits) != 1:
        raise RecordError("版本记录标记 <!-- portal:versions --> 应出现一次，实际 %d 次" % len(hits))
    table = _table_at(lines, hits[0] + 1, "portal:versions")
    if table.header != VERSION_HEADER:
        raise RecordError("版本记录表头应为 %s" % " | ".join(VERSION_HEADER))
    return table


def version_rows(text: str) -> list:
    return [VersionRow(*row) for row in version_table(text).rows]


def split_version_section(body: str) -> tuple[str, str]:
    """Split a body into (content, version section). The version section starts at '## 版本记录'."""
    body = normalize(body)
    marker = "\n" + VERSION_HEADING + "\n"
    position = body.rfind(marker)
    if position < 0:
        return body, ""
    return body[:position + 1], body[position + 1:]


# ---------------------------------------------------------------- registry

@dataclass
class RegistryEntry:
    doc_id: str
    name: str
    path: str
    category: str
    confirmation: str


def strip_code(cell: str) -> str:
    cell = cell.strip()
    if cell.startswith("`") and cell.endswith("`"):
        return cell[1:-1]
    return cell


def load_registry(root: Path) -> list:
    table = anchored_table(read_text(Path(root) / DOCS_SYSTEM), "registry")
    if table.header[:5] != ["ID", "名称", "路径", "类别", "确认方式"]:
        raise RecordError("受控文档清单的表头应为 ID | 名称 | 路径 | 类别 | 确认方式")
    entries = [RegistryEntry(row[0], row[1], strip_code(row[2]), row[3], row[4]) for row in table.rows]
    ids = [entry.doc_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise RecordError("受控文档清单中的 ID 重复")
    return entries


# ---------------------------------------------------------------- skill copies (docs/superpowers)

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_TARGET_RE = re.compile(r"\]\(([^)\s]+)\)")


def rebase_links(text: str, from_file: str, to_file: str) -> str:
    """Rewrite relative Markdown link targets written for from_file so they work from to_file.

    Code blocks and inline code are left alone: links quoted there belong to another document's context.
    """
    if posixpath.dirname(from_file) == posixpath.dirname(to_file):
        return text

    def rewrite(match):
        target = match.group(1)
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            return match.group(0)
        path, sep, fragment = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(from_file), path))
        rebased = posixpath.relpath(resolved, posixpath.dirname(to_file) or ".")
        return "](%s)" % (rebased + (sep + fragment if sep else ""))

    lines, in_fence = [], False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            parts = re.split(r"(`[^`]*`)", line)
            parts[0::2] = [_TARGET_RE.sub(rewrite, part) for part in parts[0::2]]
            line = "".join(parts)
        lines.append(line)
    return "\n".join(lines)


@dataclass
class Mirror:
    project: str
    mirror: str
    note: str


def load_mirrors(root: Path) -> list:
    """Pairs of (authoritative project file, skill copy under docs/superpowers) from DOCS_SYSTEM."""
    table = anchored_table(read_text(Path(root) / DOCS_SYSTEM), "mirrors")
    if table.header != MIRROR_HEADER:
        raise RecordError("技能副本对照表的表头应为 %s" % " | ".join(MIRROR_HEADER))
    pairs = [Mirror(strip_code(row[0]), strip_code(row[1]), row[2]) for row in table.rows]
    for pair in pairs:
        if not pair.mirror.startswith(SKILL_ROOT + "/"):
            raise RecordError("技能副本必须在 %s/ 下：%s" % (SKILL_ROOT, pair.mirror))
    mirrors = [pair.mirror for pair in pairs]
    if len(set(mirrors)) != len(mirrors):
        raise RecordError("技能副本对照表中有重复的技能副本")
    return pairs


def mirror_states(root: Path) -> list:
    """State of every skill copy: synced, missing, stale (equals a released old version), conflict, no-project."""
    root = Path(root)
    controlled = {entry.path: entry.doc_id for entry in load_registry(root)}
    index = load_index(root)
    states = []
    for pair in load_mirrors(root):
        project_file, mirror_file = root / pair.project, root / pair.mirror
        if not project_file.exists():
            states.append((pair, "no-project"))
            continue
        if not mirror_file.exists():
            states.append((pair, "missing"))
            continue
        expected = rebase_links(read_text(project_file), pair.project, pair.mirror)
        mirror_text = read_text(mirror_file)
        if mirror_text == expected:
            states.append((pair, "synced"))
            continue
        handled = {sha256_text(rebase_links(read_text(root / entry["path"]), pair.project, pair.mirror))
                   for entry in index["documents"]
                   if entry["doc_id"] == controlled.get(pair.project) and (root / entry["path"]).exists()}
        handled |= {entry["sha256"] for key in ("adopted", "mirror_writes") for entry in index.get(key, [])
                    if entry["mirror"] == pair.mirror}
        states.append((pair, "stale" if sha256_text(mirror_text) in handled else "conflict"))
    return states


def unregistered_skill_files(root: Path) -> list:
    root = Path(root)
    known = {pair.mirror for pair in load_mirrors(root)}
    found = []
    skill_dir = root / SKILL_ROOT
    if skill_dir.exists():
        for path in sorted(skill_dir.rglob("*.md")):
            rel = path.relative_to(root).as_posix()
            if rel not in known and not path.name.upper().startswith("README"):
                found.append(rel)
    return found


def mirror_problems(root: Path) -> list:
    problems = []
    for pair, state in mirror_states(root):
        if state in ("missing", "stale"):
            problems.append("%s：%s（运行 python -m tools.docs build）" % (UNSYNCED_MIRROR, pair.mirror))
        elif state == "conflict":
            problems.append("技能副本 %s 与项目文件 %s 不一致，且不是已发布的旧版本：用 adopt 并入项目文件，或手工合并" % (
                pair.mirror, pair.project))
        elif state == "no-project":
            problems.append("技能副本对照表中的项目文件不存在：%s" % pair.project)
    problems.extend("技能目录中有未登记的文件 %s：在项目文件夹建立对应文档，并在技能副本对照表登记" % rel
                    for rel in unregistered_skill_files(root))
    return problems


def sync_mirrors(root: Path) -> list:
    """Copy each project file over a missing or stale skill copy. Conflicting copies are left untouched.

    Every content the tool writes is recorded, so a later sync never mistakes the tool's own write for a skill edit.
    """
    root = Path(root)
    changed = []
    index = load_index(root)
    writes = index.setdefault("mirror_writes", [])
    for pair, state in mirror_states(root):
        if state in ("missing", "stale"):
            text = rebase_links(read_text(root / pair.project), pair.project, pair.mirror)
            write_text(root / pair.mirror, text)
            record = {"mirror": pair.mirror, "sha256": sha256_text(text)}
            if record not in writes:
                writes.append(record)
            changed.append(pair.mirror)
    if changed:
        save_index(root, index)
    return changed


def adopt_mirror(root: Path, mirror: str, *, merged: bool = False) -> Path:
    """Copy an edited skill copy into its project file and record its content as handled.

    merged=True only records the content as handled, for edits that were merged into the project file by hand.
    Without it, the copy is refused when the project file has unreleased edits.
    """
    root = Path(root)
    pairs = {pair.mirror: pair for pair in load_mirrors(root)}
    if mirror not in pairs:
        raise RecordError("%s 不在技能副本对照表中" % mirror)
    pair = pairs[mirror]
    controlled = {entry.path: entry.doc_id for entry in load_registry(root)}
    project_file = root / pair.project
    mirror_text = read_text(root / mirror)
    index = load_index(root)
    record = {"mirror": mirror, "project": pair.project, "sha256": sha256_text(mirror_text)}
    if merged:
        if record not in index.setdefault("adopted", []):
            index["adopted"].append(record)
            save_index(root, index)
        return project_file
    if pair.project in controlled and project_file.exists():
        text = read_text(project_file)
        fields, _ = split_front_matter(text)
        stored = index_entry(load_index(root), controlled[pair.project], fields.get("version", ""))
        if stored is None or stored["sha256"] != sha256_text(text):
            raise RecordError("项目文件 %s 有尚未发布的修改；先发布或手工合并，再并入技能副本" % pair.project)
    write_text(project_file, rebase_links(mirror_text, mirror, pair.project))
    if record not in index.setdefault("adopted", []):
        index["adopted"].append(record)
        save_index(root, index)
    return project_file


# ---------------------------------------------------------------- archive index

def archive_path(doc_id: str, version: str) -> str:
    return "%s/%s/%s_v%s.md" % (ARCHIVE_ROOT, doc_id, doc_id, version)


def load_index(root: Path) -> dict:
    path = Path(root) / ARCHIVE_INDEX
    if not path.exists():
        return {"version": 1, "documents": [], "baselines": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_index(root: Path, index: dict) -> None:
    write_text(Path(root) / ARCHIVE_INDEX, json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def index_entry(index: dict, doc_id: str, version: str):
    for entry in index["documents"]:
        if entry["doc_id"] == doc_id and entry["version"] == version:
            return entry
    return None


def archive_text(root: Path, doc_id: str, version: str, text: str, *, date: str, status: str, summary: str,
                 source: str, index: dict) -> dict:
    """Store an immutable snapshot and register it in the (in-memory) index."""
    parse_version(version)
    if index_entry(index, doc_id, version) is not None:
        raise RecordError("%s v%s 已经归档，归档不能覆盖" % (doc_id, version))
    rel = archive_path(doc_id, version)
    target = Path(root) / rel
    if target.exists():
        raise RecordError("归档文件已存在：%s" % rel)
    write_text(target, text)
    entry = {"doc_id": doc_id, "version": version, "date": date, "status": status, "summary": summary,
             "path": rel, "sha256": sha256_text(text), "source": source}
    index["documents"].append(entry)
    index["documents"].sort(key=lambda item: (item["doc_id"], parse_version(item["version"])))
    return entry


def relative_link(from_file: str, to_file: str) -> str:
    return posixpath.relpath(to_file, posixpath.dirname(from_file))


def archive_cell(doc_path: str, doc_id: str, version: str) -> str:
    return "[v%s](%s)" % (version, relative_link(doc_path, archive_path(doc_id, version)))


def set_version_archive_cell(text: str, row_index: int, cell: str) -> str:
    """Replace the 归档 cell of one version-log row."""
    lines = normalize(text).split("\n")
    table = version_table(text)
    line_index = table.start + 2 + row_index
    cells = split_row(lines[line_index])
    cells[5] = cell
    lines[line_index] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines)


# ---------------------------------------------------------------- checks

def check_records(root: Path) -> list:
    """Return a list of problems with the controlled documents and the archive (empty means OK)."""
    root = Path(root)
    problems = []
    try:
        registry = load_registry(root)
    except (RecordError, FileNotFoundError) as error:
        return ["受控文档清单：%s" % error]
    index = load_index(root)
    registered = {entry.doc_id for entry in registry}
    for entry in registry:
        doc_file = root / entry.path
        label = "%s（%s）" % (entry.doc_id, entry.path)
        if not doc_file.exists():
            problems.append("%s：文件不存在" % label)
            continue
        text = read_text(doc_file)
        try:
            fields, _ = split_front_matter(text)
        except RecordError as error:
            problems.append("%s：%s" % (label, error))
            continue
        problems.extend("%s：%s" % (label, item) for item in front_matter_problems(fields))
        if fields.get("doc_id") and fields["doc_id"] != entry.doc_id:
            problems.append("%s：文件头 doc_id 为 %s" % (label, fields["doc_id"]))
        try:
            rows = version_rows(text)
        except RecordError as error:
            problems.append("%s：%s" % (label, error))
            continue
        if not rows:
            problems.append("%s：版本记录为空" % label)
            continue
        top = rows[0]
        for key, value in (("version", top.version), ("updated", top.date), ("status", top.status)):
            if fields.get(key) and fields[key] != value:
                problems.append("%s：版本记录第一行的%s %s 与文件头 %s 不一致" % (
                    label, {"version": "版本", "updated": "日期", "status": "状态"}[key], value, fields[key]))
        previous = None
        for row in rows:
            try:
                current = parse_version(row.version)
            except RecordError as error:
                problems.append("%s：%s" % (label, error))
                continue
            if previous is not None and not current < previous:
                problems.append("%s：版本记录应从新到旧排列，%s 位置不对" % (label, row.version))
            previous = current
            if row.status not in DOC_STATUSES:
                problems.append("%s：v%s 的状态 %r 不在词表中" % (label, row.version, row.status))
            if not is_date(row.date):
                problems.append("%s：v%s 的日期 %r 格式不对" % (label, row.version, row.date))
            stored = index_entry(index, entry.doc_id, row.version)
            if stored is None:
                problems.append("%s：v%s 没有归档（运行 release）" % (label, row.version))
                continue
            expected_cell = archive_cell(entry.path, entry.doc_id, row.version)
            if row.archive != expected_cell:
                problems.append("%s：v%s 的归档链接应为 %s" % (label, row.version, expected_cell))
        logged = {row.version for row in rows}
        for stored in index["documents"]:
            if stored["doc_id"] == entry.doc_id and stored["version"] not in logged:
                problems.append("%s：归档中有 v%s，但版本记录没有这一行" % (label, stored["version"]))
        current_entry = index_entry(index, entry.doc_id, top.version)
        if current_entry is not None and current_entry["sha256"] != sha256_text(text):
            problems.append("%s：当前文件与 v%s 的归档不一致，有修改尚未发布（升版本号后运行 release）" % (label, top.version))
    for stored in index["documents"]:
        if stored["doc_id"] not in registered:
            problems.append("归档索引中的 %s 不在受控文档清单中" % stored["doc_id"])
        target = root / stored["path"]
        if not target.exists():
            problems.append("归档文件缺失：%s" % stored["path"])
        elif sha256_text(read_text(target)) != stored["sha256"]:
            problems.append("归档文件被改动：%s" % stored["path"])
    for baseline in index["baselines"]:
        for rel, digest in sorted(baseline["files"].items()):
            target = root / rel
            if not target.exists():
                problems.append("基线 %s 的文件缺失：%s" % (baseline["id"], rel))
            elif sha256_text(read_text(target)) != digest:
                problems.append("基线 %s 的文件被改动：%s" % (baseline["id"], rel))
    try:
        problems.extend(mirror_problems(root))
    except RecordError as error:
        problems.append("技能副本对照表：%s" % error)
    return problems


# ---------------------------------------------------------------- release, restore, snapshot

def source_files(root: Path) -> list:
    """Files whose content the views are built from (registry documents plus STATE and ROADMAP)."""
    paths = [entry.path for entry in load_registry(root)] + [STATE, ROADMAP]
    if DOCS_SYSTEM not in paths:
        paths.append(DOCS_SYSTEM)
    return sorted(set(paths))


def source_hashes(root: Path) -> dict:
    return {rel: sha256_text(read_text(Path(root) / rel)) for rel in source_files(root)}


def next_baseline_id(index: dict) -> str:
    numbers = [int(item["id"][1:]) for item in index["baselines"]]
    return "B%03d" % ((max(numbers) if numbers else 0) + 1)


def prepare_release(root: Path, doc_ids: list, index: dict) -> list:
    """Archive the current version of each document (filling its 归档 cell). Returns the new entries."""
    root = Path(root)
    registry = {entry.doc_id: entry for entry in load_registry(root)}
    created = []
    for doc_id in doc_ids:
        if doc_id not in registry:
            raise RecordError("%s 不在受控文档清单中" % doc_id)
        entry = registry[doc_id]
        doc_file = root / entry.path
        text = read_text(doc_file)
        fields, _ = split_front_matter(text)
        problems = front_matter_problems(fields)
        if problems:
            raise RecordError("%s：%s" % (doc_id, "；".join(problems)))
        rows = version_rows(text)
        if not rows or rows[0].version != fields["version"]:
            raise RecordError("%s：版本记录最上面一行必须是文件头的版本 %s" % (doc_id, fields["version"]))
        top = rows[0]
        if top.date != fields["updated"] or top.status != fields["status"]:
            raise RecordError("%s：版本记录第一行的日期或状态与文件头不一致" % doc_id)
        existing = [parse_version(item["version"]) for item in index["documents"] if item["doc_id"] == doc_id]
        if index_entry(index, doc_id, top.version) is not None:
            raise RecordError("%s v%s 已经发布过；修改后需要升版本号" % (doc_id, top.version))
        if existing and not parse_version(top.version) > max(existing):
            raise RecordError("%s：新版本 %s 必须大于已归档的最高版本" % (doc_id, top.version))
        text = set_version_archive_cell(text, 0, archive_cell(entry.path, doc_id, top.version))
        write_text(doc_file, text)
        created.append(archive_text(root, doc_id, top.version, text, date=top.date, status=top.status,
                                    summary=top.summary, source="worktree", index=index))
    return created


def record_baseline(root: Path, index: dict, baseline_id: str, *, date: str, note: str, files: dict) -> dict:
    root = Path(root)
    documents = {}
    for entry in load_registry(root):
        fields, _ = split_front_matter(read_text(root / entry.path))
        documents[entry.doc_id] = fields.get("version", "")
    baseline = {"id": baseline_id, "date": date, "note": note, "documents": documents,
                "sources": source_hashes(root), "files": {rel: sha256_text(text) for rel, text in files.items()}}
    index["baselines"].append(baseline)
    return baseline


def restore(root: Path, doc_id: str, from_version: str, to_version: str, *, status: str, summary: str,
            date: str) -> Path:
    """Write an archived version's body back as a new version; the existing version log is kept."""
    root = Path(root)
    if status not in DOC_STATUSES:
        raise RecordError("状态 %r 不在词表中" % status)
    if not is_date(date):
        raise RecordError("日期必须是 YYYY-MM-DD")
    registry = {entry.doc_id: entry for entry in load_registry(root)}
    if doc_id not in registry:
        raise RecordError("%s 不在受控文档清单中" % doc_id)
    index = load_index(root)
    stored = index_entry(index, doc_id, from_version)
    if stored is None:
        raise RecordError("%s v%s 没有归档，无法回档" % (doc_id, from_version))
    doc_file = root / registry[doc_id].path
    fields, body = split_front_matter(read_text(doc_file))
    rows = version_rows(read_text(doc_file))
    if not parse_version(to_version) > parse_version(rows[0].version):
        raise RecordError("回档后的版本号 %s 必须大于当前版本 %s" % (to_version, rows[0].version))
    _, old_body = split_front_matter(read_text(root / stored["path"]))
    old_content, _ = split_version_section(old_body)
    _, version_section = split_version_section(body)
    if not version_section:
        raise RecordError("%s 当前文件缺少“版本记录”一节" % doc_id)
    fields.update({"version": to_version, "status": status, "updated": date})
    new_row = "| %s | %s | %s | %s | %s | %s |" % (to_version, date, status, summary, "回档自 v%s" % from_version,
                                                  PENDING_ARCHIVE_CELL)
    section_lines = version_section.split("\n")
    table = _table_at(section_lines, next(i for i, line in enumerate(section_lines)
                                          if line.strip() == "<!-- portal:versions -->") + 1, "portal:versions")
    section_lines.insert(table.start + 2, new_row)
    text = render_front_matter(fields) + old_content.rstrip("\n") + "\n\n" + "\n".join(section_lines)
    write_text(doc_file, text)
    return doc_file
