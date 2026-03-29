---
name: money_tracker
description: 本地 SQLite 记账 skill。用于处理中文自然语言记账、查账、分类管理、账户管理、周期性交易管理、最近账单查询、修改账单和删除账单请求，例如“记账 我喝奶茶用了10元”“用支付宝记一笔午饭 25 元”“添加周期性支出 每月 1 号交房租 3000 用银行卡”“显示这周花了多少”“列出 2026-03-15 的账单”。支持用户预定义分类、账户选择、按日周月年统计、分类与账户占比分析、交易明细查询和账单维护。
---

# money_tracker

## Overview

Use this skill for local bookkeeping with a lightweight SQLite database.
Interpret the user's Chinese prompt, map it to a structured record or query, and use the bundled script to persist and analyze data.

## Runtime Rules

- Use `python` 3.9+ only. The bundled script uses only the standard library.
- Use UTF-8 and LF for all text inputs and outputs.
- Prefer the bundled script instead of writing ad-hoc SQL.
- Always reference bundled files via `{baseDir}` so the skill still works when installed under an OpenClaw `skills/` directory.
- The uploaded runtime only needs `{baseDir}/scripts/bookkeeping.py`.
- Use the default database path unless the user explicitly wants a custom location.
- Default database path: `~/.money_tracker/bookkeeping.db`
- Allow override with `--db` or the `MONEY_TRACKER_DB` environment variable.
- The bundled script also accepts the legacy `LOCAL_BOOKKEEPING_DB` environment variable and can fall back to the legacy `~/.local-bookkeeping/bookkeeping.db` path when needed.
- For extra Chinese prompt examples, load `{baseDir}/references/chat_reference.md` only when needed.

## Intent Routing

Route the user's request into one of these flows:

1. `记账 ...` or other natural-language add-entry requests
2. Category management such as setting, replacing, adding, listing, or deleting categories
3. Account management such as listing, enabling, resetting, or deleting accounts like `现金`, `支付宝`, `微信`, `银行卡`, and `信用卡`
4. Recurring transaction management such as adding, listing, updating, or deleting periodic payments or income schedules
5. Day, week, month, or year totals such as `今天花了多少`, `这周花了多少`, `这个月花了多少`, or `今年花了多少`
6. Day, week, month, or year analysis such as `这周花销哪里更多`, `这个月花销哪里更多`, or `今年收入主要来自哪里`
7. Day, week, month, or year detail queries such as `列出 2026-03-15 的账单`, `列出这周的账单`, `列出我这个月的账单`, or `列出 2026 年的账单`
8. Recent transaction queries such as `展示出最新的10个账单`
9. Latest-entry queries such as `显示最近的一笔账`
10. Update requests such as `修改一笔账 1 金额为12元，分类为学习`
11. Deletion requests such as `删除一笔账 3` or `删除最近的一笔账`

If the user's wording is relative, resolve it into an explicit date, week, month, or year before calling the script. In final answers, mention the exact period used, for example `2026-03-15`, `2026-W11`, `2026-03`, or `2026`.

## Recording Workflow

When the user asks to record a transaction:

1. Extract:
   - `entry_type`: default to `expense`; use `income` only when the prompt clearly indicates inflow such as salary, refund, reimbursement, bonus, or revenue.
   - `amount`: parse the positive numeric amount.
   - `occurred_on`: use `YYYY-MM-DD`; default to today if the prompt does not specify a date.
   - `account`: map to one of the supported accounts such as `现金`, `支付宝`, `微信`, `银行卡`, or `信用卡`; use `未指定账户` only when the user did not specify one.
   - `description`: keep it short and concrete, such as `奶茶`, `英语教材`, `插线板`.
   - `note`: keep extra context only if useful.
   - `source_text`: store the original natural-language prompt when practical.
2. Load the active categories first with `list-categories`.
3. Load the active accounts first with `list-accounts` if the account matters and you do not already know which ones are active.
4. If active categories exist, map the transaction into exactly one of them using semantic judgment.
5. If the mapping is clear, record with `--strict-category`.
6. If the account is clear and active, record with `--strict-account`.
7. If no categories exist yet, or the mapping is not reliable, either:
   - ask the user to define categories, or
   - record the transaction as `未分类` without `--strict-category`.
