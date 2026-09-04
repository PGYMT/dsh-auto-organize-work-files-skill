#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作文件工作区自动整理脚本。

安全性：
- 只处理显式指定的“工作文件”工作区，默认允许路径为 /root/dsh-workspace/工作文件。
- --check 只输出操作清单，不移动文件；--apply 才执行移动。
- 不删除文件，不覆盖同名文件。
- 忽略 README.md、隐藏目录、.dsh、.git 及 00-模板与规范、99-待处理 等受保护区域。
"""

import argparse
import datetime
import os
import re
import shutil
import sys

DEFAULT_WORKSPACE = "/root/dsh-workspace/工作文件"
WORKSPACE_BASENAME = "工作文件"

# 已知顶层目录（用于校验工作区身份）
KNOWN_TOP_DIRS = [
    "00-模板与规范",
    "01-教学计划",
    "02-培优辅潜",
    "03-成绩",
    "04-教案",
    "05-课件与文本",
    "06-工具与提示词",
    "07-培训研修",
    "99-待处理",
]

CHAPTERS = [
    "第十三章-内能",
    "第十四章-内能的利用",
    "第十五章-电流和电路",
]


def chapter_hint(name: str, rel_path: str) -> str | None:
    """根据文件名中的章节关键词，或当前路径中已有的章节目录推断章节。"""
    low = name
    if any(k in low for k in ["13.1", "13.2", "13.3", "第十三章", "内能", "热量", "比热容", "分子动理论"]):
        return "第十三章-内能"
    if any(k in low for k in ["14.1", "14.2", "14.3", "14.4", "第十四章", "内能的利用", "热机"]):
        return "第十四章-内能的利用"
    if any(k in low for k in ["15.1", "15.2", "15.3", "15.4", "15.5", "第十五章", "电流", "电路", "串联", "并联"]):
        return "第十五章-电流和电路"
    for ch in CHAPTERS:
        if f"/{ch}/" in f"/{rel_path}":
            return ch
    return None


def category_of(name: str, ext: str):
    """返回 (大类, 子类)；子类用于进一步决定 md/docx 落位。"""
    if ext == ".xlsx" or ext == ".csv":
        return ("03-成绩", "raw")
    if ext == ".enbx":
        return ("05-课件与文本", "courseware")
    if "成绩分析" in name or "质量分析" in name or "分析报告" in name:
        return ("03-成绩", "analysis")
    if "教学计划" in name or "实验教学开课" in name or "实验教学计划" in name or "进度安排" in name:
        return ("01-教学计划", "plan")
    if "培优辅潜" in name:
        return ("02-培优辅潜", "plan")
    if "成绩单" in name or "成绩表" in name or "期末成绩" in name or "考试" in name:
        return ("03-成绩", "raw")
    if "教案" in name or "课时分配" in name or "大单元整合复习" in name:
        return ("04-教案", "lesson")
    if "课件文本" in name or "白板文本" in name or "教学内容提取" in name or ("第1节" in name or "第2节" in name or "第3节" in name or "第4节" in name or "第5节" in name):
        return ("05-课件与文本", "course_text")
    if "提示词" in name or "prompt" in name.lower():
        return ("06-工具与提示词", "prompt")
    if "DeepSeek" in name or "WSL" in name or "OpenViking服务" in name or "教程" in name or "安装" in name:
        return ("06-工具与提示词", "tutorial")
    if any(k in name for k in ["师德", "培训", "学习文件", "心得", "体会", "家庭教育", "未成年人", "教师职业"]):
        return ("07-培训研修", "training")
    return (None, None)


def target_for(rel_path: str):
    """为不在正确位置的文件计算目标相对路径；无法判断时返回 99-待处理。"""
    parts = rel_path.split("/")
    name = parts[-1]
    ext = os.path.splitext(name)[1].lower()

    # 历史版本
    if ext in (".bak", ".md") and "历史版本" in rel_path:
        return f"06-工具与提示词/提示词/历史版本/md文件/{name}"

    # 旧版 .doc：按内容归入 00 模板或 07 培训，否则待处理
    if ext == ".doc":
        if "实验教学计划" in name:
            return f"00-模板与规范/{name}"
        if any(k in name for k in ["师德", "培训", "学习文件", "未成年人", "教师职业"]):
            return f"07-培训研修/学习文件/{name}"
        return f"99-待处理/{name}"

    target_category, sub = category_of(name, ext)
    if target_category is None:
        return f"99-待处理/{name}"

    ch = chapter_hint(name, rel_path)

    if ext == ".md":
        if sub == "analysis":
            return f"03-成绩/分析/md文件/{name}"
        if sub == "lesson":
            if ch:
                return f"04-教案/{ch}/md文件/{name}"
            return f"04-教案/md文件/{name}"
        if sub == "course_text":
            if ch:
                return f"05-课件与文本/{ch}/课件文本/md文件/{name}"
            return f"05-课件与文本/课件文本/md文件/{name}"
        if sub == "tutorial":
            return f"06-工具与提示词/教程/md文件/{name}"
        if sub == "prompt":
            return f"06-工具与提示词/提示词/md文件/{name}"
        if sub == "training":
            if "心得" in name or "体会" in name:
                return f"07-培训研修/心得体会/md文件/{name}"
            return f"07-培训研修/学习文件/md文件/{name}"
        # 教学计划 / 培优 / 其他计划
        if target_category in ("01-教学计划", "02-培优辅潜"):
            return f"{target_category}/md文件/{name}"
        return f"{target_category}/md文件/{name}"

    if ext == ".txt":
        if "心得" in name or "体会" in name:
            return f"07-培训研修/心得体会/{name}"
        return f"99-待处理/{name}"

    # 非 md：docx/enbx/xlsx/其他交付
    if sub == "raw":
        return f"03-成绩/原始数据/{name}"
    if sub == "analysis":
        return f"03-成绩/分析/{name}"
    if sub == "lesson":
        if ch:
            return f"04-教案/{ch}/{name}"
        return f"04-教案/{name}"
    if sub == "courseware":
        if ch:
            return f"05-课件与文本/{ch}/原始课件/{name}"
        return f"05-课件与文本/原始课件/{name}"
    if sub == "course_text":
        if ch:
            return f"05-课件与文本/{ch}/课件文本/{name}"
        return f"05-课件与文本/课件文本/{name}"
    if sub == "tutorial":
        return f"06-工具与提示词/教程/{name}"
    if sub == "prompt":
        return f"06-工具与提示词/提示词/{name}"
    if sub == "training":
        if "心得" in name or "体会" in name:
            return f"07-培训研修/心得体会/{name}"
        return f"07-培训研修/学习文件/{name}"
    return f"99-待处理/{name}"


def is_correct(rel_path: str) -> bool:
    """判断文件是否已经按规范处于正确位置。"""
    parts = rel_path.split("/")
    name = parts[-1]
    if name == "README.md":
        return True
    top = parts[0]
    if top.startswith("."):
        return True
    if top in ("00-模板与规范", "99-待处理"):
        return True

    ext = os.path.splitext(name)[1].lower()

    if top == "07-培训研修":
        return len(parts) >= 3 and parts[1] in ("学习文件", "心得体会")

    if top == "01-教学计划":
        if ext == ".md":
            return len(parts) >= 3 and parts[1] == "md文件"
        if ext in (".docx", ".doc"):
            return len(parts) == 2
        return False

    if top == "02-培优辅潜":
        if ext == ".md":
            return len(parts) >= 3 and parts[1] == "md文件"
        if ext == ".docx":
            return len(parts) == 2
        return False

    if top == "03-成绩":
        if ext in (".xlsx", ".csv"):
            return len(parts) >= 3 and parts[1] == "原始数据"
        if "分析" in name:
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
        if ext == ".enbx":
            return len(parts) >= 4 and parts[2] == "原始课件"
        if ext == ".md":
            return len(parts) >= 5 and parts[2] == "课件文本" and parts[3] == "md文件"
        return False

    if top == "06-工具与提示词":
        if "历史版本" in rel_path and ext in (".md", ".bak"):
            return len(parts) >= 5 and parts[2] == "历史版本" and parts[3] == "md文件"
        if len(parts) >= 2 and parts[1] == "教程":
            if ext == ".md":
                return len(parts) >= 4 and parts[2] == "md文件"
            if ext == ".docx":
                return len(parts) == 3
        if len(parts) >= 2 and parts[1] == "提示词":
            if ext == ".md":
                return len(parts) >= 4 and parts[2] == "md文件"
            if ext == ".docx":
                return len(parts) == 3
        return False

    return False


def validate_workspace(path: str) -> str:
    """校验工作区路径，确保不会误操作其他工作区。"""
    resolved = os.path.abspath(path)
    if not os.path.isdir(resolved):
        print(f"错误：工作区目录不存在：{resolved}", file=sys.stderr)
        sys.exit(1)
    if os.path.basename(resolved) != WORKSPACE_BASENAME:
        print(f"错误：仅允许操作名为“{WORKSPACE_BASENAME}”的工作区，当前路径为：{resolved}", file=sys.stderr)
        sys.exit(1)
    present = [d for d in KNOWN_TOP_DIRS if os.path.isdir(os.path.join(resolved, d))]
    if not present:
        print(f"错误：路径 {resolved} 不是符合规范的工作文件工作区（未找到已知顶层目录）", file=sys.stderr)
        sys.exit(1)
    return resolved


def iter_files(root: str):
    """遍历工作区文件，返回 (绝对路径, 相对路径)。"""
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # 跳过隐藏目录、.git/.dsh 等
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in (".git", ".dsh", "node_modules")
        ]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            yield full, rel


def main() -> int:
    parser = argparse.ArgumentParser(description="工作文件工作区自动整理脚本")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE, help="工作文件工作区路径")
    parser.add_argument("--check", action="store_true", help="仅检查，不移动")
    parser.add_argument("--apply", action="store_true", help="执行移动")
    args = parser.parse_args()

    if not args.check and not args.apply:
        print("请使用 --check 或 --apply。示例：organize.py --check --workspace /path/to/工作文件")
        return 2

    root = validate_workspace(args.workspace)

    moves = []      # (src_abs, dst_rel)
    conflicts = []  # (src_abs, dst_rel)

    for full, rel in iter_files(root):
        if is_correct(rel):
            continue
        dst_rel = target_for(rel)
        if dst_rel is None:
            continue
        if dst_rel == rel:
            continue
        dst_abs = os.path.join(root, dst_rel)
        if os.path.abspath(dst_abs) == os.path.abspath(full):
            continue
        if os.path.exists(dst_abs):
            conflicts.append((full, dst_rel))
        else:
            moves.append((full, dst_rel))

    if args.check:
        if not moves and not conflicts:
            print("无需整理：所有文件均已按规范归档。")
            return 0
        print(f"共发现 {len(moves)} 个待移动文件，{len(conflicts)} 个冲突文件。")
        for full, dst in moves:
            print(f"  移动: {os.path.relpath(full, root)} -> {dst}")
        for full, dst in conflicts:
            print(f"  冲突: {os.path.relpath(full, root)} -> {dst}（目标已存在，需人工处理）")
        return 0

    # apply
    moved_count = 0
    for full, dst_rel in moves:
        dst_abs = os.path.join(root, dst_rel)
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.move(full, dst_abs)
        moved_count += 1
        print(f"  已移动: {os.path.relpath(full, root)} -> {dst_rel}")

    conflict_count = 0
    for full, dst_rel in conflicts:
        name = os.path.basename(dst_rel)
        stem, ext = os.path.splitext(name)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        conflict_name = f"{stem}.冲突-{stamp}{ext}"
        dst_abs = os.path.join(root, "99-待处理", conflict_name)
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.move(full, dst_abs)
        conflict_count += 1
        print(f"  冲突已转存: {os.path.relpath(full, root)} -> 99-待处理/{conflict_name}")

    if moved_count == 0 and conflict_count == 0:
        print("无需整理：所有文件均已按规范归档。")
    else:
        print(f"整理完成：移动 {moved_count} 个，冲突转存 {conflict_count} 个。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
