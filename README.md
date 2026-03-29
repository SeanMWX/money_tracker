# money_tracker

This repository is an OpenClaw root skill for local bookkeeping with SQLite.
The repository root itself is the skill root.

## Structure

```text
.
|-- SKILL.md
|-- references/
|   |-- commands.md
|   `-- chat_reference.md
|-- scripts/
|   `-- bookkeeping.py
|-- test/
|   |-- README.md
|   |-- run_cli_tests.py
|   |-- run_smoke.py
|   |-- setup.ps1
|   `-- test_bookkeeping_cli.py
`-- skill-creator/
```

- `SKILL.md`: frontmatter and agent instructions.
- `references/`: reference material the agent can load on demand.
- `scripts/bookkeeping.py`: the bundled runtime used to read and write bookkeeping data.
- `test/`: local-only verification scripts for the SQLite helper and CLI behavior.
- `skill-creator/`: local helper content for creating or validating skills; not part of the delivered runtime.

## What The Skill Does

- Records expenses and income from Chinese natural-language prompts
- Manages user-defined categories
- Supports wallet-style accounts such as Alipay, WeChat, bank cards, and custom wallets with explicit currencies
- Shows wallet balances and grouped currency totals such as total CNY, total USD, and total EUR
- Supports adding, updating, and deleting wallet definitions
- Tracks recurring transactions as a schedule table for periodic payments or income
- Answers daily, weekly, monthly, and yearly totals, category breakdowns, period details, recent transactions, and latest-entry queries
- Supports updating and deleting saved entries

## Runtime

- Python `3.9+`
- Python standard library only
- Default database path: `~/.money_tracker/bookkeeping.db`
- Preferred env override: `MONEY_TRACKER_DB`
- Legacy env override supported: `LOCAL_BOOKKEEPING_DB`
- Recommended script path inside OpenClaw: `python "{baseDir}/scripts/bookkeeping.py" ...`

## Install In OpenClaw

OpenClaw loads skills from skill directories. To install this skill manually:

1. Place this folder under an OpenClaw skill location, preferably `<workspace>/skills/money_tracker/`.
2. Start a new session or restart the gateway so the skill is reloaded.
3. Verify that OpenClaw sees it with `openclaw skills list`.

## Example Triggers

- `记账 我喝奶茶用了10元`
- `用支付宝记一笔午饭 25 元`
- `用银行卡美元记一笔订阅 12`
- `把分类设置为日常、学习、电器`
- `列出所有账户`
- `显示所有账户余额`
- `我现在还有多少美元`
- `把 Wise:USD 改成 TravelCard:EUR`
- `添加周期性支出 每月 1 号交房租 3000 用银行卡`
- `显示这周花了多少`
- `显示我这个月的账单是多少`
- `展示出最新的10个账单`
- `修改一笔账 1 金额为12元，分类为学习`
- `删除最近的一笔账`

## Notes

- The skill is intended for agent use, so the main behavior contract lives in `SKILL.md`.
- `references/` exists to keep `SKILL.md` lean and provide detailed command shapes only when needed.
- `test/` and `skill-creator/` are local maintenance helpers and are not part of the uploaded OpenClaw runtime payload.
