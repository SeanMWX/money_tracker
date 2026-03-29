# money_tracker Commands

## Runtime

- Python: `3.9+`
- Dependencies: Python standard library only
- Default database path: `~/.money_tracker/bookkeeping.db`
- Runtime script: `{baseDir}/scripts/bookkeeping.py`
- Override order:
  1. `--db <path>`
  2. `MONEY_TRACKER_DB`
  3. `LOCAL_BOOKKEEPING_DB` (legacy compatibility)
  4. default home-directory path
- For extra prompt examples, see `{baseDir}/references/chat_reference.md`

## Command Summary

All commands print JSON with `ensure_ascii=False`.

### Initialize the database

Create the database file and schema at the resolved path:

```bash
python "{baseDir}/scripts/bookkeeping.py" init-db
python "{baseDir}/scripts/bookkeeping.py" --db ./my-bookkeeping.db init-db
```

### List categories

```bash
python "{baseDir}/scripts/bookkeeping.py" list-categories
python "{baseDir}/scripts/bookkeeping.py" list-categories --all
```

### Set categories

Replace the active set:

```bash
python "{baseDir}/scripts/bookkeeping.py" set-categories --replace 日常 学习 电器
```

Add new active categories without removing old ones:

```bash
python "{baseDir}/scripts/bookkeeping.py" set-categories 旅行
```

### Record one transaction

Expense example:

```bash
python "{baseDir}/scripts/bookkeeping.py" record --amount 10 --category 日常 --description 奶茶 --date 2026-03-15 --source-text "我喝奶茶用了10元" --strict-category
```

Income example:

```bash
python "{baseDir}/scripts/bookkeeping.py" record --type income --amount 5000 --category 工资 --description 工资到账 --date 2026-03-01 --source-text "这个月工资到账5000元"
```

Notes:

- `--type` defaults to `expense`
- `--date` defaults to today
- `--currency` defaults to `CNY`
- `--category` defaults to `未分类`
- `--strict-category` fails if the category is not an active predefined category

### Monthly report

```bash
python "{baseDir}/scripts/bookkeeping.py" month-report --month 2026-03
```

Key output fields:

- `expense_total`
- `income_total`
- `net_total`
- `expense_by_category`
- `income_by_category`
- `top_expense_category`
- `entry_count`

### List transactions for one month

```bash
python "{baseDir}/scripts/bookkeeping.py" list-transactions --month 2026-03
python "{baseDir}/scripts/bookkeeping.py" list-transactions --month 2026-03 --type expense --limit 20
python "{baseDir}/scripts/bookkeeping.py" list-transactions --month 2026-03 --category 学习 --limit 20
```

### Recent transactions

```bash
python "{baseDir}/scripts/bookkeeping.py" recent-transactions
python "{baseDir}/scripts/bookkeeping.py" recent-transactions --limit 10
python "{baseDir}/scripts/bookkeeping.py" recent-transactions --limit 10 --category 学习
```

### Show the latest transaction

```bash
python "{baseDir}/scripts/bookkeeping.py" latest-entry
```

### Update one transaction

```bash
python "{baseDir}/scripts/bookkeeping.py" update-entry --id 1 --amount 12 --category 学习 --description 奶茶教材 --strict-category
```

Use this when the user wants to fix amount, category, description, note, date, type, currency, or the original prompt text.

### Delete one transaction

```bash
python "{baseDir}/scripts/bookkeeping.py" delete-entry --id 3
```

### Delete the latest transaction

```bash
python "{baseDir}/scripts/bookkeeping.py" delete-latest-entry
```

### Delete one category

```bash
python "{baseDir}/scripts/bookkeeping.py" delete-category --name 旅行
```

## Classification Guidance

When a user says `记账 <prompt>`:

1. Extract the monetary amount.
2. Infer whether it is `expense` or `income`.
3. Resolve the date into `YYYY-MM-DD`.
4. Read active categories.
5. Map the transaction to the closest active category.
6. If the mapping is weak, ask one question instead of inventing a category.
7. Use `未分类` only as an intentional fallback.

## Data Semantics

- Amounts are stored internally as integer cents.
- Date storage uses ISO format `YYYY-MM-DD`.
- Monthly filtering uses half-open ranges:
  - start: first day of the month
  - end: first day of the next month
- Category reports group by the saved category snapshot so historical entries remain readable even if the active category list changes later.
