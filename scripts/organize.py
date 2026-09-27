#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作文件自动整理引擎 v2。

只读命令：plan / check / selftest / validate / dsh-official
会改磁盘：apply / undo / archive（都必须显式调用）
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import sys
import tomllib

DEFAULT_REGISTRY = os.path.expanduser("~/.dsh/storages/auto-organize/registry.toml")
RULES_REL = ".organize/rules.toml"
REPORTS_REL = ".organize/reports"
JOURNAL_REL = ".organize/journal"
LOCK_REL = ".organize/lock"
KEEP_REPORTS = 30

SKIP_DIR_NAMES = {"node_modules", "__pycache__", "vendor", ".venv", "site-packages"}
SKIP_DIR_SUFFIXES = (".dist-info", ".libs")
SKIP_FILE_SUFFIXES = (".pyc", ".pyo", ".lock", ".tmp")
SKIP_FILE_NAMES = {".DS_Store", "Thumbs.db", "AGENTS.md", "CLAUDE.md",
                   "AGENTS.local.md", "CLAUDE.local.md"}
OFFICIAL_DSH_NAMES = ["AGENTS.md", "CLAUDE.md", "AGENTS.local.md", "CLAUDE.local.md",
                      ".git", ".dsh", ".dsh-module-fallback", "node_modules",
                      "__pycache__", "vendor"]


def eprint(*a):
    print(*a, file=sys.stderr)


def read_toml(path, what):
    if not os.path.isfile(path):
        eprint(f"错误：{what}不存在：{path}")
        sys.exit(2)
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as ex:
        eprint(f"错误：{what}无法解析：{path}：{ex}")
        sys.exit(2)


def load_registry(path):
    data = read_toml(path, "注册表")
    entries = data.get("workspaces")
    if not isinstance(entries, list) or not entries:
        eprint("错误：注册表缺少 [[workspaces]] 段")
        sys.exit(2)
    return entries


def load_rules(workspace):
    return read_toml(os.path.join(workspace, RULES_REL), "规则文件")


def admit(entries, workspace):
    if not workspace:
        eprint("错误：必须显式给出 --workspace")
        sys.exit(2)
    path = os.path.abspath(workspace)
    if not os.path.isdir(path):
        eprint(f"错误：工作区不存在：{path}")
        sys.exit(2)
    entry = None
    for e in entries:
        if os.path.abspath(str(e.get("path", ""))) == path:
            entry = e
            break
    if entry is None:
        eprint(f"错误：工作区未在注册表中：{path}")
        sys.exit(2)
    kind = str(entry.get("kind", ""))
    if kind != "documents" or not entry.get("enabled", False):
        eprint(f"错误：该工作区 kind={kind or '未设置'} enabled={entry.get('enabled')}，不允许整理")
        sys.exit(2)
    home = os.path.abspath(os.path.expanduser(os.environ.get("DSH_HOME") or "~/.dsh"))
    if path == home or path.startswith(home + os.sep):
        eprint(f"错误：不允许整理 $DSH_HOME 下的目录：{path}")
        sys.exit(2)
    if os.path.exists(os.path.join(path, ".git")) and not entry.get("allow_git", False):
        eprint("错误：目录含 .git（代码仓库）；确需整理请在注册表该条目写 allow_git = true")
        sys.exit(2)
    return path, entry


def skip_dir(name, rel_dir, extra):
    if name.startswith("."):
        return True
    if name in SKIP_DIR_NAMES or name.endswith(SKIP_DIR_SUFFIXES):
        return True
    rel = (rel_dir + "/" + name).strip("/")
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in extra)


def skip_file(name, rel, extra):
    if name.startswith("."):
        return True
    if name.endswith(SKIP_FILE_SUFFIXES) or name in SKIP_FILE_NAMES:
        return True
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in extra)


def walk_files(workspace, extra):
    for dirpath, dirnames, filenames in os.walk(workspace, topdown=True, followlinks=False):
        reldir = os.path.relpath(dirpath, workspace)
        reldir = "" if reldir == "." else reldir.replace(os.sep, "/")
        if reldir and (os.path.exists(os.path.join(dirpath, ".archived"))
                       or os.path.exists(os.path.join(dirpath, ".organize-ignore"))):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames
                       if not skip_dir(d, reldir, extra)
                       and not os.path.islink(os.path.join(dirpath, d))]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            rel = (reldir + "/" + fn) if reldir else fn
            if skip_file(fn, rel, extra):
                continue
            yield full, rel


