# money_tracker

This repository is an OpenClaw root skill for local bookkeeping with SQLite.
The repository root itself is the skill root.

## Structure

```text
.
|-- README.md
|-- SKILL.md
|-- references/
|   |-- commands.md
|   |-- chat_reference.md
|   `-- intent_mapping.md
|-- scripts/
|   `-- bookkeeping.py
`-- test/
    |-- README.md
    |-- run_cli_tests.py
    |-- run_smoke.py
    |-- setup.ps1
    `-- test_bookkeeping_cli.py
```

- `SKILL.md`: frontmatter plus the main agent behavior contract.
- `references/`: secondary reference material loaded on demand.
- `scripts/bookkeeping.py`: the bundled runtime required by the skill.
- `test/`: local-only verification scripts for the SQLite helper and CLI behavior.

Optional local helper directories such as `skill-creator/` may exist during maintenance, but they are not part of the delivered runtime payload.

## Current Scope

- Record expense and income entries from Chinese bookkeeping requests
- Manage user-defined categories
- Manage wallet-style accounts in `wallet:currency` form such as `支付宝:CNY`, `银行卡:USD`, or `Wise:EUR`
- Show per-wallet balances and grouped totals by currency
- Add, update, deactivate, and list recurring transaction schedules
- Query day, week, month, and year reports plus transaction details
- Query recent transactions and the latest saved entry
- Update or delete saved entries

## Runtime

- Python `3.9+`
- Python standard library only
- Default database path: `~/.money_tracker/bookkeeping.db`
- Preferred env override: `MONEY_TRACKER_DB`
- Legacy env override supported: `LOCAL_BOOKKEEPING_DB`
- Recommended script path inside OpenClaw: `python "{baseDir}/scripts/bookkeeping.py" ...`

## Important Semantics

- Use `account-balances` for current holdings by wallet and by currency.
- Wallet balances are grouped by saved wallet definitions such as `支付宝:CNY` or `银行卡:EUR`.
- Day, week, month, and year report commands do not perform FX conversion. If one period contains multiple currencies, the totals are raw stored amounts and must not be interpreted as converted totals.
- Recurring transactions are stored as schedules only. They do not automatically create normal transaction entries.

## Install In OpenClaw

OpenClaw loads skills from skill directories. To install this skill manually:

1. Place this folder under an OpenClaw skill location, preferably `<workspace>/skills/money_tracker/`.
2. Start a new session or restart the gateway so the skill is reloaded.
3. Verify that OpenClaw sees it with `openclaw skills list`.

## Prompt Coverage

Prompt examples and routing details are maintained in:

- `SKILL.md` for the main agent workflow
- `references/commands.md` for exact command shapes
- `references/chat_reference.md` for extra Chinese prompt examples
- `references/intent_mapping.md` for a concise user-intent to command mapping table

## Local Verification

From the repository root:

```powershell
pwsh -ExecutionPolicy Bypass -File .\test\setup.ps1
.\test\.venv\Scripts\python.exe .\test\run_smoke.py
.\test\.venv\Scripts\python.exe .\test\run_cli_tests.py
```

## Notes

- The skill is intended for agent use, so the main behavior contract lives in `SKILL.md`.
- `references/` keeps `SKILL.md` lean and avoids repeating command syntax in multiple places.
- `test/` is for local verification and is not part of the uploaded OpenClaw runtime payload.
