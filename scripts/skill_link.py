#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能软链的建立、校验与备份。

运行入口是软链：~/.dsh/skills/<技能名> -> 权威源（独立仓库的本地克隆）。
本脚本只维护这条软链和自包含备份；技能内容一律在权威源里编辑。

命令：
  link     建立或修复软链（旧实体目录移到备份区，不删除）
  verify   校验软链、权威源与 SKILL.md 是否有效，并检查项目级同名副本
  backup   把权威源导出成自包含备份
  restore  从远端重新克隆缺失的权威源，再重建软链

退出码：0 正常；1 有需要处理的问题；2 用法或环境错误。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys

SKILLS = {
    "generate-9th-grade-physics-lesson-plan": {
        "repo": "/root/skill-repos/g9-physics",
        "remote": "https://github.com/PGYMT/dsh-grade9-physics-lesson-plan-skill.git",
    },
    "auto-organize-work-files": {
        "repo": "/root/skill-repos/auto-organize",
        "remote": "https://github.com/PGYMT/dsh-auto-organize-work-files-skill.git",
    },
}
DEFAULT_SKILLS_HOME = os.path.expanduser("~/.dsh/skills")
DEFAULT_BACKUP_DIR = "/root/skill-backups"
DEFAULT_SHADOW_ROOT = "/root/dsh-workspace"


def eprint(*a):
    print(*a, file=sys.stderr)


def skill_version(repo):
    """从权威源的 SKILL.md 取版本号，用于备份命名。"""
    path = os.path.join(repo, "SKILL.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "v0"
    m = re.search(r"^\s*version:\s*(\S+)", text, re.M)
    if m:
        return "v" + m.group(1).strip().lstrip("v")
    m = re.search(r"（v(\d+(?:\.\d+)*)", text)
    return "v" + m.group(1) if m else "v0"


def stamp():
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def project_roots(shadow_root):
    """把 shadow_root 本身和它的直接子目录都当作候选项目根。"""
    roots = [shadow_root]
    try:
        entries = sorted(os.scandir(shadow_root), key=lambda e: e.name)
    except OSError as ex:
        eprint(f"提示：无法列出 {shadow_root}（{ex}）")
        return roots
    roots += [e.path for e in entries if e.is_dir(follow_symlinks=False)]
    return roots


def shadow_problems(name, spec, shadow_root):
    """项目级同名副本会抢在用户级软链之前生效，必须为 0。"""
    found = []
    for root in project_roots(shadow_root):
        for sub in (".dsh/skills", ".agents/skills"):
            cand = os.path.join(root, sub, name)
            if not os.path.lexists(cand):
                continue
            if os.path.islink(cand):
                if os.path.realpath(cand) != os.path.realpath(spec["repo"]):
                    found.append((cand, f"软链指向别处 {os.path.realpath(cand)}"))
            else:
                found.append((cand, "实体副本会抢在用户级软链之前生效"))
    return found


def link_one(name, spec, skills_home, backup_dir):
    """为一个技能建立或修复软链；返回问题条数。"""
    repo = spec["repo"]
    link = os.path.join(skills_home, name)
    if not os.path.isdir(repo):
        print(f"[跳过] {name}：权威源不存在 {repo}")
        return 1
    if os.path.islink(link):
        if os.path.realpath(link) == os.path.realpath(repo):
            print(f"[已就位] {name} -> {repo}")
            return 0
        eprint(f"[冲突] {name}：软链指向别处 {os.path.realpath(link)}；未改动，请人工确认")
        return 1
    os.makedirs(skills_home, exist_ok=True)
    if os.path.exists(link):
        parked = os.path.join(backup_dir, f"{name}.prelink-{stamp()}")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.move(link, parked)
        print(f"[移开旧目录] {name} -> {parked}")
    os.symlink(repo, link)
    print(f"[已建软链] {link} -> {repo}")
    return 0


def verify(skills, skills_home, shadow_root=""):
    problems = 0
    for name, spec in sorted(skills.items()):
        link = os.path.join(skills_home, name)
        repo = spec["repo"]
        if shadow_root:
            for path, why in shadow_problems(name, spec, shadow_root):
                eprint(f"[FAIL] {name}：项目级副本 {path}（{why}）")
                problems += 1
        if not os.path.islink(link):
            eprint(f"[FAIL] {name}：运行入口不是软链（{link}）")
            problems += 1
            continue
        real = os.path.realpath(link)
        if real != os.path.realpath(repo):
            eprint(f"[FAIL] {name}：软链指向 {real}，期望 {repo}")
            problems += 1
            continue
        if not os.path.isfile(os.path.join(link, "SKILL.md")):
            eprint(f"[FAIL] {name}：软链有效但读不到 SKILL.md")
            problems += 1
            continue
        print(f"[OK] {name} -> {repo}（{skill_version(repo)}）")
    return problems


def backup(skills, backup_dir):
    problems = 0
    for name, spec in sorted(skills.items()):
        repo = spec["repo"]
        if not os.path.isdir(repo):
            eprint(f"[FAIL] {name}：权威源不存在 {repo}")
            problems += 1
            continue
        dest = os.path.join(backup_dir, f"{name}-{skill_version(repo)}-{dt.date.today().isoformat()}")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(repo, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        print(f"[已备份] {dest}")
    return problems


def restore(skills, skills_home, backup_dir):
    problems = 0
    for name, spec in sorted(skills.items()):
        repo, remote = spec["repo"], spec["remote"]
        if os.path.isdir(os.path.join(repo, ".git")):
            print(f"[拉取] {repo}")
            r = subprocess.run(["git", "-C", repo, "pull", "--ff-only"])
            if r.returncode != 0:
                eprint(f"[FAIL] {name}：git pull 失败")
                problems += 1
                continue
        else:
            os.makedirs(os.path.dirname(repo), exist_ok=True)
            print(f"[克隆] {remote} -> {repo}")
            r = subprocess.run(["git", "clone", remote, repo])
            if r.returncode != 0:
                eprint(f"[FAIL] {name}：git clone 失败")
                problems += 1
                continue
        problems += link_one(name, spec, skills_home, backup_dir)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="技能软链维护")
    ap.add_argument("cmd", choices=["link", "verify", "backup", "restore"])
    ap.add_argument("--skills-home", default=DEFAULT_SKILLS_HOME)
    ap.add_argument("--backup-dir", default=DEFAULT_BACKUP_DIR)
    ap.add_argument("--only", default="", help="只处理这些技能，逗号分隔；默认全部")
    ap.add_argument("--shadow-root", default=DEFAULT_SHADOW_ROOT,
                    help="检查项目级同名副本的根目录；传空字符串可跳过")
    args = ap.parse_args(argv)
    wanted = [x.strip() for x in args.only.split(",") if x.strip()]
    skills = {k: v for k, v in SKILLS.items() if not wanted or k in wanted}
    if not skills:
        eprint(f"错误：--only 没有匹配到任何技能：{args.only}")
        return 2
    if args.cmd == "link":
        os.makedirs(args.backup_dir, exist_ok=True)
        problems = sum(link_one(n, s, args.skills_home, args.backup_dir) for n, s in sorted(skills.items()))
    elif args.cmd == "verify":
        problems = verify(skills, args.skills_home, args.shadow_root)
    elif args.cmd == "backup":
        os.makedirs(args.backup_dir, exist_ok=True)
        problems = backup(skills, args.backup_dir)
    else:
        problems = restore(skills, args.skills_home, args.backup_dir)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