8. After writing the record, report the saved amount, category, account, date, and whether the category and account matched predefined values.

## Category Rules

- Categories are user-defined flat labels such as `日常`, `学习`, `电器`.
- Use `set-categories --replace` when the user wants to redefine the whole active category set.
- Use `set-categories` without `--replace` when the user wants to add more categories while preserving existing ones.
- Use `list-categories` before classification if you do not already know the active category set from the current conversation.
- If multiple categories are plausible, ask one disambiguation question instead of guessing.
- For `显示分类`, call `list-categories`.
- For `添加分类 ...`, call `set-categories` without `--replace`.
- For `删除分类 ...`, call `delete-category --name <category>` and treat it as deactivation, not history rewrites.

## Account Rules

- Supported account names are `现金`, `支付宝`, `微信`, `银行卡`, and `信用卡`.
- Default accounts are seeded automatically when the database is initialized.
- Use `list-accounts` to inspect the active account set.
- Use `set-accounts --replace` when the user wants to reset the active account set.
- Use `set-accounts` without `--replace` when the user wants to re-enable additional accounts while preserving existing ones.
- If the user specifies an account while recording, updating, or filtering transactions, normalize it to one of the supported account names.
- For `删除账户 ...`, call `delete-account --name <account>` and treat it as deactivation, not history rewrites.

## Recurring Workflow

Use recurring transactions to store scheduled payments or income that repeat over time.

When the user asks to manage recurring transactions:

1. Extract:
   - `entry_type`: default to `expense` unless the recurring item is clearly income.
   - `amount`
   - `category`
   - `account`
   - `description`
   - `frequency`: one of `weekly`, `monthly`, or `yearly`
   - `interval`: default to `1`
   - `next_due_on`: use `YYYY-MM-DD`
2. For creation, run `add-recurring ...`.
3. For listing schedules, run `list-recurring`.
4. If the user wants to see only items due by a specific date, run `list-recurring --due-by YYYY-MM-DD`.
5. For updates, require an id and run `update-recurring --id <id> ...`.
6. For deletion, require an id and run `delete-recurring --id <id>`.

Example prompts:

- `添加周期性支出 每月 1 号交房租 3000 用银行卡`
- `添加周期性支出 每周交健身房 100 用微信`
- `列出所有周期性账单`
- `列出本月到期的周期性账单`
- `修改周期性账单 1 下次日期为 2026-05-01`
- `删除周期性账单 2`

## Query Workflow

For day, week, month, or year totals or analysis:

1. Resolve the target period to one of:
   - `YYYY-MM-DD` for a day
   - `YYYY-Www` for an ISO week
   - `YYYY-MM` for a month
   - `YYYY` for a year
2. Run the matching report command:
   - `day-report --date YYYY-MM-DD`
   - `week-report --week YYYY-Www`
   - `month-report --month YYYY-MM`
   - `year-report --year YYYY`
3. Answer from the structured result:
   - `expense_total` for total spending
   - `income_total` for total income
   - `net_total` for net cash flow
   - `expense_by_category` for where spending is concentrated
   - `top_expense_category` for the largest spending category
   - `expense_by_account` for which account handled the spending
   - `top_expense_account` for the most-used spending account in the selected period

Example prompts:

- `今天花了多少`
- `2026-03-15 花了多少`
- `这周花了多少`
- `2026-W11 花了多少`
- `这个月花了多少`
- `2026-03 花了多少`
- `今年花了多少`
- `2026 年花了多少`
- `这周花销哪里更多`
- `今年收入主要来自哪里`

For detail queries:

1. Resolve the target period.
2. If the user asks for a category filter, load active categories first and pass `--category <name>`.
3. If the user asks for an account filter, load active accounts first and pass `--account <name>`.
4. Run `list-transactions` with exactly one period selector:
   - `--date YYYY-MM-DD`
   - `--week YYYY-Www`
   - `--month YYYY-MM`
   - `--year YYYY`
5. Summarize or list the returned entries.

Example prompts:

- `列出 2026-03-15 的账单`
- `显示今天的账单`
- `列出这周的账单`
- `列出 2026-W11 的账单`
- `列出这个月的账单`
- `列出 2026-03 的账单`
- `列出今年的账单`
- `列出 2026 年的账单`
- `列出 2026-03-15 学习分类的账单`
- `列出 2026-03 的支付宝账单`

