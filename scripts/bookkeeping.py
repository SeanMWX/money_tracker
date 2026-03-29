#!/usr/bin/env python3
"""money_tracker helper backed by SQLite."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

MIN_PYTHON = (3, 9)
DEFAULT_DB_ENV = "MONEY_TRACKER_DB"
LEGACY_DB_ENV = "LOCAL_BOOKKEEPING_DB"
DEFAULT_DB_DIR = ".money_tracker"
LEGACY_DB_DIR = ".local-bookkeeping"
DEFAULT_DB_NAME = "bookkeeping.db"
DEFAULT_UNCATEGORIZED = "\u672a\u5206\u7c7b"


def fail(message, exit_code=1, **extra):
    payload = {"ok": False, "error": message}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_db_path(raw_path):
    candidate = raw_path or os.environ.get(DEFAULT_DB_ENV) or os.environ.get(LEGACY_DB_ENV)
    if candidate:
        return Path(candidate).expanduser().resolve()
    default_path = (Path.home() / DEFAULT_DB_DIR / DEFAULT_DB_NAME).resolve()
    legacy_path = (Path.home() / LEGACY_DB_DIR / DEFAULT_DB_NAME).resolve()
    if default_path.exists() or not legacy_path.exists():
        return default_path
    return legacy_path


def connect_db(db_path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    return conn


def ensure_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL CHECK (entry_type IN ('expense', 'income')),
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            currency TEXT NOT NULL DEFAULT 'CNY',
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            category_name_snapshot TEXT NOT NULL,
            description TEXT NOT NULL,
            note TEXT,
            occurred_on TEXT NOT NULL,
            source_text TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_entries_occurred_on ON entries (occurred_on);
        CREATE INDEX IF NOT EXISTS idx_entries_type_date ON entries (entry_type, occurred_on);
        CREATE INDEX IF NOT EXISTS idx_entries_category_snapshot ON entries (category_name_snapshot);
        """
    )
    conn.commit()


def get_db_counts(conn):
    category_count = conn.execute("SELECT COUNT(*) AS count FROM categories WHERE is_active = 1").fetchone()["count"]
    entry_count = conn.execute("SELECT COUNT(*) AS count FROM entries").fetchone()["count"]
    return {"active_category_count": category_count, "entry_count": entry_count}


def normalize_names(names):
    cleaned = []
    seen = set()
    for raw_name in names:
        name = raw_name.strip()
        if not name:
            continue
        if name not in seen:
            cleaned.append(name)
            seen.add(name)
    if not cleaned:
        fail("At least one non-empty category name is required.")
    return cleaned


def parse_amount_to_cents(raw_amount):
    try:
        amount = Decimal(str(raw_amount))
    except InvalidOperation:
        fail("Invalid amount.", provided=raw_amount)
    if amount <= 0:
        fail("Amount must be greater than zero.", provided=raw_amount)
    normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((normalized * 100).to_integral_value(rounding=ROUND_HALF_UP))


def cents_to_amount(cents):
    return format((Decimal(cents) / Decimal(100)).quantize(Decimal("0.01")), "f")


def parse_iso_date(raw_date):
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        fail("Invalid date. Expected YYYY-MM-DD.", provided=raw_date)


def normalize_month(raw_month):
    if not raw_month:
        today = date.today()
        return f"{today.year:04d}-{today.month:02d}"
    parts = raw_month.split("-")
    if len(parts) != 2:
        fail("Invalid month. Expected YYYY-MM.", provided=raw_month)
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError:
        fail("Invalid month. Expected YYYY-MM.", provided=raw_month)
    if year < 1 or not 1 <= month <= 12:
        fail("Invalid month. Expected YYYY-MM.", provided=raw_month)
    return f"{year:04d}-{month:02d}"


def month_bounds(month_value):
    normalized = normalize_month(month_value)
    year, month = (int(part) for part in normalized.split("-"))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return normalized, start.isoformat(), end.isoformat()