def structurally_ok(rel):
    """已经在合乎规范的目录结构里，就不再折腾。"""
    parts = rel.split("/")
    top = parts[0]
    name = parts[-1]
    ext = os.path.splitext(name)[1].lower()
    if name == "README.md" or top in ("00-模板与规范", "99-待处理", "08-网络资源"):
        return True
    if top in ("01-教学计划", "02-培优辅潜"):
        if ext == ".md":
            return len(parts) >= 3 and parts[1] == "md文件"
        if ext in (".docx", ".doc"):
            return len(parts) == 2
        return False
    if top == "03-成绩":
        if ext in (".xlsx", ".csv"):
            return len(parts) >= 3 and parts[1] == "原始数据"
        if ext == ".md":
            return len(parts) >= 4 and parts[1] == "分析" and parts[2] == "md文件"
        if ext == ".docx":
            return len(parts) >= 3 and parts[1] == "分析"
        return False
    if top == "04-教案":
        if ext == ".md":
            return len(parts) >= 4 and parts[2] == "md文件"
        if ext == ".docx":
            return len(parts) == 3
        return False
    if top == "05-课件与文本":
        if "课件素材" in parts:
            return True
        if ext == ".enbx":
            return len(parts) >= 4 and parts[2] == "原始课件"
        if ext == ".md":
            return len(parts) >= 5 and parts[2] == "课件文本" and parts[3] == "md文件"
        return False
    if top == "06-工具与提示词":
        if ext == ".py":
            return len(parts) == 3 and parts[1] == "教程"
        if "历史版本" in rel and ext in (".md", ".bak"):
            return True
        if len(parts) >= 2 and parts[1] == "教程":
            if ext == ".md":
                return len(parts) >= 4 and parts[2] == "md文件"
            return len(parts) == 3
        if len(parts) >= 2 and parts[1] == "提示词":
            if ext == ".md":
                return len(parts) >= 4 and parts[2] == "md文件"
            return len(parts) == 3
        return False
    if top == "07-培训研修":
        if len(parts) >= 3 and parts[1] in ("学习文件", "心得体会"):
            if ext == ".md":
                return len(parts) >= 4 and parts[2] == "md文件"
            return len(parts) == 3
        return False
    return False


def chapter_of(name, chapters, rel=""):
    best, best_score = None, -1
    for ch, keys in chapters.items():
        for k in list(keys) + [ch]:
            if not k:
                continue
            if k in name or (rel and f"/{k}/" in f"/{rel}/"):
                score = len(k) + (100 if ("章" in k or re.fullmatch(r"\d+\.\d+", k)) else 0)
                if score > best_score:
                    best, best_score = ch, score
    return best


def rule_matches(rule, name, ext, rel):
    locs = rule.get("locations") or ["**"]
    if not any(fnmatch.fnmatch(rel, l) or fnmatch.fnmatch(name, l) for l in locs):
        return False
    f = rule.get("filter") or {}
    exts = [str(x).lower() for x in (f.get("ext") or [])]
    if exts and ext not in exts:
        return False
    nm = f.get("name")
    if nm and not re.search(nm, name):
        return False
    nn = f.get("not_name")
    if nn and re.search(nn, name):
        return False
    return True


def classify(name, rel, config):
    rules = config.get("rules") or []
    chapters = config.get("chapters") or {}
    ext = os.path.splitext(name)[1].lower()
    for rule in rules:
        if not rule_matches(rule, name, ext, rel):
            continue
        action = rule.get("action") or {}
        target = action.get("target")
        if not target:
            continue
        target = str(target).replace("{chapter}", chapter_of(name, chapters, rel) or "")
        if ext == ".md" and action.get("md_to"):
            target = target.rstrip("/") + "/" + str(action["md_to"]).strip("/")
        target = target.strip("/")
        full = f"{target}/{name}" if target else name
        return {"target": full, "rule": rule.get("id", "?"), "reason": "命中规则",
                "confidence": "high", "severity": rule.get("severity", "warn")}
    return None