For latest-entry queries:

1. Run `latest-entry`.
2. Return the saved entry id, date, amount, category, account, and description.

For recent-entry queries:

1. Parse the requested count; default to `10` if the user asks for `latest` without a number.
2. If the user asks for a category filter, load active categories first and pass `--category <name>`.
3. If the user asks for an account filter, load active accounts first and pass `--account <name>`.
4. Run `recent-transactions --limit N`.

For updates:

1. Require an id for either an entry or a recurring transaction.
2. Extract only the fields the user explicitly wants to change.
3. If the category is being changed, validate it against the active category list when possible.
4. If the account is being changed, validate it against the active account list when possible.
5. Use `update-entry --id <id> ...` for transactions.
6. Use `update-recurring --id <id> ...` for recurring schedules.

For deletion:

1. If the user asks for the latest entry, run `delete-latest-entry`.
2. If the user asks to delete a specific entry, require an id and run `delete-entry --id <id>`.
3. If the user asks to delete a recurring schedule, require an id and run `delete-recurring --id <id>`.
4. If no id is provided, ask for it instead of guessing.

## Script Entry Points

Use `{baseDir}/references/commands.md` for exact runtime command shapes.
Use `{baseDir}/references/chat_reference.md` only when you need extra natural-language prompt examples.

Main commands:

- `python "{baseDir}/scripts/bookkeeping.py" init-db`
- `python "{baseDir}/scripts/bookkeeping.py" list-categories`
- `python "{baseDir}/scripts/bookkeeping.py" list-accounts`
- `python "{baseDir}/scripts/bookkeeping.py" set-categories --replace 日常 学习 电器`
- `python "{baseDir}/scripts/bookkeeping.py" set-accounts --replace 现金 支付宝 微信 银行卡 信用卡`
- `python "{baseDir}/scripts/bookkeeping.py" set-categories 旅行`
- `python "{baseDir}/scripts/bookkeeping.py" record --amount 10 --category 日常 --account 支付宝 --description 奶茶 --date 2026-03-15 --source-text "我喝奶茶用了10元" --strict-category --strict-account`
- `python "{baseDir}/scripts/bookkeeping.py" add-recurring --amount 3000 --category 日常 --account 银行卡 --description 房租 --frequency monthly --next-date 2026-04-01 --strict-category --strict-account`
- `python "{baseDir}/scripts/bookkeeping.py" list-recurring --due-by 2026-04-30`
- `python "{baseDir}/scripts/bookkeeping.py" day-report --date 2026-03-15`
- `python "{baseDir}/scripts/bookkeeping.py" week-report --week 2026-W11`
- `python "{baseDir}/scripts/bookkeeping.py" month-report --month 2026-03`
- `python "{baseDir}/scripts/bookkeeping.py" year-report --year 2026`
- `python "{baseDir}/scripts/bookkeeping.py" list-transactions --date 2026-03-15 --account 支付宝`
- `python "{baseDir}/scripts/bookkeeping.py" list-transactions --month 2026-03`
- `python "{baseDir}/scripts/bookkeeping.py" recent-transactions --limit 10 --account 微信`
- `python "{baseDir}/scripts/bookkeeping.py" latest-entry`
- `python "{baseDir}/scripts/bookkeeping.py" update-entry --id 1 --amount 12 --category 学习 --account 信用卡 --description 奶茶教材 --strict-category --strict-account`
- `python "{baseDir}/scripts/bookkeeping.py" update-recurring --id 1 --account 信用卡 --next-date 2026-05-01 --strict-account`
- `python "{baseDir}/scripts/bookkeeping.py" delete-entry --id 3`
- `python "{baseDir}/scripts/bookkeeping.py" delete-latest-entry`
- `python "{baseDir}/scripts/bookkeeping.py" delete-category --name 旅行`
- `python "{baseDir}/scripts/bookkeeping.py" delete-account --name 微信`
- `python "{baseDir}/scripts/bookkeeping.py" delete-recurring --id 2`

## Response Rules

- Keep the user-facing response concise.
- When recording an entry, mention the exact date used.
- When answering a day, week, month, or year query, mention the exact period used.
- If the script reports an unmatched category or unmatched account, say so plainly and suggest updating the active sets if needed.
- If the database is empty for the requested period, state that directly.