def list_categories_rows(conn, include_inactive=False):
    if include_inactive:
        query = """
            SELECT id, name, is_active, sort_order, created_at, updated_at
            FROM categories
            ORDER BY sort_order ASC, id ASC
        """
        return conn.execute(query).fetchall()
    query = """
        SELECT id, name, is_active, sort_order, created_at, updated_at
        FROM categories
        WHERE is_active = 1
        ORDER BY sort_order ASC, id ASC
    """
    return conn.execute(query).fetchall()


def active_category_names(conn):
    return [row["name"] for row in list_categories_rows(conn, include_inactive=False)]


def resolve_category(conn, category_name):
    snapshot = category_name.strip() if category_name and category_name.strip() else DEFAULT_UNCATEGORIZED
    row = conn.execute(
        """
        SELECT id, name
        FROM categories
        WHERE name = ? AND is_active = 1
        """,
        (snapshot,),
    ).fetchone()
    if row:
        return row["id"], row["name"], True
    return None, snapshot, False


def serialize_category_row(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "is_active": bool(row["is_active"]),
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_entry_row(row):
    return {
        "id": row["id"],
        "type": row["entry_type"],
        "amount": cents_to_amount(row["amount_cents"]),
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "category": row["category_name_snapshot"],
        "description": row["description"],
        "note": row["note"],
        "occurred_on": row["occurred_on"],
        "source_text": row["source_text"],
        "created_at": row["created_at"],
    }


def fetch_entry_by_id(conn, entry_id):
    return conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()


def fetch_latest_entry(conn):
    return conn.execute("SELECT * FROM entries ORDER BY id DESC LIMIT 1").fetchone()


def fetch_category_by_name(conn, category_name):
    return conn.execute(
        """
        SELECT id, name, is_active, sort_order, created_at, updated_at
        FROM categories
        WHERE name = ?
        """,
        (category_name,),
    ).fetchone()


def get_breakdown(conn, start_date, end_date, entry_type):
    rows = conn.execute(
        """
        SELECT
            category_name_snapshot AS category,
            SUM(amount_cents) AS total_cents,
            COUNT(*) AS entry_count
        FROM entries
        WHERE occurred_on >= ? AND occurred_on < ? AND entry_type = ?
        GROUP BY category_name_snapshot
        ORDER BY total_cents DESC, category_name_snapshot ASC
        """,
        (start_date, end_date, entry_type),
    ).fetchall()
    breakdown = []
    for row in rows:
        breakdown.append(
            {
                "category": row["category"],
                "total": cents_to_amount(row["total_cents"]),
                "total_cents": row["total_cents"],
                "entry_count": row["entry_count"],
            }
        )
    return breakdown


def cmd_list_categories(args):
    db_path = resolve_db_path(args.db)
    with closing(connect_db(db_path)) as conn:
        categories = [serialize_category_row(row) for row in list_categories_rows(conn, args.all)]
    emit(
        {
            "ok": True,
            "command": "list-categories",
            "db_path": str(db_path),
            "categories": categories,
            "active_category_names": [item["name"] for item in categories if item["is_active"]],
        }
    )


def cmd_init_db(args):
    db_path = resolve_db_path(args.db)
    existed_before = db_path.exists()
    with closing(connect_db(db_path)) as conn:
        counts = get_db_counts(conn)
    emit(
        {
            "ok": True,
            "command": "init-db",
            "db_path": str(db_path),
            "db_exists": db_path.exists(),
            "db_existed_before": existed_before,
            "db_parent": str(db_path.parent),
            **counts,
        }
    )


def cmd_set_categories(args):
    names = normalize_names(args.names)
    db_path = resolve_db_path(args.db)
    now = utc_now()
    with closing(connect_db(db_path)) as conn:
        if args.replace:
            conn.execute("UPDATE categories SET is_active = 0, updated_at = ? WHERE is_active = 1", (now,))
            base_order = 0
        else:
            base_order = (
                conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS max_sort_order FROM categories").fetchone()[
                    "max_sort_order"
                ]
                + 1
            )
        for index, name in enumerate(names):
            conn.execute(
                """
                INSERT INTO categories (name, is_active, sort_order, created_at, updated_at)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    is_active = 1,
                    sort_order = excluded.sort_order,
                    updated_at = excluded.updated_at
                """,
                (name, base_order + index, now, now),
            )
        conn.commit()
        categories = [serialize_category_row(row) for row in list_categories_rows(conn, include_inactive=False)]
    emit(
        {
            "ok": True,
            "command": "set-categories",
            "db_path": str(db_path),
            "replace": bool(args.replace),
            "categories": categories,
        }
    )