def scan(workspace, config):
    general = config.get("general") or {}
    extra = list(general.get("skip") or [])
    inbox = str(general.get("inbox", "99-待处理/收件箱")).strip("/")
    planned, unknown = [], []
    for full, rel in walk_files(workspace, extra):
        if structurally_ok(rel):
            continue
        info = classify(os.path.basename(rel), rel, config)
        if info is None:
            unknown.append(rel)
            continue
        if rel == info["target"].strip("/"):
            continue
        st = os.stat(full)
        planned.append({"source": rel, "target": info["target"].strip("/"),
                        "rule": info["rule"], "severity": info["severity"],
                        "size": st.st_size, "mtime": int(st.st_mtime)})
    grouped = {}
    for item in planned:
        grouped.setdefault(item["target"], []).append(item)
    moves, conflicts = [], []
    for target, items in grouped.items():
        if len(items) > 1:
            for it in items:
                conflicts.append({**it, "reason": "本轮重复目标"})
            continue
        it = items[0]
        if os.path.exists(os.path.join(workspace, target)):
            conflicts.append({**it, "reason": "目标已存在"})
        else:
            moves.append(it)
    return {"workspace": workspace, "inbox": inbox, "moves": moves,
            "conflicts": conflicts, "unknown": unknown,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds")}


def render_md(result):
    out = ["# 整理核对报告", "",
           f"- 工作区：{result['workspace']}",
           f"- 时间：{result['generated_at']}",
           f"- 待移动：{len(result['moves'])}　冲突：{len(result['conflicts'])}　拿不准：{len(result['unknown'])}",
           ""]
    if result["moves"]:
        out.append("## 待移动")
        out += [f"- {m['source']} -> {m['target']}（规则 {m['rule']}）" for m in result["moves"]]
        out.append("")
    if result["conflicts"]:
        out.append("## 冲突（只报告，不搬）")
        out += [f"- {c['source']} -> {c['target']}（{c['reason']}）" for c in result["conflicts"]]
        out.append("")
    if result["unknown"]:
        out.append("## 拿不准（建议进收件箱）")
        out += [f"- {u}" for u in result["unknown"]]
        out.append("")
    return "\n".join(out)


def write_report(workspace, result):
    d = os.path.join(workspace, REPORTS_REL)
    os.makedirs(d, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(d, stamp)
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(render_md(result))
    files = sorted(x for x in os.listdir(d) if x[:1].isdigit())
    for old in files[:max(0, len(files) - KEEP_REPORTS * 2)]:
        os.remove(os.path.join(d, old))
    return base + ".json"


def cmd_plan(args, config):
    general = config.get("general") or {}
    inbox = str(general.get("inbox", "99-待处理/收件箱")).strip("/")
    name = args.name
    rel = (args.dir.replace(os.sep, "/").strip("/") + "/" + name) if args.dir else name
    info = classify(name, rel, config)
    if info is None:
        print(f"目标：{inbox}/{name}")
        print("规则：无（拿不准）")
        print("把握度：低")
        print("理由：没有命中的规则，建议进收件箱")
        return 0
    print(f"目标：{info['target']}")
    print(f"规则：{info['rule']}")
    print(f"把握度：{info['confidence']}")
    print(f"理由：{info['reason']}")
    return 0


def cmd_check(args, config):
    result = scan(args.workspace, config)
    print(f"工作区：{args.workspace}")
    print(f"待移动：{len(result['moves'])}　冲突：{len(result['conflicts'])}　拿不准：{len(result['unknown'])}")
    for m in result["moves"][:20]:
        print(f"  移动: {m['source']} -> {m['target']}")
    if len(result["moves"]) > 20:
        print(f"  …… 还有 {len(result['moves']) - 20} 条")
    for c in result["conflicts"]:
        print(f"  冲突: {c['source']} -> {c['target']}（{c['reason']}）")
    for u in result["unknown"][:20]:
        print(f"  拿不准: {u}")
    if not args.no_report:
        print(f"报告：{write_report(args.workspace, result)}")
    has_error = any(x.get("severity") == "error" for x in result["moves"] + result["conflicts"])
    return 3 if has_error else 0


def cmd_apply(args, config):
    workspace = args.workspace
    lock = os.path.join(workspace, LOCK_REL)
    if os.path.exists(lock):
        eprint(f"错误：已有搬运锁：{lock}（可能有另一个会话在搬，或上次异常退出）")
        return 2
    if args.dry_run:
        result = scan(workspace, config)
        print(f"演习：准备搬 {len(result['moves'])} 个，冲突 {len(result['conflicts'])} 个（未改动任何文件）")
        for m in result["moves"]:
            print(f"  将会移动: {m['source']} -> {m['target']}")
        return 0
    if not args.from_report:
        eprint("错误：apply 需要 --dry-run 或 --from-report <报告.json>")
        return 2
    try:
        with open(args.from_report, encoding="utf-8") as f:
            result = json.load(f)
    except Exception as ex:
        eprint(f"错误：报告无法读取：{args.from_report}：{ex}")
        return 2
    moves = result.get("moves") or []
    for m in moves:
        src = os.path.join(workspace, m["source"])
        dst = os.path.join(workspace, m["target"])
        if not os.path.isfile(src):
            eprint(f"错误：报告过期，源文件不存在：{m['source']}")
            return 2
        if os.path.exists(dst):
            eprint(f"错误：报告过期，目标已存在：{m['target']}")
            return 2
        st = os.stat(src)
        if st.st_size != m.get("size") or int(st.st_mtime) != m.get("mtime"):
            eprint(f"错误：报告过期，文件已变化：{m['source']}")
            return 2
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    jdir = os.path.join(workspace, JOURNAL_REL)
    os.makedirs(jdir, exist_ok=True)
    journal = os.path.join(jdir, dt.datetime.now().strftime("%Y%m%d") + ".jsonl")
    done = []
    try:
        for m in moves:
            src = os.path.join(workspace, m["source"])
            dst = os.path.join(workspace, m["target"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            rec = {**m, "time": dt.datetime.now().isoformat(timespec="seconds"), "ok": True}
            done.append(rec)
            with open(journal, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  已移动: {m['source']} -> {m['target']}")
        if args.prune_empty:
            for dirpath, _dirnames, _filenames in os.walk(workspace, topdown=False):
                if dirpath == workspace or "/.organize" in dirpath:
                    continue
                try:
                    if not os.listdir(dirpath):
                        os.rmdir(dirpath)
                        print(f"  已删除空目录: {os.path.relpath(dirpath, workspace)}")
                except OSError:
                    pass
        with open(os.path.join(jdir, "last.json"), "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False, indent=2)
    finally:
        if os.path.exists(lock):
            os.remove(lock)
    print(f"整理完成：移动 {len(done)} 个")
    return 0


def cmd_undo(args, config):
    workspace = args.workspace
    last = os.path.join(workspace, JOURNAL_REL, "last.json")
    if not os.path.isfile(last):
        eprint("错误：没有可撤回的记录（找不到 last.json）")
        return 2
    with open(last, encoding="utf-8") as f:
        records = json.load(f)
    for r in records:
        dst = os.path.join(workspace, r["target"])
        src = os.path.join(workspace, r["source"])
        if not os.path.isfile(dst):
            eprint(f"错误：目标不存在，无法撤回：{r['target']}")
            return 2
        if os.path.exists(src):
            eprint(f"错误：原位置已被占用，无法撤回：{r['source']}")
            return 2
    for r in reversed(records):
        shutil.move(os.path.join(workspace, r["target"]), os.path.join(workspace, r["source"]))
        print(f"  已撤回: {r['target']} -> {r['source']}")
    os.remove(last)
    return 0


def cmd_archive(args, config):
    workspace = args.workspace
    d = os.path.abspath(os.path.join(workspace, args.dir))
    if not d.startswith(os.path.abspath(workspace) + os.sep) or not os.path.isdir(d):
        eprint(f"错误：目录不存在或不在工作区内：{args.dir}")
        return 2
    text = f"归档原因：{args.reason}\n归档日期：{dt.date.today().isoformat()}\n"
    with open(os.path.join(d, ".archived"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"已归档标记：{os.path.relpath(os.path.join(d, '.archived'), workspace)}")
    return 0


def cmd_selftest(args, config):
    general = config.get("general") or {}
    inbox = str(general.get("inbox", "99-待处理/收件箱")).strip("/")
    ok = fail = 0
    for rule in config.get("rules") or []:
        for ex in rule.get("examples") or []:
            fn = str(ex.get("file", ""))
            expected = str(ex.get("to", "")).strip("/")
            info = classify(os.path.basename(fn), fn, config)
            actual = (os.path.dirname(info["target"]) if info else inbox).strip("/")
            if actual == expected:
                ok += 1
            else:
                fail += 1
                print(f"FAIL [{rule.get('id')}] {fn}：期望 {expected}，实际 {actual}")
    print(f"selftest：通过 {ok}，失败 {fail}")
    return 1 if fail else 0


def cmd_validate(args, entries):
    print(f"注册表条目数：{len(entries)}")
    for e in entries:
        print(f"- {e.get('name')}：kind={e.get('kind')} enabled={e.get('enabled')} path={e.get('path')}")
    if args.workspace:
        path, entry = admit(entries, args.workspace)
        print(f"准入：通过（{path}，kind={entry.get('kind')}）")
    return 0


def cmd_dsh_official(args, config):
    general = config.get("general") or {}
    extra = list(general.get("skip") or [])
    missing = []
    for n in OFFICIAL_DSH_NAMES:
        covered = (n.startswith(".") or n in SKIP_DIR_NAMES or n in SKIP_FILE_NAMES
                   or n.endswith(SKIP_DIR_SUFFIXES) or n.endswith(SKIP_FILE_SUFFIXES)
                   or any(fnmatch.fnmatch(n, p) for p in extra))
        if not covered:
            missing.append(n)
    print(f"DSH 官方名 {len(OFFICIAL_DSH_NAMES)} 个，已覆盖 {len(OFFICIAL_DSH_NAMES) - len(missing)} 个")
    if missing:
        print("需补：" + "、".join(missing))
        return 1
    print("跳过清单已覆盖全部官方名。")
    return 0


def add_common(sp):
    sp.add_argument("--workspace")
    sp.add_argument("--registry", default=DEFAULT_REGISTRY)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    subs = {"plan", "check", "apply", "undo", "archive", "selftest", "validate", "dsh-official"}
    if argv and argv[0] not in subs:
        if "--check" in argv:
            argv = ["check"] + [a for a in argv if a != "--check"]
        elif "--apply" in argv:
            argv = ["apply"] + [a for a in argv if a != "--apply"]
    parser = argparse.ArgumentParser(description="工作文件自动整理引擎 v2")
    common = argparse.ArgumentParser(add_help=False)
    add_common(common)
    sub = parser.add_subparsers(dest="cmd")
    sp = sub.add_parser("plan", parents=[common]); sp.add_argument("--name", required=True); sp.add_argument("--dir", default="")
    sc = sub.add_parser("check", parents=[common]); sc.add_argument("--no-report", action="store_true")
    sa = sub.add_parser("apply", parents=[common])
    sa.add_argument("--dry-run", action="store_true"); sa.add_argument("--from-report", default="")
    sa.add_argument("--prune-empty", action="store_true")
    sub.add_parser("undo", parents=[common])
    sr = sub.add_parser("archive", parents=[common]); sr.add_argument("dir"); sr.add_argument("--reason", default="未说明")
    sub.add_parser("selftest", parents=[common])
    sub.add_parser("validate", parents=[common])
    sub.add_parser("dsh-official", parents=[common])
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 2
    entries = load_registry(args.registry)
    if args.cmd == "validate":
        return cmd_validate(args, entries)
    if args.cmd == "dsh-official":
        ws = args.workspace or next((e.get("path") for e in entries
                                     if e.get("kind") == "documents" and e.get("enabled")), None)
        config = load_rules(admit(entries, ws)[0])
        return cmd_dsh_official(args, config)
    workspace, _entry = admit(entries, args.workspace)
    args.workspace = workspace
    config = load_rules(workspace)
    if args.cmd == "plan":
        return cmd_plan(args, config)
    if args.cmd == "check":
        return cmd_check(args, config)
    if args.cmd == "apply":
        return cmd_apply(args, config)
    if args.cmd == "undo":
        return cmd_undo(args, config)
    if args.cmd == "archive":
        return cmd_archive(args, config)
    if args.cmd == "selftest":
        return cmd_selftest(args, config)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
