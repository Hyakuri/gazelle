"""Command line for the documentation records: python -m tools.docs <command>. See docs/rules/DOCS_SYSTEM_CN.md §12."""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

from . import portal as P
from . import records as R


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _print_problems(problems: list) -> None:
    for item in problems:
        print("  - " + item)


def _build(root: Path) -> list:
    return R.sync_mirrors(root) + P.build(root)


def _release(root: Path, doc_ids: list, note: str, date: str) -> int:
    registry = {entry.doc_id: entry for entry in R.load_registry(root)}
    unknown = [doc_id for doc_id in doc_ids if doc_id not in registry]
    if unknown:
        raise R.RecordError("不在受控文档清单中：%s" % "、".join(unknown))
    blocking = [item for item in R.check_records(root)
                if not any(item.startswith("%s（" % doc_id) for doc_id in doc_ids)
                and not item.startswith(R.UNSYNCED_MIRROR)]
    if blocking:
        print("发布前检查未通过（与本次发布无关的问题需要先处理）：")
        _print_problems(blocking)
        return 1
    P.collect(root)  # fail before archiving if the views cannot be built
    index = R.load_index(root)
    created = R.prepare_release(root, doc_ids, index)
    R.save_index(root, index)
    synced = R.sync_mirrors(root)
    baseline = P.make_baseline(root, index, date=date, note=note)
    for entry in created:
        print("已归档 %s v%s -> %s" % (entry["doc_id"], entry["version"], entry["path"]))
    for rel in synced:
        print("已同步技能副本 %s" % rel)
    print("已建立基线 %s（%s）" % (baseline["id"], baseline["date"]))
    problems = P.check(root)
    if problems:
        print("发布后检查发现问题：")
        _print_problems(problems)
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.docs",
                                     description="受控文档的版本、归档、基线、技能副本与项目总览（docs/rules/DOCS_SYSTEM_CN.md）")
    parser.add_argument("--root", help="仓库根目录，默认为本工具所在的仓库")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="同步技能副本，重建 docs/portal/index.html 与 docs/README.md")
    commands.add_parser("check", help="检查视图同步、版本记录、归档与技能副本；有问题时退出码为 1")
    release = commands.add_parser("release", help="把受控文档的当前版本留档，并建立基线")
    release.add_argument("--doc", action="append", required=True, help="受控文档 ID，可重复")
    release.add_argument("--note", required=True, help="基线说明")
    release.add_argument("--date", help="基线日期 YYYY-MM-DD，默认今天")
    restore = commands.add_parser("restore", help="把已归档的旧版本正文写回为一个新版本（之后运行 release）")
    restore.add_argument("--doc", required=True)
    restore.add_argument("--from", dest="from_version", required=True)
    restore.add_argument("--to", dest="to_version", required=True)
    restore.add_argument("--status", required=True, choices=R.DOC_STATUSES)
    restore.add_argument("--summary", required=True)
    restore.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    adopt = commands.add_parser("adopt", help="把技能（superpowers）改过的副本并入项目文件（之后升版本并 release）")
    adopt.add_argument("--mirror", required=True, help="docs/superpowers/ 下的技能副本路径")
    adopt.add_argument("--merged", action="store_true", help="修改已手工合并进项目文件，只登记这份副本为已处理")
    snapshot = commands.add_parser("snapshot", help="不改文档版本，建立一个记录当前进展的基线")
    snapshot.add_argument("--note", required=True)
    snapshot.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            if (stream.encoding or "").lower().replace("-", "") != "utf8":
                stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    root = Path(args.root).resolve() if args.root else _repo_root()
    today = datetime.date.today().isoformat()
    try:
        if args.command == "build":
            changed = _build(root)
            print("已更新：%s" % "、".join(changed) if changed else "视图与技能副本已是最新")
            conflicts = [item for item in R.mirror_problems(root) if not item.startswith(R.UNSYNCED_MIRROR)]
            if conflicts:
                print("技能副本需要处理：")
                _print_problems(conflicts)
                return 1
            return 0
        if args.command == "check":
            problems = P.check(root)
            if problems:
                print("检查未通过：")
                _print_problems(problems)
                return 1
            print("检查通过：视图与技能副本已同步，版本记录与归档完好")
            return 0
        if args.command == "release":
            return _release(root, args.doc, args.note, args.date or today)
        if args.command == "restore":
            path = R.restore(root, args.doc, args.from_version, args.to_version, status=args.status,
                             summary=args.summary, date=args.date or today)
            print("已把 %s v%s 的正文写回 %s，新版本 %s。检查后运行 release。" % (
                args.doc, args.from_version, path.relative_to(root).as_posix(), args.to_version))
            return 0
        if args.command == "adopt":
            path = R.adopt_mirror(root, args.mirror, merged=args.merged)
            if args.merged:
                print("已登记 %s 的内容为已处理（手工合并进 %s）。" % (args.mirror, path.relative_to(root).as_posix()))
            else:
                print("已把 %s 并入 %s。受控文档请升版本号并运行 release。" % (args.mirror, path.relative_to(root).as_posix()))
            return 0
        if args.command == "snapshot":
            R.sync_mirrors(root)
            problems = R.check_records(root)
            if problems:
                print("建立基线前检查未通过：")
                _print_problems(problems)
                return 1
            baseline = P.make_baseline(root, R.load_index(root), date=args.date or today, note=args.note)
            print("已建立基线 %s（%s）" % (baseline["id"], baseline["date"]))
            return 0
    except R.RecordError as error:
        print("错误：%s" % error)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
