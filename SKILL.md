---
name: auto-organize-work-files
description: Use when writing, moving, renaming or deleting any file inside an enabled document workspace (currently only 工作文件), and after any change in that workspace. Ask the target path before writing and verify after writing. Never operates on code repositories, $DSH_HOME, or unregistered workspaces.
---

# 工作文件自动整理（v3 · 流程版）

## 适用范围

- 本技能支持多工作区：每个工作区自带 .organize/rules.toml 与 AGENTS.md，互不影响。
- 哪些工作区启用，由 ~/.dsh/storages/auto-organize/registry.toml 决定（kind = documents 且 enabled = true）。
- 当前只启用「工作文件」一个工作区；其他工作区、代码仓库（含 .git）、DSH 运行数据（$DSH_HOME）一律不操作，先拒绝并说明。
- 所有命令必须带 --workspace，且该路径必须在注册表内；报告必须写明工作区路径。

## 四个动作

1. 写文件前先问路（plan），按它给的路径写；拿不准的进 99-待处理/收件箱/。
2. 写完核对（check），出现“放错”当轮改正。
3. 要搬文件，先把核对结果给人看，人同意后才搬（apply）；搬了有日志、可 undo。
4. 要归档或免打扰一个目录，用 archive 盖 .archived，或放 .organize-ignore；不要靠改文件夹名。

## 命令

问路：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py plan --name "<文件名>" --workspace "<工作区>"

核对：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py check --workspace "<工作区>"

演习搬运：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py apply --dry-run --workspace "<工作区>"

按报告搬运（需人工确认后）：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py apply --from-report "<报告.json>" --workspace "<工作区>"

撤回：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py undo --workspace "<工作区>"

自检与准入：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py selftest --workspace "<工作区>"

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py validate --workspace "<工作区>"

## 禁止

- 不删除任何文件；不覆盖同名文件（冲突只报告）。
- 不整理未登记的工作区、代码仓库、$DSH_HOME。
- 不绕过准入检查。
