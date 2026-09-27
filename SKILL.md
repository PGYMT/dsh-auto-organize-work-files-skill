---
name: auto-organize-work-files
description: Use when writing, moving, renaming or deleting any file inside an enabled document workspace (currently only 工作文件), and after any change in that workspace. Ask the target path before writing and verify after writing; run the rule lint after changing rules or another skill's output file names; keep the shared checklist in sync with its backup. Never operates on code repositories, $DSH_HOME, or unregistered workspaces.
---

# 工作文件自动整理（v4 · 流程版）

## 适用范围

- 本技能支持多工作区：每个工作区自带 .organize/rules.toml 与 AGENTS.md，互不影响。
- 哪些工作区启用，由 ~/.dsh/storages/auto-organize/registry.toml 决定（kind = documents 且 enabled = true）。
- 当前只启用「工作文件」一个工作区；其他工作区、代码仓库（含 .git）、DSH 运行数据（$DSH_HOME）一律不操作，先拒绝并说明。
- 所有命令必须带 --workspace，且该路径必须在注册表内；报告必须写明工作区路径。

## 去向铁律（plan 的判断顺序）

1. **本次显式声明** `--dest "<目标目录>"`：生产方自己说清去处，优先级最高；声明不合法就报错并退回规则。
2. **有主之树**：文件已在 `[owned]` 或内置豁免目录里，就地不动。
3. **名称规则**：按 rules.toml 匹配。
4. **兜底**：进 99-待处理/收件箱/。

plan 与 check 走同一套判断，不存在“一边说合法、一边说要搬走”。

## 五个动作

1. 写文件前先问路（plan），按它给的路径写；拿不准的进 99-待处理/收件箱/。
2. 写完核对（check），出现“放错”当轮改正。
3. 要搬文件，先把核对结果给人看，人同意后才搬（apply）；搬了有日志、可 undo。
4. 要归档或免打扰一个目录，用 archive 盖 .archived，或放 .organize-ignore；不要靠改文件夹名。
5. 改了规则、或别处流程改了产出文件名，跑 lint 体检；联动清单用 sync_checklist.py 比对。

## 命令

问路（可选带显式声明）：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py plan --name "<文件名>" --dest "<目标目录>" --workspace "<工作区>"

核对：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py check --workspace "<工作区>"

规则体检（样本语料，查误判/争抢/拿不准）：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py lint --workspace "<工作区>"

演习搬运：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py apply --dry-run --workspace "<工作区>"

按报告搬运（需人工确认后）：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py apply --from-report "<报告.json>" --workspace "<工作区>"

撤回：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py undo --workspace "<工作区>"

自检与准入：

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py selftest --workspace "<工作区>"

    python3 ~/.dsh/skills/auto-organize-work-files/scripts/organize.py validate --workspace "<工作区>"

样本语料在 <工作区>/.organize/samples.toml；规则新增或产出文件名变化时同步补一条。

## 联动清单（与教案技能共用）

- 权威：references/联动判断清单.md（本技能仓库）。
- 备份：教案技能的 references/联动判断清单.local.md。
- 比对：scripts/sync_checklist.py，改任一边之前和之后各跑一次。
- 四种结果：全同直接用；只差条目自动整合；同编号正文不同就停下报人；权威读不到用备份。

## 技能文件与运行位置

- 权威源：独立仓库的本地克隆 /root/skill-repos/auto-organize。
- 运行入口：~/.dsh/skills/auto-organize-work-files，是指向权威源的软链接。
- 只改权威源；运行入口由 scripts/skill_link.py 维护，不直接编辑。
- 自包含备份：scripts/skill_link.py backup 导出到 /root/skill-backups/。

## 禁止

- 不删除任何文件；不覆盖同名文件（冲突只报告）。
- 不整理未登记的工作区、代码仓库、$DSH_HOME。
- 不绕过准入检查。

## 变更记录

| 版本 | 日期 | 改动摘要 |
|---|---|---|
| v4 | 2026-09-27 | 统一 resolve（显式声明 > 有主之树 > 名称规则 > 收件箱）；plan 新增 --dest；规则新增 exclude 与 [owned]；新增 lint 与样本语料；新增联动判断清单、sync_checklist.py、skill_link.py；权威源改为独立仓库 + 软链 |
| v3 | — | 流程版：plan / check / apply / undo / archive / selftest / validate |
