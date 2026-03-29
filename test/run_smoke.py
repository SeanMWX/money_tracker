#!/usr/bin/env python3
"""Local smoke test for the money_tracker script."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
BOOKKEEPING_SCRIPT = REPO_ROOT / "scripts" / "bookkeeping.py"
DEFAULT_DB_PATH = TEST_DIR / "data" / "smoke_test.db"

ACCOUNT_ALIPAY_CNY = "\u652f\u4ed8\u5b9d (CNY)"
ACCOUNT_BANK_USD = "\u94f6\u884c\u5361 (USD)"
ACCOUNT_TRAVELCARD_EUR = "TravelCard (EUR)"


def resolve_test_db() -> Path:
    raw_value = os.environ.get("MONEY_TRACKER_TEST_DB")
    if not raw_value:
        return DEFAULT_DB_PATH.resolve()
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = (TEST_DIR / path).resolve()
    return path


def run_command(db_path: Path, *args: str) -> dict:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    cmd = [sys.executable, str(BOOKKEEPING_SCRIPT), "--db", str(db_path), *args]
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not return JSON: {' '.join(args)}\n{result.stdout}") from exc


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    db_path = resolve_test_db()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    print(f"[INFO] Using test database: {db_path}")

    init_payload = run_command(db_path, "init-db")
    expect(init_payload["ok"], "init-db did not return ok=true")
    expect(init_payload["db_path"] == str(db_path), "init-db used the wrong database path")
    expect(init_payload["active_account_count"] == 5, "init-db did not seed the expected default wallets")

    categories_payload = run_command(db_path, "set-categories", "--replace", "daily", "salary")
    active_names = [item["name"] for item in categories_payload["categories"] if item["is_active"]]
    expect(active_names == ["daily", "salary"], f"unexpected categories: {active_names}")

    accounts_payload = run_command(db_path, "list-accounts")
    expect(ACCOUNT_ALIPAY_CNY in accounts_payload["active_account_labels"], "default wallets were not available")

    record_payload = run_command(
        db_path,
        "record",
        "--amount",
        "10",
        "--category",
        "daily",
        "--account",
        "\u652f\u4ed8\u5b9d",
        "--description",
        "tea",
        "--date",
        "2026-03-15",
        "--source-text",
        "record tea 10",
        "--strict-category",
        "--strict-account",
    )
    expect(record_payload["entry"]["category"] == "daily", "record did not use the expected category")
    expect(record_payload["entry"]["account"] == ACCOUNT_ALIPAY_CNY, "record did not normalize the expected wallet")
    expect(record_payload["entry"]["currency"] == "CNY", "record did not use the expected wallet currency")
    expect(record_payload["entry"]["amount"] == "10.00", "record did not persist the expected amount")

    set_accounts_payload = run_command(
        db_path,
        "set-accounts",
        "--replace",
        "\u652f\u4ed8\u5b9d",
        "\u94f6\u884c\u5361:USD",
    )
    expect(
        [item["label"] for item in set_accounts_payload["accounts"]] == [ACCOUNT_ALIPAY_CNY, ACCOUNT_BANK_USD],
        "set-accounts did not activate the expected wallets",
    )

    recurring_payload = run_command(
        db_path,
        "add-recurring",
        "--type",
        "income",
        "--amount",
        "50",
        "--category",
        "salary",
        "--account",
        "\u94f6\u884c\u5361:USD",
        "--description",
        "weekly_bonus",
        "--frequency",
        "monthly",
        "--next-date",
        "2026-04-01",
        "--strict-category",
        "--strict-account",
    )
    expect(recurring_payload["recurring_transaction"]["account"] == ACCOUNT_BANK_USD, "recurring wallet mismatch")
    expect(recurring_payload["recurring_transaction"]["currency"] == "USD", "recurring currency mismatch")
    expect(recurring_payload["recurring_transaction"]["frequency"] == "monthly", "recurring frequency mismatch")

    update_account_payload = run_command(
        db_path,
        "update-account",
        "--name",
        "\u94f6\u884c\u5361:USD",
        "--new-name",
        "TravelCard",
        "--currency",
        "EUR",
    )
    expect(update_account_payload["account"]["label"] == ACCOUNT_TRAVELCARD_EUR, "update-account wallet label mismatch")
    expect(update_account_payload["linked_recurring_transaction_count"] == 1, "update-account recurring propagation mismatch")

    balances_payload = run_command(db_path, "account-balances")
    totals = {item["currency"]: item["balance"] for item in balances_payload["totals_by_currency"]}
    expect(totals["CNY"] == "-10.00", "CNY wallet totals mismatch after replace")
    expect(totals["EUR"] == "0.00", "EUR wallet totals mismatch after update-account")

    report_payload = run_command(db_path, "month-report", "--month", "2026-03")
    expect(report_payload["expense_total"] == "10.00", "month-report expense_total mismatch")
    expect(report_payload["totals_by_currency"][0]["currency"] == "CNY", "month-report currency summary mismatch")
    expect(report_payload["top_expense_account"]["account"] == ACCOUNT_ALIPAY_CNY, "month-report wallet breakdown mismatch")

    day_payload = run_command(db_path, "day-report", "--date", "2026-03-15")
    expect(day_payload["expense_total"] == "10.00", "day-report expense_total mismatch")
    expect(day_payload["date"] == "2026-03-15", "day-report date mismatch")

    year_payload = run_command(db_path, "year-report", "--year", "2026")
    expect(year_payload["expense_total"] == "10.00", "year-report expense_total mismatch")
    expect(year_payload["year"] == "2026", "year-report year mismatch")

    latest_payload = run_command(db_path, "latest-entry")
    expect(latest_payload["entry"]["description"] == "tea", "latest-entry description mismatch")

    recent_payload = run_command(db_path, "recent-transactions", "--account", "\u652f\u4ed8\u5b9d", "--limit", "5")
    expect(len(recent_payload["entries"]) == 1, "recent-transactions entry count mismatch")

    recurring_list_payload = run_command(db_path, "list-recurring", "--due-by", "2026-04-30")
    expect(len(recurring_list_payload["recurring_transactions"]) == 1, "list-recurring count mismatch")
    expect(
        recurring_list_payload["recurring_transactions"][0]["account"] == ACCOUNT_TRAVELCARD_EUR,
        "list-recurring wallet label mismatch after update-account",
    )

    print("[OK] Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
