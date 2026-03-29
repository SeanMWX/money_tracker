---
name: money_tracker
description: 本地 SQLite 记账与月度消费分析。用于处理中文自然语言记账、查账、分类管理、最近账单查询、修改账单和删除账单请求，例如“记账 我喝奶茶用了10元”“把分类设置为日常、学习、电器”“显示我这个月的账单是多少”“展示出最新的10个账单”“删除最近的一笔账”。支持用户预定义分类、自动分类、本月总额统计、分类占比分析、交易明细查询和账单维护。
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
3. Monthly totals such as `这个月花了多少`
4. Monthly analysis such as `这个月花销哪里更多`
5. Monthly detail queries such as `列出我这个月的账单`
6. Recent transaction queries such as `展示出最新的10个账单`
7. Latest-entry queries such as `显示最近的一笔账`
8. Update requests such as `修改一笔账 1 金额为12元，分类为学习`
9. Deletion requests such as `删除一笔账 3` or `删除最近的一笔账`

If the user's wording is relative, resolve it into an explicit date or month before calling the script. In final answers, mention the exact month or date used, for example `2026-03` or `2026-03-15`.

## Recording Workflow

When the user asks to record a transaction:

1. Extract:
   - `entry_type`: default to `expense`; use `income` only when the prompt clearly indicates inflow such as salary, refund, reimbursement, bonus, or revenue.
   - `amount`: parse the positive numeric amount.
   - `occurred_on`: use `YYYY-MM-DD`; default to today if the prompt does not specify a date.
   - `description`: keep it short and concrete, such as `奶茶`, `英语教材`, `插线板`.
   - `note`: keep extra context only if useful.
   - `source_text`: store the original natural-language prompt when practical.
2. Load the active categories first with `list-categories`.
3. If active categories exist, map the transaction into exactly one of them using semantic judgment.
4. If the mapping is clear, record with `--strict-category`.
5. If no categories exist yet, or the mapping is not reliable, either:
   - ask the user to define categories, or
   - record the transaction as `未分类` without `--strict-category`.
6. After writing the record, report the saved amount, category, date, and whether the category matched a predefined category.

## Category Rules

- Categories are user-defined flat labels such as `日常`, `学习`, `电器`.
- Use `set-categories --replace` when the user wants to redefine the whole active category set.
- Use `set-categories` without `--replace` when the user wants to add more categories while preserving existing ones.
- Use `list-categories` before classification if you do not already know the active category set from the current conversation.
- If multiple categories are plausible, ask one disambiguation question instead of guessing.
- For `显示分类`, call `list-categories`.
- For `添加分类 ...`, call `set-categories` without `--replace`.
- For `删除分类 ...`, call `delete-category --name <category>` and treat it as deactivation, not history rewrites.

## Query Workflow

For monthly totals or analysis:

1. Resolve the target month to `YYYY-MM`.
2. Run `month-report --month YYYY-MM`.
3. Answer from the structured result:
   - `expense_total` for total spending
   - `income_total` for total income
   - `net_total` for net cash flow
   - `expense_by_category` for where spending is concentrated
   - `top_expense_category` for the largest spending category

For detail queries:

1. Resolve the target month.
2. If the user asks for a category filter, load active categories first and pass `--category <name>`.
3. Run `list-transactions --month YYYY-MM`.
4. Summarize or list the returned entries.

For latest-entry queries:

1. Run `latest-entry`.
2. Return the saved entry id, date, amount, category, and description.

For recent-entry queries:

1. Parse the requested count; default to `10` if the user asks for `latest` without a number.
2. If the user asks for a category filter, load active categories first and pass `--category <name>`.
3. Run `recent-transactions --limit N`.

For updates:

1. Require an entry id.
2. Extract only the fields the user explicitly wants to change.
3. If the category is being changed, validate it against the active category list when possible.
4. Run `update-entry --id <id> ...`.

For deletion:

1. If the user asks for the latest entry, run `delete-latest-entry`.
2. If the user asks to delete a specific entry, require an id and run `delete-entry --id <id>`.
3. If no id is provided, ask for it instead of guessing.

## Script Entry Points

Use `{baseDir}/references/commands.md` for exact runtime command shapes.
Use `{baseDir}/references/chat_reference.md` only when you need extra natural-language prompt examples.

Main commands:

- `python "{baseDir}/scripts/bookkeeping.py" init-db`
- `python "{baseDir}/scripts/bookkeeping.py" list-categories`
- `python "{baseDir}/scripts/bookkeeping.py" set-categories --replace 日常 学习 电器`
- `python "{baseDir}/scripts/bookkeeping.py" set-categories 旅行`
- `python "{baseDir}/scripts/bookkeeping.py" record --amount 10 --category 日常 --description 奶茶 --date 2026-03-15 --source-text "我喝奶茶用了10元" --strict-category`
- `python "{baseDir}/scripts/bookkeeping.py" month-report --month 2026-03`
- `python "{baseDir}/scripts/bookkeeping.py" list-transactions --month 2026-03`
- `python "{baseDir}/scripts/bookkeeping.py" recent-transactions --limit 10`
- `python "{baseDir}/scripts/bookkeeping.py" latest-entry`
- `python "{baseDir}/scripts/bookkeeping.py" update-entry --id 1 --amount 12 --category 学习 --description 奶茶教材 --strict-category`
- `python "{baseDir}/scripts/bookkeeping.py" delete-entry --id 3`
- `python "{baseDir}/scripts/bookkeeping.py" delete-latest-entry`
- `python "{baseDir}/scripts/bookkeeping.py" delete-category --name 旅行`

## Response Rules

- Keep the user-facing response concise.
- When recording an entry, mention the exact date used.
- When answering a monthly query, mention the exact month used.
- If the script reports an unmatched category, say so plainly and suggest updating categories if needed.
- If the database is empty for the requested month, state that directly.
