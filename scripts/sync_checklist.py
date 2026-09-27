#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""联动判断清单的比对与整合。

权威源按优先级取：--url 的 GitHub 原始链接 → --authority 本地权威文件。
两者都读不到时打印“连不上”，直接用本地备份干活。

退出码：0 一致或已整合；1 有冲突（停下报人）；3 权威源读不到（用了备份）。
同编号正文不同＝冲突，默认停下；确认是权威源的正常更新后，用 --accept-authority 采用权威源。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import urllib.request
from urllib.parse import quote

ITEM_RE = re.compile(r"^-\s*\[([A-Za-z]+\d+)\]\s*(.*)$")
DEFAULT_AUTHORITY = "/root/skill-repos/auto-organize/references/联动判断清单.md"
DEFAULT_BACKUP = ("/root/skill-repos/g9-physics/references/联动判断清单.local.md")
DEFAULT_URL = quote("https://raw.githubusercontent.com/PGYMT/"
                    "dsh-auto-organize-work-files-skill/main/references/联动判断清单.md",
                    safe=":/")
RECORD_HEAD = "## 同步记录"


def eprint(*a):
    print(*a, file=sys.stderr)


def parse_items(text):
    """把清单正文解析成 {编号: 正文}。"""
    items = {}
    for line in text.splitlines():
        m = ITEM_RE.match(line.strip())
        if m:
            items[m.group(1)] = m.group(2).strip()
    return items


def fetch_url(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except Exception as ex:
        eprint(f"提示：链接读不到（{ex}）")
        return None


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as ex:
        eprint(f"提示：文件读不到（{ex}）")
        return None


def previous_records(text):
    if not text or RECORD_HEAD not in text:
        return []
    tail = text.split(RECORD_HEAD, 1)[1]
    return [ln for ln in tail.splitlines() if ln.strip().startswith("- ")]


def build_backup(authority_items, backup_only, source, same, diff, conflict, records):
    out = ["# 联动判断清单（本地备份）", "",
           "> 本文件由 scripts/sync_checklist.py 生成，禁止手改；要改去改权威源。",
           f"> 权威源：{source}",
           f"> 生成时间：{dt.datetime.now().isoformat(timespec='seconds')}",
           f"> 本次结果：相同 {same}　差别 {diff}　冲突 {conflict}", "",
           "## 检查项", ""]
    for key in sorted(authority_items):
        out.append(f"- [{key}] {authority_items[key]}")
    out += ["", "## 仅在本备份里（权威源没有）", ""]
    if backup_only:
        for key in sorted(backup_only):
            out.append(f"- [{key}] {backup_only[key]}")
    else:
        out.append("（无）")
    out += ["", RECORD_HEAD, ""]
    out += records or ["（暂无）"]
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="联动判断清单比对")
    ap.add_argument("--authority", default=DEFAULT_AUTHORITY)
    ap.add_argument("--backup", default=DEFAULT_BACKUP)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--no-url", action="store_true", help="不联网，只读本地权威源")
    ap.add_argument("--apply", action="store_true", help="把结果写回本地备份")
    ap.add_argument("--accept-authority", action="store_true",
                    help="同编号正文不同时，按权威源覆盖备份（人工确认后使用）")
    args = ap.parse_args(argv)

    backup_text = read_text(args.backup)
    if backup_text is None:
        # 首次生成时备份还不存在，按空清单处理，不是错误。
        backup_text = ""
    backup_items = parse_items(backup_text)
    records = previous_records(backup_text)

    authority_text, source = None, ""
    if not args.no_url:
        authority_text = fetch_url(args.url)
        source = args.url
    if authority_text is None:
        authority_text = read_text(args.authority)
        source = args.authority
    if authority_text is None:
        print("结论：连不上权威源，本次直接用本地备份。")
        print(f"备份条目：{len(backup_items)} 条（{args.backup}）")
        return 3

    authority_items = parse_items(authority_text)
    same = [k for k in authority_items if k in backup_items and authority_items[k] == backup_items[k]]
    conflict = [k for k in authority_items if k in backup_items and authority_items[k] != backup_items[k]]
    added = [k for k in authority_items if k not in backup_items]
    backup_only = {k: v for k, v in backup_items.items() if k not in authority_items}
    diff = len(added) + len(backup_only)

    print(f"权威源：{source}")
    print(f"条目：权威 {len(authority_items)}　备份 {len(backup_items)}")
    print(f"结果：相同 {len(same)}　差别 {diff}（权威新增 {len(added)}，仅备份 {len(backup_only)}）　冲突 {len(conflict)}")
    for k in added:
        print(f"  差别：权威新增 [{k}] {authority_items[k]}")
    for k, v in sorted(backup_only.items()):
        print(f"  差别：仅备份 [{k}] {v}")
    for k in conflict:
        print(f"  冲突：[{k}]")
        print(f"    权威：{authority_items[k]}")
        print(f"    备份：{backup_items[k]}")

    stamp = dt.datetime.now().isoformat(timespec="seconds")
    if conflict and not args.accept_authority:
        verdict = f"- {stamp} 冲突 {len(conflict)} 条，未自动整合（权威源 {source}）"
        records.append(verdict)
        print("结论：有冲突，停下等人工决定；未改动本地备份。")
        if args.apply:
            eprint("提示：有冲突时不写备份；确认是权威源的正常更新后，加 --accept-authority 重跑。")
        return 1
    if conflict:
        print(f"提示：{len(conflict)} 条同编号正文不同，已按 --accept-authority 采用权威源。")

    verdict = (f"- {stamp} 已整合（权威源 {source}；相同 {len(same)}，并入 {len(added)}，"
               f"更新 {len(conflict)}，仅备份保留 {len(backup_only)}）")
    print("结论：" + ("一致，无需改动。" if not diff and not conflict
                     else f"已整合（并入 {len(added)} 条，更新 {len(conflict)} 条）。"))
    if args.apply:
        records.append(verdict)
        text = build_backup(authority_items, backup_only, source,
                            len(same), diff, 0, records)
        os.makedirs(os.path.dirname(args.backup), exist_ok=True)
        with open(args.backup, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入本地备份：{args.backup}")
    else:
        print("（本次是干跑，加 --apply 才写回备份。）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
