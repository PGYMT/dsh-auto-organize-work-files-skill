# dsh-auto-organize-work-files-skill

`工作文件` 工作区的自动整理 Skill（v2，2026-09-27 重写）。

核心变化：**规则不再写死在脚本里**，改由工作区自己的 `.organize/rules.toml` 决定；脚本默认**只核对、不搬运**；归档/免打扰靠标记文件；拿不准的进收件箱。

## 四个动作

1. 写文件前先问路（plan），按算出的路径写；拿不准的进 `99-待处理/收件箱/`。
2. 写完核对（check），出现“放错”当轮改正。
3. 要搬文件，先把核对结果给人看，人同意后才搬（apply）；搬了有日志、可 undo。
4. 要归档或免打扰一个目录，盖 `.archived` 或放 `.organize-ignore` 标记。

## 适用范围（多工作区）

- 哪些工作区启用，由 `~/.dsh/storages/auto-organize/registry.toml` 决定（`kind = documents` 且 `enabled = true`）。
- 代码仓库（含 `.git`）、DSH 运行数据（`$DSH_HOME`）、未登记的工作区一律拒绝。
- 每个工作区各有一份 `.organize/rules.toml` 和 `AGENTS.md`，互不影响。

## 命令

问路：

    python3 scripts/organize.py plan --name "<文件名>" --workspace "<工作区>"

核对：

    python3 scripts/organize.py check --workspace "<工作区>"

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

## 目录结构

```text
.
├── SKILL.md                  # Skill 主文件（流程版）
├── scripts/
│   ├── organize.py           # 引擎（v2）
│   └── rules.example.toml    # 新工作区规则模板
└── README.md                 # 本说明
```

## 安全边界

- 不删除任何文件；不覆盖同名文件（冲突只报告）。
- 一次只处理一个工作区；目标路径必须落在该工作区内。
- 跳过清单（遍历阶段生效）：以 `.` 开头的目录/文件、`node_modules`、`__pycache__`、`vendor`、`*.dist-info`、`*.libs`、`*.pyc`、`*.tmp`、符号链接，以及 `AGENTS.md`/`CLAUDE.md` 等 DSH 说明文件。
- `apply` 默认关闭，必须显式调用并按报告点名搬运。
