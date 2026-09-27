# dsh-auto-organize-work-files-skill

`工作文件` 工作区的自动整理 Skill（v4，2026-09-27）。

规则不写死在脚本里，由工作区自己的 `.organize/rules.toml` 决定；脚本默认**只核对、不搬运**；归档/免打扰靠标记文件；拿不准的进收件箱。

## 去向铁律（判断顺序）

1. **本次显式声明** `--dest "<目标目录>"`：生产方说清去处，优先级最高；声明不合法就报错并退回规则。
2. **有主之树**：`[owned]` 与内置三棵（`00-模板与规范`、`99-待处理`、`08-网络资源`）里的文件，就地不动。
3. **名称规则**：按 `rules.toml` 匹配。
4. **兜底**：进 `99-待处理/收件箱/`。

`plan` 与 `check` 走同一套判断，不会出现“一边说合法、一边说要搬”。

## 五个动作

1. 写文件前先问路（plan），按算出的路径写；拿不准的进 `99-待处理/收件箱/`。
2. 写完核对（check），出现“放错”当轮改正。
3. 要搬文件，先把核对结果给人看，人同意后才搬（apply）；搬了有日志、可 undo。
4. 要归档或免打扰一个目录，盖 `.archived` 或放 `.organize-ignore` 标记。
5. 改了规则、或别处流程改了产出文件名，跑 lint 体检；联动清单用 sync_checklist.py 比对。

## 适用范围（多工作区）

- 哪些工作区启用，由 `~/.dsh/storages/auto-organize/registry.toml` 决定（`kind = documents` 且 `enabled = true`）。
- 代码仓库（含 `.git`）、DSH 运行数据（`$DSH_HOME`）、未登记的工作区一律拒绝。
- 每个工作区各有一份 `.organize/rules.toml` 和 `AGENTS.md`，互不影响。
- 工作区可另建 `.organize/samples.toml` 作规则体检语料。

## 命令

问路（可选带显式声明）：

    python3 scripts/organize.py plan --name "<文件名>" --dest "<目标目录>" --workspace "<工作区>"

核对：

    python3 scripts/organize.py check --workspace "<工作区>"

规则体检（样本语料，查误判/争抢/拿不准）：

    python3 scripts/organize.py lint --workspace "<工作区>"

演习搬运：

    python3 scripts/organize.py apply --dry-run --workspace "<工作区>"

按报告搬运（人工确认后）：

    python3 scripts/organize.py apply --from-report "<报告.json>" --workspace "<工作区>"

撤回：

    python3 scripts/organize.py undo --workspace "<工作区>"

自检 / 准入 / DSH 官方名对照：

    python3 scripts/organize.py selftest --workspace "<工作区>"

    python3 scripts/organize.py validate --workspace "<工作区>"

    python3 scripts/organize.py dsh-official --workspace "<工作区>"

## 联动判断清单（与教案技能共用）

- 权威源：`references/联动判断清单.md`（本仓库）。
- 本地备份：教案技能的 `references/联动判断清单.local.md`，由 `scripts/sync_checklist.py` 生成，禁止手改。
- 比对：`python3 scripts/sync_checklist.py --apply`。全同或只差条目会整合；同编号正文不同＝冲突，停下报人；权威源读不到＝用本地备份。

## 权威源与运行入口

- 权威源：`/root/skill-repos/auto-organize`（本仓库的本地克隆），技能内容只在这里改。
- 运行入口：`~/.dsh/skills/auto-organize-work-files`，是指向权威源的软链接。
- 维护：`python3 scripts/skill_link.py link|verify|backup|restore`（`--only <技能名>` 可只处理一个）。

## 目录结构

```text
.
├── SKILL.md                  # Skill 主文件（流程版 v4）
├── references/
│   └── 联动判断清单.md        # 与教案技能共用的权威清单
├── scripts/
│   ├── organize.py           # 引擎（v4）
│   ├── rules.example.toml    # 新工作区规则模板
│   ├── sync_checklist.py     # 联动清单比对与整合
│   └── skill_link.py         # 软链维护与自包含备份
└── README.md                 # 本说明
```

## 安全边界

- 不删除任何文件；不覆盖同名文件（冲突只报告）。
- 一次只处理一个工作区；目标路径必须落在该工作区内。
- 跳过清单（遍历阶段生效）：以 `.` 开头的目录/文件、`node_modules`、`__pycache__`、`vendor`、`*.dist-info`、`*.libs`、`*.pyc`、`*.tmp`、符号链接，以及 `AGENTS.md`/`CLAUDE.md` 等 DSH 说明文件。
- `apply` 默认关闭，必须显式调用并按报告点名搬运。
