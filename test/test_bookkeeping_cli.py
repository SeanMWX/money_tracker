#!/usr/bin/env python3
"""Comprehensive tests for the money_tracker CLI script."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bookkeeping.py"

ACCOUNT_CASH = "\u73b0\u91d1"
ACCOUNT_ALIPAY = "\u652f\u4ed8\u5b9d"
ACCOUNT_WECHAT = "\u5fae\u4fe1"
ACCOUNT_BANK_CARD = "\u94f6\u884c\u5361"
ACCOUNT_CREDIT_CARD = "\u4fe1\u7528\u5361"

SPEC = importlib.util.spec_from_file_location("money_tracker_bookkeeping", SCRIPT_PATH)
BOOKKEEPING = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BOOKKEEPING)


class CliTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="money_tracker_test_")
        self.temp_path = Path(self.temp_dir.name)
        self.db_path = self.temp_path / "bookkeeping.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str, env_extra: dict[str, str] | None = None) -> tuple[int, dict, str]:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        if env_extra:
            env.update(env_extra)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--db", str(self.db_path), *args],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
        return result.returncode, payload, result.stderr

    def assert_ok(self, payload: dict, command: str) -> None:
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("command"), command)
        self.assertEqual(payload.get("db_path"), str(self.db_path))

    def iso_week(self, raw_date: str) -> str:
        target = date.fromisoformat(raw_date)
        iso_year, iso_week, _ = target.isocalendar()
        return f"{iso_year:04d}-W{iso_week:02d}"

    def seed_entries(self) -> None:
        code, payload, _ = self.run_cli("set-categories", "--replace", "daily", "study", "salary")
        self.assertEqual(code, 0, payload)

        for args in (
            (
                "record",
                "--amount",
                "10",
                "--category",
                "daily",
                "--account",
                "cash",
                "--description",
                "tea",
                "--date",
                "2026-03-15",
                "--source-text",
                "record tea 10",
                "--strict-category",
                "--strict-account",
            ),
            (
                "record",
                "--type",
                "expense",
                "--amount",
                "20",
                "--category",
                "study",
                "--account",
                "wechat",
                "--description",
                "books",
                "--date",
                "2026-03-16",
                "--strict-category",
                "--strict-account",
            ),
            (
                "record",
                "--type",
                "income",
                "--amount",
                "5000",
                "--category",
                "salary",
                "--account",
                "bank_card",
                "--description",
                "salary_in",
                "--date",
                "2026-03-01",
                "--strict-category",
                "--strict-account",
            ),
            (
                "record",
                "--type",
                "expense",
                "--amount",
                "8",
                "--category",
                "daily",
                "--account",
                "alipay",
                "--description",
                "breakfast",
                "--date",
                "2026-04-01",
                "--strict-category",
                "--strict-account",
            ),
        ):
            code, payload, _ = self.run_cli(*args)
            self.assertEqual(code, 0, payload)


class TestResolveDbPath(unittest.TestCase):
    def test_db_path_precedence_and_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="money_tracker_home_") as temp_dir:
            fake_home = Path(temp_dir) / "home"
            fake_home.mkdir(parents=True, exist_ok=True)
            default_path = fake_home / BOOKKEEPING.DEFAULT_DB_DIR / BOOKKEEPING.DEFAULT_DB_NAME
            legacy_path = fake_home / BOOKKEEPING.LEGACY_DB_DIR / BOOKKEEPING.DEFAULT_DB_NAME
            cli_path = fake_home / "cli.db"
            new_env_path = fake_home / "new_env.db"
            legacy_env_path = fake_home / "legacy_env.db"

            with patch.object(BOOKKEEPING.Path, "home", return_value=fake_home):
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(BOOKKEEPING.DEFAULT_DB_ENV, None)
                    os.environ.pop(BOOKKEEPING.LEGACY_DB_ENV, None)

                    self.assertEqual(BOOKKEEPING.resolve_db_path(cli_path), cli_path.resolve())

                    os.environ[BOOKKEEPING.LEGACY_DB_ENV] = str(legacy_env_path)
                    self.assertEqual(BOOKKEEPING.resolve_db_path(None), legacy_env_path.resolve())

                    os.environ[BOOKKEEPING.DEFAULT_DB_ENV] = str(new_env_path)
                    self.assertEqual(BOOKKEEPING.resolve_db_path(None), new_env_path.resolve())

                    os.environ.pop(BOOKKEEPING.DEFAULT_DB_ENV, None)
                    os.environ.pop(BOOKKEEPING.LEGACY_DB_ENV, None)

                    self.assertEqual(BOOKKEEPING.resolve_db_path(None), default_path.resolve())

                    legacy_path.parent.mkdir(parents=True, exist_ok=True)
                    legacy_path.touch()
                    self.assertEqual(BOOKKEEPING.resolve_db_path(None), legacy_path.resolve())

                    default_path.parent.mkdir(parents=True, exist_ok=True)
                    default_path.touch()
                    self.assertEqual(BOOKKEEPING.resolve_db_path(None), default_path.resolve())


class TestBookkeepingCli(CliTestCase):
    def test_init_db_creates_database_and_reports_counts(self) -> None:
        code, payload, stderr = self.run_cli("init-db")
        self.assertEqual(code, 0, stderr)
        self.assert_ok(payload, "init-db")
        self.assertTrue(self.db_path.exists())
        self.assertEqual(payload["active_category_count"], 0)
        self.assertEqual(payload["active_account_count"], 5)
        self.assertEqual(payload["entry_count"], 0)
        self.assertEqual(payload["active_recurring_transaction_count"], 0)

    def test_list_set_and_delete_accounts(self) -> None:
        code, payload, _ = self.run_cli("list-accounts")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "list-accounts")
        self.assertEqual(
            payload["active_account_names"],
            [ACCOUNT_CASH, ACCOUNT_ALIPAY, ACCOUNT_WECHAT, ACCOUNT_BANK_CARD, ACCOUNT_CREDIT_CARD],
        )

        code, payload, _ = self.run_cli("set-accounts", "--replace", "cash", "alipay")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "set-accounts")
        self.assertEqual([item["name"] for item in payload["accounts"]], [ACCOUNT_CASH, ACCOUNT_ALIPAY])

        code, payload, _ = self.run_cli("delete-account", "--name", "alipay")
        self.assertEqual(code, 0)
        self.assertEqual(payload["active_account_names"], [ACCOUNT_CASH])

        code, payload, _ = self.run_cli("list-accounts", "--all")
        self.assertEqual(code, 0)
        names_to_active = {item["name"]: item["is_active"] for item in payload["accounts"]}
        self.assertEqual(
            names_to_active,
            {
                ACCOUNT_CASH: True,
                ACCOUNT_ALIPAY: False,
                ACCOUNT_WECHAT: False,
                ACCOUNT_BANK_CARD: False,
                ACCOUNT_CREDIT_CARD: False,
            },
        )

    def test_set_and_list_categories_support_replace_add_and_all(self) -> None:
        code, payload, _ = self.run_cli("set-categories", "--replace", "daily", "study", "daily")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "set-categories")
        self.assertEqual([item["name"] for item in payload["categories"]], ["daily", "study"])

        code, payload, _ = self.run_cli("set-categories", "travel")
        self.assertEqual(code, 0)
        self.assertEqual([item["name"] for item in payload["categories"]], ["daily", "study", "travel"])

        code, payload, _ = self.run_cli("delete-category", "--name", "study")
        self.assertEqual(code, 0)
        self.assertEqual(payload["active_category_names"], ["daily", "travel"])

        code, payload, _ = self.run_cli("list-categories", "--all")
        self.assertEqual(code, 0)
        names_to_active = {item["name"]: item["is_active"] for item in payload["categories"]}
        self.assertEqual(names_to_active, {"daily": True, "study": False, "travel": True})

    def test_record_defaults_to_uncategorized_and_unspecified_account_when_not_strict(self) -> None:
        code, payload, _ = self.run_cli("record", "--amount", "5", "--description", "water")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "record")
        self.assertEqual(payload["entry"]["category"], BOOKKEEPING.DEFAULT_UNCATEGORIZED)
        self.assertEqual(payload["entry"]["account"], BOOKKEEPING.DEFAULT_UNSPECIFIED_ACCOUNT)
        self.assertFalse(payload["entry"]["category_matched_active_category"])
        self.assertFalse(payload["entry"]["account_matched_active_account"])
        self.assertEqual(payload["entry"]["occurred_on"], date.today().isoformat())

    def test_record_with_strict_category_and_account_requires_active_values(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "cash")

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "10",
            "--category",
            "study",
            "--account",
            "wechat",
            "--description",
            "books",
            "--date",
            "2026-03-15",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("Category does not match", payload["error"])

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "10",
            "--category",
            "daily",
            "--account",
            "wechat",
            "--description",
            "books",
            "--date",
            "2026-03-15",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account does not match an active predefined account.")

    def test_reports_cover_day_week_month_and_year(self) -> None:
        self.seed_entries()

        code, payload, _ = self.run_cli("day-report", "--date", "2026-03-15")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "day-report")
        self.assertEqual(payload["date"], "2026-03-15")
        self.assertEqual(payload["expense_total"], "10.00")
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_CASH)

        code, payload, _ = self.run_cli("week-report", "--week", self.iso_week("2026-03-15"))
        self.assertEqual(code, 0)
        self.assert_ok(payload, "week-report")
        self.assertEqual(payload["week"], self.iso_week("2026-03-15"))
        self.assertEqual(payload["expense_total"], "10.00")
        self.assertEqual(payload["income_total"], "0.00")

        code, payload, _ = self.run_cli("week-report", "--date", "2026-03-16")
        self.assertEqual(code, 0)
        self.assertEqual(payload["week"], self.iso_week("2026-03-16"))
        self.assertEqual(payload["expense_total"], "20.00")
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_WECHAT)

        code, payload, _ = self.run_cli("month-report", "--month", "2026-03")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "month-report")
        self.assertEqual(payload["expense_total"], "30.00")
        self.assertEqual(payload["income_total"], "5000.00")
        self.assertEqual(payload["net_total"], "4970.00")
        self.assertEqual(payload["entry_count"], 3)
        self.assertEqual(payload["top_expense_category"]["category"], "study")
        self.assertEqual(payload["top_income_category"]["category"], "salary")
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_WECHAT)
        self.assertEqual(payload["top_income_account"]["account"], ACCOUNT_BANK_CARD)

        code, payload, _ = self.run_cli("year-report", "--year", "2026")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "year-report")
        self.assertEqual(payload["year"], "2026")
        self.assertEqual(payload["expense_total"], "38.00")
        self.assertEqual(payload["income_total"], "5000.00")
        self.assertEqual(payload["entry_count"], 4)

    def test_list_transactions_supports_date_week_month_year_and_account_filters(self) -> None:
        self.seed_entries()

        code, payload, _ = self.run_cli("list-transactions", "--date", "2026-03-16")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "list-transactions")
        self.assertEqual(payload["date"], "2026-03-16")
        self.assertEqual([item["description"] for item in payload["entries"]], ["books"])

        code, payload, _ = self.run_cli("list-transactions", "--week", self.iso_week("2026-03-15"))
        self.assertEqual(code, 0)
        self.assertEqual(payload["week"], self.iso_week("2026-03-15"))
        self.assertEqual([item["description"] for item in payload["entries"]], ["tea"])

        code, payload, _ = self.run_cli("list-transactions", "--month", "2026-03", "--type", "expense", "--limit", "1")
        self.assertEqual(code, 0)
        self.assertEqual(payload["month"], "2026-03")
        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["description"], "books")

        code, payload, _ = self.run_cli("list-transactions", "--year", "2026", "--account", "alipay")
        self.assertEqual(code, 0)
        self.assertEqual(payload["year"], "2026")
        self.assertEqual([item["description"] for item in payload["entries"]], ["breakfast"])
        self.assertEqual(payload["account_filter"], ACCOUNT_ALIPAY)

    def test_recent_transactions_and_latest_entry_return_latest_ids_first(self) -> None:
        self.seed_entries()

        code, payload, _ = self.run_cli("recent-transactions", "--limit", "2")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "recent-transactions")
        self.assertEqual([item["description"] for item in payload["entries"]], ["breakfast", "salary_in"])

        code, payload, _ = self.run_cli("recent-transactions", "--type", "expense", "--account", "cash", "--limit", "5")
        self.assertEqual(code, 0)
        self.assertEqual([item["description"] for item in payload["entries"]], ["tea"])

        code, payload, _ = self.run_cli("latest-entry")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "latest-entry")
        self.assertEqual(payload["entry"]["description"], "breakfast")
        self.assertEqual(payload["entry"]["account"], ACCOUNT_ALIPAY)

    def test_update_entry_supports_account_and_note_clearing(self) -> None:
        self.seed_entries()
        code, payload, _ = self.run_cli(
            "update-entry",
            "--id",
            "1",
            "--amount",
            "12",
            "--category",
            "study",
            "--account",
            "credit_card",
            "--description",
            "tea_books",
            "--note",
            "keep_receipt",
            "--date",
            "2026-03-18",
            "--source-text",
            "update first entry",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        self.assert_ok(payload, "update-entry")
        self.assertEqual(
            payload["updated_fields"],
            ["amount", "category", "account", "description", "note", "date", "source_text"],
        )
        self.assertEqual(payload["entry"]["amount"], "12.00")
        self.assertEqual(payload["entry"]["category"], "study")
        self.assertEqual(payload["entry"]["account"], ACCOUNT_CREDIT_CARD)
        self.assertTrue(payload["entry"]["category_matched_active_category"])
        self.assertTrue(payload["entry"]["account_matched_active_account"])
        self.assertEqual(payload["entry"]["note"], "keep_receipt")
        self.assertEqual(payload["entry"]["occurred_on"], "2026-03-18")

        code, payload, _ = self.run_cli("update-entry", "--id", "1", "--note", "")
        self.assertEqual(code, 0)
        self.assertIsNone(payload["entry"]["note"])

    def test_add_list_update_and_delete_recurring_transactions(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "study")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--amount",
            "50",
            "--category",
            "daily",
            "--account",
            "alipay",
            "--description",
            "phone_bill",
            "--frequency",
            "monthly",
            "--interval",
            "1",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        self.assert_ok(payload, "add-recurring")
        self.assertEqual(payload["recurring_transaction"]["account"], ACCOUNT_ALIPAY)
        self.assertTrue(payload["recurring_transaction"]["account_matched_active_account"])

        code, payload, _ = self.run_cli("list-recurring", "--due-by", "2026-04-30", "--account", "alipay")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "list-recurring")
        self.assertEqual(len(payload["recurring_transactions"]), 1)
        self.assertEqual(payload["recurring_transactions"][0]["description"], "phone_bill")

        code, payload, _ = self.run_cli(
            "update-recurring",
            "--id",
            "1",
            "--account",
            "credit_card",
            "--frequency",
            "yearly",
            "--interval",
            "2",
            "--next-date",
            "2027-04-01",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        self.assert_ok(payload, "update-recurring")
        self.assertEqual(payload["recurring_transaction"]["account"], ACCOUNT_CREDIT_CARD)
        self.assertEqual(payload["recurring_transaction"]["frequency"], "yearly")
        self.assertEqual(payload["recurring_transaction"]["interval_count"], 2)

        code, payload, _ = self.run_cli("delete-recurring", "--id", "1")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "delete-recurring")
        self.assertEqual(payload["active_recurring_transaction_count"], 0)

    def test_delete_entry_and_delete_latest_entry_update_counts(self) -> None:
        self.seed_entries()

        code, payload, _ = self.run_cli("delete-entry", "--id", "2")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "delete-entry")
        self.assertEqual(payload["deleted_entry"]["description"], "books")
        self.assertEqual(payload["entry_count"], 3)

        code, payload, _ = self.run_cli("delete-latest-entry")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "delete-latest-entry")
        self.assertEqual(payload["deleted_entry"]["description"], "breakfast")
        self.assertEqual(payload["entry_count"], 2)

    def test_delete_category_and_account_do_not_rewrite_historical_entries(self) -> None:
        self.seed_entries()
        code, payload, _ = self.run_cli("delete-category", "--name", "daily")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "delete-category")
        self.assertFalse(payload["deleted_category"]["is_active"])

        code, payload, _ = self.run_cli("delete-account", "--name", "cash")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "delete-account")
        self.assertFalse(payload["deleted_account"]["is_active"])

        code, payload, _ = self.run_cli("list-transactions", "--month", "2026-03", "--account", "cash")
        self.assertEqual(code, 0)
        self.assertEqual([item["description"] for item in payload["entries"]], ["tea"])

    def test_empty_periods_and_latest_failures_are_stable(self) -> None:
        code, payload, _ = self.run_cli("day-report", "--date", "2026-03-15")
        self.assertEqual(code, 0)
        self.assertEqual(payload["expense_total"], "0.00")
        self.assertIsNone(payload["top_expense_category"])
        self.assertIsNone(payload["top_expense_account"])

        code, payload, _ = self.run_cli("latest-entry")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "No entries available.")

    def test_validation_failures_return_json_errors(self) -> None:
        code, payload, _ = self.run_cli("recent-transactions", "--limit", "0")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Limit must be greater than zero.")

        code, payload, _ = self.run_cli("delete-entry", "--id", "0")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Entry id must be greater than zero.")

        code, payload, _ = self.run_cli("record", "--amount", "-1", "--description", "bad")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Amount must be greater than zero.")

        code, payload, _ = self.run_cli("record", "--amount", "10", "--description", "bad", "--date", "2026-13-01")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Invalid date. Expected YYYY-MM-DD.")

        code, payload, _ = self.run_cli("record", "--amount", "10", "--account", "crypto", "--description", "bad")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Invalid account. Use one of the supported account names.")

        code, payload, _ = self.run_cli("week-report", "--week", "2026-W54")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Invalid week. Expected YYYY-Www.")

        code, payload, _ = self.run_cli("year-report", "--year", "0")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Invalid year. Expected YYYY.")

        code, payload, _ = self.run_cli("add-recurring", "--amount", "10", "--description", "rent", "--frequency", "monthly", "--interval", "0", "--next-date", "2026-04-01")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Interval must be greater than zero.")

        code, payload, _ = self.run_cli("update-entry", "--id", "1")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Entry not found.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