def cmd_record(args):
    db_path = resolve_db_path(args.db)
    amount_cents = parse_amount_to_cents(args.amount)
    occurred_on = parse_iso_date(args.date).isoformat()
    entry_type = args.type
    description = args.description.strip()
    if not description:
        fail("Description is required.")
    note = args.note.strip() if args.note else None
    source_text = args.source_text.strip() if args.source_text else None
    currency = args.currency.strip().upper() if args.currency else "CNY"
    if not currency:
        currency = "CNY"

    with closing(connect_db(db_path)) as conn:
        category_id, category_snapshot, matched = resolve_category(conn, args.category)
        active_names = active_category_names(conn)
        if args.strict_category and not matched:
            fail(
                "Category does not match an active predefined category.",
                provided_category=category_snapshot,
                active_categories=active_names,
            )
        created_at = utc_now()
        cursor = conn.execute(
            """
            INSERT INTO entries (
                entry_type,
                amount_cents,
                currency,
                category_id,
                category_name_snapshot,
                description,
                note,
                occurred_on,
                source_text,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_type,
                amount_cents,
                currency,
                category_id,
                category_snapshot,
                description,
                note,
                occurred_on,
                source_text,
                created_at,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM entries WHERE id = ?", (cursor.lastrowid,)).fetchone()

    payload = serialize_entry_row(row)
    payload["category_matched_active_category"] = matched
    emit(
        {
            "ok": True,
            "command": "record",
            "db_path": str(db_path),
            "entry": payload,
        }
    )


def cmd_list_transactions(args):
    db_path = resolve_db_path(args.db)
    month_value, start_date, end_date = month_bounds(args.month)
    params = [start_date, end_date]
    query = """
        SELECT *
        FROM entries
        WHERE occurred_on >= ? AND occurred_on < ?
    """
    if args.type:
        query += " AND entry_type = ?"
        params.append(args.type)
    if args.category:
        query += " AND category_name_snapshot = ?"
        params.append(args.category.strip())
    query += " ORDER BY occurred_on DESC, id DESC LIMIT ?"
    params.append(args.limit)

    with closing(connect_db(db_path)) as conn:
        rows = conn.execute(query, params).fetchall()

    emit(
        {
            "ok": True,
            "command": "list-transactions",
            "db_path": str(db_path),
            "month": month_value,
            "start_date": start_date,
            "end_date_exclusive": end_date,
            "type_filter": args.type,
            "category_filter": args.category,
            "limit": args.limit,
            "entries": [serialize_entry_row(row) for row in rows],
        }
    )


def cmd_recent_transactions(args):
    db_path = resolve_db_path(args.db)
    params = []
    query = """
        SELECT *
        FROM entries
    """
    filters = []
    if args.type:
        filters.append("entry_type = ?")
        params.append(args.type)
    if args.category:
        filters.append("category_name_snapshot = ?")
        params.append(args.category.strip())
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)

    with closing(connect_db(db_path)) as conn:
        rows = conn.execute(query, params).fetchall()

    emit(
        {
            "ok": True,
            "command": "recent-transactions",
            "db_path": str(db_path),
            "type_filter": args.type,
            "category_filter": args.category,
            "limit": args.limit,
            "entries": [serialize_entry_row(row) for row in rows],
        }
    )


def cmd_latest_entry(args):
    db_path = resolve_db_path(args.db)
    with closing(connect_db(db_path)) as conn:
        row = fetch_latest_entry(conn)
        if row is None:
            fail("No entries available.")

    emit(
        {
            "ok": True,
            "command": "latest-entry",
            "db_path": str(db_path),
            "entry": serialize_entry_row(row),
        }
    )


def cmd_month_report(args):
    db_path = resolve_db_path(args.db)
    month_value, start_date, end_date = month_bounds(args.month)

    with closing(connect_db(db_path)) as conn:
        totals = {"expense": {"total_cents": 0, "entry_count": 0}, "income": {"total_cents": 0, "entry_count": 0}}
        for row in conn.execute(
            """
            SELECT entry_type, COALESCE(SUM(amount_cents), 0) AS total_cents, COUNT(*) AS entry_count
            FROM entries
            WHERE occurred_on >= ? AND occurred_on < ?
            GROUP BY entry_type
            """,
            (start_date, end_date),
        ):
            totals[row["entry_type"]] = {
                "total_cents": row["total_cents"],
                "entry_count": row["entry_count"],
            }

        expense_breakdown = get_breakdown(conn, start_date, end_date, "expense")
        income_breakdown = get_breakdown(conn, start_date, end_date, "income")

    expense_total_cents = totals["expense"]["total_cents"]
    income_total_cents = totals["income"]["total_cents"]
    net_total_cents = income_total_cents - expense_total_cents

    emit(
        {
            "ok": True,
            "command": "month-report",
            "db_path": str(db_path),
            "month": month_value,
            "start_date": start_date,
            "end_date_exclusive": end_date,
            "expense_total": cents_to_amount(expense_total_cents),
            "expense_total_cents": expense_total_cents,
            "income_total": cents_to_amount(income_total_cents),
            "income_total_cents": income_total_cents,
            "net_total": cents_to_amount(net_total_cents),
            "net_total_cents": net_total_cents,
            "entry_count": totals["expense"]["entry_count"] + totals["income"]["entry_count"],
            "expense_entry_count": totals["expense"]["entry_count"],
            "income_entry_count": totals["income"]["entry_count"],
            "expense_by_category": expense_breakdown,
            "income_by_category": income_breakdown,
            "top_expense_category": expense_breakdown[0] if expense_breakdown else None,
            "top_income_category": income_breakdown[0] if income_breakdown else None,
        }
    )


def cmd_update_entry(args):
    db_path = resolve_db_path(args.db)
    with closing(connect_db(db_path)) as conn:
        row = fetch_entry_by_id(conn, args.id)
        if row is None:
            fail("Entry not found.", entry_id=args.id)

        updates = {}
        updated_fields = []
        matched = None
        active_names = None

        if args.type is not None:
            updates["entry_type"] = args.type
            updated_fields.append("type")
        if args.amount is not None:
            updates["amount_cents"] = parse_amount_to_cents(args.amount)
            updated_fields.append("amount")
        if args.currency is not None:
            currency = args.currency.strip().upper() if args.currency else "CNY"
            if not currency:
                currency = "CNY"
            updates["currency"] = currency
            updated_fields.append("currency")
        if args.category is not None:
            category_id, category_snapshot, matched = resolve_category(conn, args.category)
            active_names = active_category_names(conn)
            if args.strict_category and not matched:
                fail(
                    "Category does not match an active predefined category.",
                    provided_category=category_snapshot,
                    active_categories=active_names,
                )
            updates["category_id"] = category_id
            updates["category_name_snapshot"] = category_snapshot
            updated_fields.append("category")
        if args.description is not None:
            description = args.description.strip()
            if not description:
                fail("Description is required.")
            updates["description"] = description
            updated_fields.append("description")
        if args.note is not None:
            note = args.note.strip()
            updates["note"] = note or None
            updated_fields.append("note")
        if args.date is not None:
            updates["occurred_on"] = parse_iso_date(args.date).isoformat()
            updated_fields.append("date")
        if args.source_text is not None:
            source_text = args.source_text.strip()
            updates["source_text"] = source_text or None
            updated_fields.append("source_text")

        if not updates:
            fail("Provide at least one field to update.")

        update_pairs = list(updates.items())
        query = "UPDATE entries SET " + ", ".join(f"{column} = ?" for column, _ in update_pairs) + " WHERE id = ?"
        values = [value for _, value in update_pairs]
        values.append(args.id)
        conn.execute(query, values)
        conn.commit()
        updated_row = fetch_entry_by_id(conn, args.id)

    payload = serialize_entry_row(updated_row)
    if matched is not None:
        payload["category_matched_active_category"] = matched
    emit(
        {
            "ok": True,
            "command": "update-entry",
            "db_path": str(db_path),
            "updated_fields": updated_fields,
            "active_categories": active_names,
            "entry": payload,
        }
    )


def cmd_delete_entry(args):
    db_path = resolve_db_path(args.db)
    with closing(connect_db(db_path)) as conn:
        row = fetch_entry_by_id(conn, args.id)
        if row is None:
            fail("Entry not found.", entry_id=args.id)
        deleted_entry = serialize_entry_row(row)
        conn.execute("DELETE FROM entries WHERE id = ?", (args.id,))
        conn.commit()
        counts = get_db_counts(conn)

    emit(
        {
            "ok": True,
            "command": "delete-entry",
            "db_path": str(db_path),
            "deleted_entry": deleted_entry,
            **counts,
        }
    )


def cmd_delete_category(args):
    db_path = resolve_db_path(args.db)
    category_name = args.name.strip()
    if not category_name:
        fail("Category name is required.")

    with closing(connect_db(db_path)) as conn:
        row = fetch_category_by_name(conn, category_name)
        if row is None:
            fail("Category not found.", category=category_name)
        if not row["is_active"]:
            fail("Category is already inactive.", category=category_name)

        now = utc_now()
        conn.execute(
            """
            UPDATE categories
            SET is_active = 0, updated_at = ?
            WHERE id = ?
            """,
            (now, row["id"]),
        )
        conn.commit()
        deleted_category = fetch_category_by_name(conn, category_name)
        categories = [serialize_category_row(item) for item in list_categories_rows(conn, include_inactive=False)]

    emit(
        {
            "ok": True,
            "command": "delete-category",
            "db_path": str(db_path),
            "deleted_category": serialize_category_row(deleted_category),
            "categories": categories,
            "active_category_names": [item["name"] for item in categories],
        }
    )


def cmd_delete_latest_entry(args):
    db_path = resolve_db_path(args.db)
    with closing(connect_db(db_path)) as conn:
        row = fetch_latest_entry(conn)
        if row is None:
            fail("No entries available to delete.")
        deleted_entry = serialize_entry_row(row)
        conn.execute("DELETE FROM entries WHERE id = ?", (row["id"],))
        conn.commit()
        counts = get_db_counts(conn)

    emit(
        {
            "ok": True,
            "command": "delete-latest-entry",
            "db_path": str(db_path),
            "deleted_entry": deleted_entry,
            **counts,
        }
    )


def build_parser():
    parser = argparse.ArgumentParser(description="money_tracker helper backed by SQLite.")
    parser.add_argument("--db", help="Custom SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Create the database file and schema")
    init_db.set_defaults(func=cmd_init_db)

    list_categories = subparsers.add_parser("list-categories", help="List categories")
    list_categories.add_argument("--all", action="store_true", help="Include inactive categories")
    list_categories.set_defaults(func=cmd_list_categories)

    set_categories = subparsers.add_parser("set-categories", help="Add or replace categories")
    set_categories.add_argument("names", nargs="+", help="Category names")
    set_categories.add_argument("--replace", action="store_true", help="Replace the active category set")
    set_categories.set_defaults(func=cmd_set_categories)

    record = subparsers.add_parser("record", help="Record one transaction")
    record.add_argument("--type", choices=["expense", "income"], default="expense", help="Transaction type")
    record.add_argument("--amount", required=True, help="Positive amount")
    record.add_argument("--category", default=DEFAULT_UNCATEGORIZED, help="Category name")
    record.add_argument("--description", required=True, help="Short description")
    record.add_argument("--note", help="Additional note")
    record.add_argument("--date", default=date.today().isoformat(), help="Occurrence date in YYYY-MM-DD")
    record.add_argument("--currency", default="CNY", help="Currency code")
    record.add_argument("--source-text", help="Original natural-language prompt")
    record.add_argument(
        "--strict-category",
        action="store_true",
        help="Require the category to match an active predefined category",
    )
    record.set_defaults(func=cmd_record)

    list_transactions = subparsers.add_parser("list-transactions", help="List transactions for one month")
    list_transactions.add_argument("--month", help="Target month in YYYY-MM; defaults to the current month")
    list_transactions.add_argument("--type", choices=["expense", "income"], help="Optional type filter")
    list_transactions.add_argument("--category", help="Optional category filter")
    list_transactions.add_argument("--limit", type=int, default=100, help="Maximum number of entries to return")
    list_transactions.set_defaults(func=cmd_list_transactions)

    recent_transactions = subparsers.add_parser(
        "recent-transactions",
        help="List the most recent transactions across all dates",
    )
    recent_transactions.add_argument("--type", choices=["expense", "income"], help="Optional type filter")
    recent_transactions.add_argument("--category", help="Optional category filter")
    recent_transactions.add_argument("--limit", type=int, default=10, help="Maximum number of entries to return")
    recent_transactions.set_defaults(func=cmd_recent_transactions)

    latest_entry = subparsers.add_parser("latest-entry", help="Show the latest transaction")
    latest_entry.set_defaults(func=cmd_latest_entry)

    month_report = subparsers.add_parser("month-report", help="Get totals and category breakdown for one month")
    month_report.add_argument("--month", help="Target month in YYYY-MM; defaults to the current month")
    month_report.set_defaults(func=cmd_month_report)

    update_entry = subparsers.add_parser("update-entry", help="Update one transaction by id")
    update_entry.add_argument("--id", type=int, required=True, help="Entry id to update")
    update_entry.add_argument("--type", choices=["expense", "income"], help="Updated transaction type")
    update_entry.add_argument("--amount", help="Updated positive amount")
    update_entry.add_argument("--currency", help="Updated currency code")
    update_entry.add_argument("--category", help="Updated category name")
    update_entry.add_argument("--description", help="Updated short description")
    update_entry.add_argument("--note", help="Updated note; use an empty string to clear it")
    update_entry.add_argument("--date", help="Updated occurrence date in YYYY-MM-DD")
    update_entry.add_argument("--source-text", help="Updated original natural-language prompt")
    update_entry.add_argument(
        "--strict-category",
        action="store_true",
        help="Require the updated category to match an active predefined category",
    )
    update_entry.set_defaults(func=cmd_update_entry)

    delete_entry = subparsers.add_parser("delete-entry", help="Delete one transaction by id")
    delete_entry.add_argument("--id", type=int, required=True, help="Entry id to delete")
    delete_entry.set_defaults(func=cmd_delete_entry)

    delete_latest_entry = subparsers.add_parser("delete-latest-entry", help="Delete the latest transaction")
    delete_latest_entry.set_defaults(func=cmd_delete_latest_entry)

    delete_category = subparsers.add_parser("delete-category", help="Deactivate one category by name")
    delete_category.add_argument("--name", required=True, help="Active category name to deactivate")
    delete_category.set_defaults(func=cmd_delete_category)

    return parser


def main():
    if sys.version_info < MIN_PYTHON:
        fail(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.",
            python_version=".".join(str(part) for part in sys.version_info[:3]),
        )
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "limit") and args.limit <= 0:
        fail("Limit must be greater than zero.", provided=args.limit)
    if hasattr(args, "id") and args.id <= 0:
        fail("Entry id must be greater than zero.", provided=args.id)
    args.func(args)


if __name__ == "__main__":
    main()
