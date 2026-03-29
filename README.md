# local-bookkeeping

This repository is a single OpenClaw skill for local bookkeeping with SQLite.
The repository root is the skill root.

## Structure

```text
.
├── SKILL.md
├── references/
│   ├── commands.md
│   └── chat-reference.md
└── scripts/
    └── bookkeeping.py
```

- `SKILL.md`: frontmatter and agent instructions.
- `references/`: reference material the agent can load on demand.
- `scripts/bookkeeping.py`: the bundled runtime used to read and write bookkeeping data.

## What The Skill Does

- Records expenses and income from Chinese natural-language prompts
- Manages user-defined categories
- Answers monthly totals, category breakdowns, monthly details, recent transactions, and latest-entry queries
- Supports updating and deleting saved entries

## Runtime

- Python `3.9+`
- Python standard library only
- Default database path: `~/.local-bookkeeping/bookkeeping.db`
- Recommended script path inside OpenClaw: `python "{baseDir}/scripts/bookkeeping.py" ...`

## Install In OpenClaw

OpenClaw loads skills from skill directories. To install this skill manually:

1. Place this folder under an OpenClaw skill location, preferably `<workspace>/skills/local-bookkeeping/`.
2. Start a new session or restart the gateway so the skill is reloaded.
3. Verify that OpenClaw sees it with `openclaw skills list`.

## Example Triggers

- `记账 我喝奶茶用了10元`
- `把分类设置为日常、学习、电器`
- `显示我这个月的账单是多少`
- `展示出最新的10个账单`
- `修改一笔账 1 金额为12元，分类为学习`
- `删除最近的一笔账`

## Notes

- The skill is intended for agent use, so the main behavior contract lives in `SKILL.md`.
- `references/` exists to keep `SKILL.md` lean and provide detailed command shapes only when needed.
