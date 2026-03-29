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

ACCOUNT_ALIPAY_CNY = "\u652f\u4ed8\u5b9d (CNY)"
ACCOUNT_WECHAT_CNY = "\u5fae\u4fe1 (CNY)"
ACCOUNT_BANK_CNY = "\u94f6\u884c\u5361 (CNY)"
ACCOUNT_BANK_USD = "\u94f6\u884c\u5361 (USD)"
ACCOUNT_BANK_EUR = "\u94f6\u884c\u5361 (EUR)"
ACCOUNT_WISE_USD = "Wise (USD)"
ACCOUNT_REVOLUT_EUR = "Revolut (EUR)"

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

    def set_default_categories(self) -> None:
        code, payload, _ = self.run_cli("set-categories", "--replace", "daily", "study", "salary")
        self.assertEqual(code, 0, payload)

    def seed_cny_entries(self) -> None:
        self.set_default_categories()
        for args in (
            (
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
                "\u5fae\u4fe1",
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
                "\u94f6\u884c\u5361",
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
                "\u652f\u4ed8\u5b9d",
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
            payload["active_account_labels"],
            [
                ACCOUNT_ALIPAY_CNY,
                ACCOUNT_WECHAT_CNY,
                ACCOUNT_BANK_CNY,
                ACCOUNT_BANK_USD,
                ACCOUNT_BANK_EUR,
            ],
        )

        code, payload, _ = self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d", "\u94f6\u884c\u5361:USD", "Wise:USD")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "set-accounts")
        self.assertEqual(
            [item["label"] for item in payload["accounts"]],
            [ACCOUNT_ALIPAY_CNY, ACCOUNT_BANK_USD, ACCOUNT_WISE_USD],
        )

        code, payload, _ = self.run_cli("delete-account", "--name", "Wise:USD")
        self.assertEqual(code, 0)
        self.assertEqual(payload["active_account_labels"], [ACCOUNT_ALIPAY_CNY, ACCOUNT_BANK_USD])

        code, payload, _ = self.run_cli("list-accounts", "--all")
        self.assertEqual(code, 0)
        labels_to_active = {item["label"]: item["is_active"] for item in payload["accounts"]}
        self.assertEqual(labels_to_active[ACCOUNT_ALIPAY_CNY], True)
        self.assertEqual(labels_to_active[ACCOUNT_BANK_USD], True)
        self.assertEqual(labels_to_active[ACCOUNT_WISE_USD], False)
        self.assertEqual(labels_to_active[ACCOUNT_WECHAT_CNY], False)

    def test_update_account_rewrites_linked_entries_and_recurring_wallets(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "salary")
        self.run_cli("set-accounts", "--replace", "Wise:USD")

        code, payload, _ = self.run_cli(
            "record",
            "--type",
            "income",
            "--amount",
            "100",
            "--category",
            "salary",
            "--account",
            "Wise",
            "--description",
            "salary_usd",
            "--date",
            "2026-03-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--type",
            "income",
            "--amount",
            "20",
            "--category",
            "salary",
            "--account",
            "Wise",
            "--description",
            "weekly_bonus",
            "--frequency",
            "monthly",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli(
            "update-account",
            "--name",
            "Wise:USD",
            "--new-name",
            "TravelCard",
            "--currency",
            "EUR",
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["updated_fields"], ["name", "currency"])
        self.assertEqual(payload["previous_account"]["label"], ACCOUNT_WISE_USD)
        self.assertEqual(payload["account"]["label"], "TravelCard (EUR)")
        self.assertEqual(payload["linked_entry_count"], 1)
        self.assertEqual(payload["linked_recurring_transaction_count"], 1)

        code, payload, _ = self.run_cli("latest-entry")
        self.assertEqual(code, 0)
        self.assertEqual(payload["entry"]["account"], "TravelCard (EUR)")
        self.assertEqual(payload["entry"]["currency"], "EUR")

        code, payload, _ = self.run_cli("list-recurring")
        self.assertEqual(code, 0)
        self.assertEqual(payload["recurring_transactions"][0]["account"], "TravelCard (EUR)")
        self.assertEqual(payload["recurring_transactions"][0]["currency"], "EUR")

        code, payload, _ = self.run_cli("account-balances", "--currency", "EUR")
        self.assertEqual(code, 0)
        self.assertEqual([item["label"] for item in payload["accounts"]], ["TravelCard (EUR)"])
        self.assertEqual(payload["totals_by_currency"][0]["balance"], "100.00")

    def test_account_balances_group_wallets_by_currency(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "salary")
        self.run_cli(
            "set-accounts",
            "--replace",
            "\u652f\u4ed8\u5b9d",
            "\u94f6\u884c\u5361:USD",
            "Revolut:EUR",
        )

        for args in (
            ("record", "--type", "income", "--amount", "100", "--category", "salary", "--account", "\u652f\u4ed8\u5b9d", "--description", "salary_cny", "--date", "2026-03-01", "--strict-category", "--strict-account"),
            ("record", "--amount", "20", "--category", "daily", "--account", "\u652f\u4ed8\u5b9d", "--description", "tea", "--date", "2026-03-02", "--strict-category", "--strict-account"),
            ("record", "--type", "income", "--amount", "50", "--category", "salary", "--account", "\u94f6\u884c\u5361:USD", "--description", "salary_usd", "--date", "2026-03-03", "--strict-category", "--strict-account"),
            ("record", "--amount", "10", "--category", "daily", "--account", "\u94f6\u884c\u5361:USD", "--description", "meal_usd", "--date", "2026-03-04", "--strict-category", "--strict-account"),
            ("record", "--type", "income", "--amount", "30", "--category", "salary", "--account", "Revolut:EUR", "--description", "salary_eur", "--date", "2026-03-05", "--strict-category", "--strict-account"),
        ):
            code, payload, _ = self.run_cli(*args)
            self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli("account-balances")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "account-balances")
        balances = {item["label"]: item["balance"] for item in payload["accounts"]}
        self.assertEqual(balances[ACCOUNT_ALIPAY_CNY], "80.00")
        self.assertEqual(balances[ACCOUNT_BANK_USD], "40.00")
        self.assertEqual(balances[ACCOUNT_REVOLUT_EUR], "30.00")

        totals = {item["currency"]: item["balance"] for item in payload["totals_by_currency"]}
        self.assertEqual(totals["CNY"], "80.00")
        self.assertEqual(totals["USD"], "40.00")
        self.assertEqual(totals["EUR"], "30.00")

        code, payload, _ = self.run_cli("account-balances", "--currency", "USD")
        self.assertEqual(code, 0)
        self.assertEqual([item["label"] for item in payload["accounts"]], [ACCOUNT_BANK_USD])
        self.assertEqual(payload["totals_by_currency"][0]["currency"], "USD")
        self.assertEqual(payload["totals_by_currency"][0]["balance"], "40.00")

    def test_account_balances_include_inactive_wallets_with_all(self) -> None:
        self.run_cli("set-categories", "--replace", "salary")
        self.run_cli("set-accounts", "--replace", "Wise:USD")

        code, payload, _ = self.run_cli(
            "record",
            "--type",
            "income",
            "--amount",
            "100",
            "--category",
            "salary",
            "--account",
            "Wise",
            "--description",
            "salary_usd",
            "--date",
            "2026-03-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli("delete-account", "--name", "Wise:USD")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["active_account_labels"], [])

        code, payload, _ = self.run_cli("account-balances")
        self.assertEqual(code, 0)
        self.assertEqual(payload["accounts"], [])
        self.assertEqual(payload["totals_by_currency"], [])

        code, payload, _ = self.run_cli("account-balances", "--all")
        self.assertEqual(code, 0)
        accounts_by_label = {item["label"]: item for item in payload["accounts"]}
        self.assertIn(ACCOUNT_WISE_USD, accounts_by_label)
        self.assertFalse(accounts_by_label[ACCOUNT_WISE_USD]["is_active"])
        self.assertEqual(accounts_by_label[ACCOUNT_WISE_USD]["balance"], "100.00")
        totals_by_currency = {item["currency"]: item["balance"] for item in payload["totals_by_currency"]}
        self.assertEqual(totals_by_currency["USD"], "100.00")

    def test_ambiguous_wallet_filters_require_currency(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "salary")
        self.run_cli("set-accounts", "--replace", "Wise:USD", "Wise:EUR")

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "10",
            "--category",
            "daily",
            "--account",
            "Wise:USD",
            "--description",
            "subscription",
            "--date",
            "2026-03-15",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--type",
            "income",
            "--amount",
            "20",
            "--category",
            "salary",
            "--account",
            "Wise:USD",
            "--description",
            "bonus",
            "--frequency",
            "monthly",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli("list-transactions", "--month", "2026-03", "--account", "Wise")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account is ambiguous. Specify the currency, for example 银行卡:USD.")

        code, payload, _ = self.run_cli("list-recurring", "--account", "Wise")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account is ambiguous. Specify the currency, for example 银行卡:USD.")

    def test_record_defaults_to_uncategorized_and_unspecified_account_when_not_strict(self) -> None:
        code, payload, _ = self.run_cli("record", "--amount", "5", "--description", "water")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "record")
        self.assertEqual(payload["entry"]["category"], BOOKKEEPING.DEFAULT_UNCATEGORIZED)
        self.assertEqual(payload["entry"]["account"], BOOKKEEPING.DEFAULT_UNSPECIFIED_ACCOUNT)
        self.assertEqual(payload["entry"]["currency"], "CNY")
        self.assertFalse(payload["entry"]["category_matched_active_category"])
        self.assertFalse(payload["entry"]["account_matched_active_account"])
        self.assertEqual(payload["entry"]["occurred_on"], date.today().isoformat())

    def test_record_uses_wallet_currency_and_requires_active_wallets_when_strict(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d", "Wise:USD")

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "10",
            "--category",
            "daily",
            "--account",
            "Wise",
            "--description",
            "books",
            "--date",
            "2026-03-15",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["entry"]["account"], ACCOUNT_WISE_USD)
        self.assertEqual(payload["entry"]["currency"], "USD")

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "10",
            "--category",
            "daily",
            "--account",
            "Revolut:EUR",
            "--description",
            "books",
            "--date",
            "2026-03-15",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account does not match an active predefined account.")

    def test_record_unknown_wallet_without_strict_keeps_snapshot(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "12",
            "--category",
            "daily",
            "--account",
            "PayPal:USD",
            "--description",
            "subscription",
            "--date",
            "2026-03-15",
            "--strict-category",
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["entry"]["account"], "PayPal (USD)")
        self.assertEqual(payload["entry"]["currency"], "USD")
        self.assertFalse(payload["entry"]["account_matched_active_account"])

        code, payload, _ = self.run_cli("recent-transactions", "--account", "PayPal:USD", "--limit", "5")
        self.assertEqual(code, 0)
        self.assertEqual([item["description"] for item in payload["entries"]], ["subscription"])

        code, payload, _ = self.run_cli("account-balances", "--all")
        self.assertEqual(code, 0)
        labels = [item["label"] for item in payload["accounts"]]
        self.assertNotIn("PayPal (USD)", labels)

    def test_reports_split_totals_by_currency_for_mixed_currency_periods(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "salary")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d", "\u94f6\u884c\u5361:USD", "Revolut:EUR")

        for args in (
            (
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
                "2026-03-01",
                "--strict-category",
                "--strict-account",
            ),
            (
                "record",
                "--amount",
                "20",
                "--category",
                "daily",
                "--account",
                "\u94f6\u884c\u5361:USD",
                "--description",
                "subscription",
                "--date",
                "2026-03-02",
                "--strict-category",
                "--strict-account",
            ),
            (
                "record",
                "--type",
                "income",
                "--amount",
                "30",
                "--category",
                "salary",
                "--account",
                "Revolut:EUR",
                "--description",
                "salary_eur",
                "--date",
                "2026-03-03",
                "--strict-category",
                "--strict-account",
            ),
        ):
            code, payload, _ = self.run_cli(*args)
            self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli("month-report", "--month", "2026-03")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "month-report")
        self.assertTrue(payload["has_mixed_currencies"])
        self.assertEqual(payload["currencies"], ["CNY", "EUR", "USD"])
        self.assertIsNone(payload["expense_total"])
        self.assertIsNone(payload["income_total"])
        self.assertIsNone(payload["net_total"])
        totals = {item["currency"]: item for item in payload["totals_by_currency"]}
        self.assertEqual(totals["CNY"]["expense_total"], "10.00")
        self.assertEqual(totals["CNY"]["income_total"], "0.00")
        self.assertEqual(totals["CNY"]["net_total"], "-10.00")
        self.assertEqual(totals["USD"]["expense_total"], "20.00")
        self.assertEqual(totals["USD"]["income_total"], "0.00")
        self.assertEqual(totals["USD"]["net_total"], "-20.00")
        self.assertEqual(totals["EUR"]["expense_total"], "0.00")
        self.assertEqual(totals["EUR"]["income_total"], "30.00")
        self.assertEqual(totals["EUR"]["net_total"], "30.00")
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_BANK_USD)
        self.assertEqual(payload["top_income_account"]["account"], ACCOUNT_REVOLUT_EUR)
        self.assertEqual(
            [item["account"] for item in payload["expense_by_account"]],
            [ACCOUNT_BANK_USD, ACCOUNT_ALIPAY_CNY],
        )
        self.assertEqual(
            [(item["category"], item["currency"]) for item in payload["expense_by_category"]],
            [("daily", "USD"), ("daily", "CNY")],
        )

    def test_reports_cover_day_week_month_and_year(self) -> None:
        self.seed_cny_entries()

        code, payload, _ = self.run_cli("day-report", "--date", "2026-03-15")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "day-report")
        self.assertEqual(payload["date"], "2026-03-15")
        self.assertEqual(payload["expense_total"], "10.00")
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_ALIPAY_CNY)

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
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_WECHAT_CNY)

        code, payload, _ = self.run_cli("month-report", "--month", "2026-03")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "month-report")
        self.assertEqual(payload["expense_total"], "30.00")
        self.assertEqual(payload["income_total"], "5000.00")
        self.assertEqual(payload["net_total"], "4970.00")
        self.assertEqual(payload["entry_count"], 3)
        self.assertEqual(payload["top_expense_category"]["category"], "study")
        self.assertEqual(payload["top_income_category"]["category"], "salary")
        self.assertEqual(payload["top_expense_account"]["account"], ACCOUNT_WECHAT_CNY)
        self.assertEqual(payload["top_income_account"]["account"], ACCOUNT_BANK_CNY)

        code, payload, _ = self.run_cli("year-report", "--year", "2026")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "year-report")
        self.assertEqual(payload["year"], "2026")
        self.assertEqual(payload["expense_total"], "38.00")
        self.assertEqual(payload["income_total"], "5000.00")
        self.assertEqual(payload["entry_count"], 4)

    def test_list_transactions_supports_date_week_month_year_and_wallet_filters(self) -> None:
        self.seed_cny_entries()

        code, payload, _ = self.run_cli("list-transactions", "--date", "2026-03-16")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "list-transactions")
        self.assertEqual(payload["date"], "2026-03-16")
        self.assertEqual([item["description"] for item in payload["entries"]], ["books"])

        code, payload, _ = self.run_cli("list-transactions", "--week", self.iso_week("2026-03-15"))
        self.assertEqual(code, 0)
        self.assertEqual(payload["week"], self.iso_week("2026-03-15"))
        self.assertEqual([item["description"] for item in payload["entries"]], ["tea"])

        code, payload, _ = self.run_cli(
            "list-transactions",
            "--month",
            "2026-03",
            "--type",
            "expense",
            "--limit",
            "1",
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["month"], "2026-03")
        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["description"], "books")

        code, payload, _ = self.run_cli("list-transactions", "--year", "2026", "--account", "\u652f\u4ed8\u5b9d")
        self.assertEqual(code, 0)
        self.assertEqual(payload["account_filter"], ACCOUNT_ALIPAY_CNY)
        self.assertEqual([item["description"] for item in payload["entries"]], ["breakfast", "tea"])

    def test_recent_transactions_and_latest_entry_return_latest_ids_first(self) -> None:
        self.seed_cny_entries()

        code, payload, _ = self.run_cli("latest-entry")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "latest-entry")
        self.assertEqual(payload["entry"]["description"], "breakfast")
        self.assertEqual(payload["entry"]["account"], ACCOUNT_ALIPAY_CNY)

        code, payload, _ = self.run_cli("recent-transactions", "--account", "\u652f\u4ed8\u5b9d", "--limit", "5")
        self.assertEqual(code, 0)
        self.assert_ok(payload, "recent-transactions")
        self.assertEqual(payload["account_filter"], ACCOUNT_ALIPAY_CNY)
        self.assertEqual([item["description"] for item in payload["entries"]], ["breakfast", "tea"])

    def test_add_list_update_and_delete_recurring_transactions(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "salary")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d", "\u94f6\u884c\u5361:USD", "Wise:USD")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--amount",
            "3000",
            "--category",
            "daily",
            "--account",
            "\u652f\u4ed8\u5b9d",
            "--description",
            "rent",
            "--frequency",
            "monthly",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["recurring_transaction"]["account"], ACCOUNT_ALIPAY_CNY)
        self.assertEqual(payload["recurring_transaction"]["currency"], "CNY")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--type",
            "income",
            "--amount",
            "100",
            "--category",
            "salary",
            "--account",
            "Wise",
            "--description",
            "weekly_bonus",
            "--frequency",
            "weekly",
            "--next-date",
            "2026-04-03",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        recurring_id = payload["recurring_transaction"]["id"]
        self.assertEqual(payload["recurring_transaction"]["account"], ACCOUNT_WISE_USD)
        self.assertEqual(payload["recurring_transaction"]["currency"], "USD")

        code, payload, _ = self.run_cli("list-recurring", "--account", "Wise:USD")
        self.assertEqual(code, 0)
        self.assertEqual(payload["account_filter"], ACCOUNT_WISE_USD)
        self.assertEqual([item["description"] for item in payload["recurring_transactions"]], ["weekly_bonus"])

        code, payload, _ = self.run_cli(
            "update-recurring",
            "--id",
            str(recurring_id),
            "--account",
            "\u94f6\u884c\u5361:USD",
            "--next-date",
            "2026-04-10",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["recurring_transaction"]["account"], ACCOUNT_BANK_USD)
        self.assertEqual(payload["recurring_transaction"]["currency"], "USD")

        code, payload, _ = self.run_cli("delete-recurring", "--id", str(recurring_id))
        self.assertEqual(code, 0)
        self.assertEqual(payload["deleted_recurring_transaction"]["account"], ACCOUNT_BANK_USD)

    def test_update_entry_supports_wallets_and_note_clearing(self) -> None:
        self.run_cli("set-categories", "--replace", "daily", "study")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d", "\u5fae\u4fe1")

        code, payload, _ = self.run_cli(
            "record",
            "--amount",
            "10",
            "--category",
            "daily",
            "--account",
            "\u652f\u4ed8\u5b9d",
            "--description",
            "tea",
            "--note",
            "old note",
            "--date",
            "2026-03-15",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)
        entry_id = payload["entry"]["id"]

        code, payload, _ = self.run_cli(
            "update-entry",
            "--id",
            str(entry_id),
            "--amount",
            "12",
            "--category",
            "study",
            "--account",
            "\u5fae\u4fe1",
            "--description",
            "tea_book",
            "--note",
            "",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["entry"]["amount"], "12.00")
        self.assertEqual(payload["entry"]["category"], "study")
        self.assertEqual(payload["entry"]["account"], ACCOUNT_WECHAT_CNY)
        self.assertIsNone(payload["entry"]["note"])

    def test_update_entry_validation_paths(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")

        code, payload, _ = self.run_cli(
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
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)
        entry_id = payload["entry"]["id"]

        code, payload, _ = self.run_cli("update-entry", "--id", str(entry_id))
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Provide at least one field to update.")

        code, payload, _ = self.run_cli("update-entry", "--id", "999", "--amount", "12")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Entry not found.")

        code, payload, _ = self.run_cli("update-entry", "--id", str(entry_id), "--currency", "USD")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Currency does not match the selected account.")

        code, payload, _ = self.run_cli("update-entry", "--id", str(entry_id), "--description", "")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Description is required.")

    def test_update_account_validation_paths(self) -> None:
        self.run_cli("set-accounts", "--replace", "Wise:USD", "Revolut:EUR")

        code, payload, _ = self.run_cli("update-account", "--name", "Wise:USD")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Provide at least one field to update.")

        code, payload, _ = self.run_cli("update-account", "--name", "Wise:USD", "--new-name", "Wise", "--currency", "USD")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Provide at least one changed field to update.")

        code, payload, _ = self.run_cli("update-account", "--name", "Wise:USD", "--new-name", "Revolut", "--currency", "EUR")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account already exists.")
        self.assertEqual(payload["target_account"], ACCOUNT_REVOLUT_EUR)

    def test_update_recurring_validation_paths(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--amount",
            "30",
            "--category",
            "daily",
            "--account",
            "\u652f\u4ed8\u5b9d",
            "--description",
            "snacks",
            "--frequency",
            "monthly",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)
        recurring_id = payload["recurring_transaction"]["id"]

        code, payload, _ = self.run_cli("update-recurring", "--id", str(recurring_id))
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Provide at least one field to update.")

        code, payload, _ = self.run_cli("update-recurring", "--id", str(recurring_id), "--currency", "USD")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Currency does not match the selected account.")

        code, payload, _ = self.run_cli("update-recurring", "--id", "999", "--description", "missing")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Recurring transaction not found.")

    def test_update_recurring_activate_and_deactivate_cycle(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--amount",
            "30",
            "--category",
            "daily",
            "--account",
            "\u652f\u4ed8\u5b9d",
            "--description",
            "snacks",
            "--frequency",
            "monthly",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)
        recurring_id = payload["recurring_transaction"]["id"]

        code, payload, _ = self.run_cli("update-recurring", "--id", str(recurring_id), "--deactivate")
        self.assertEqual(code, 0)
        self.assertIn("deactivate", payload["updated_fields"])
        self.assertFalse(payload["recurring_transaction"]["is_active"])

        code, payload, _ = self.run_cli("list-recurring")
        self.assertEqual(code, 0)
        self.assertEqual(payload["recurring_transactions"], [])

        code, payload, _ = self.run_cli("update-recurring", "--id", str(recurring_id), "--activate")
        self.assertEqual(code, 0)
        self.assertIn("activate", payload["updated_fields"])
        self.assertTrue(payload["recurring_transaction"]["is_active"])

        code, payload, _ = self.run_cli("list-recurring")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["recurring_transactions"]), 1)
        self.assertEqual(payload["recurring_transactions"][0]["description"], "snacks")

    def test_delete_category_and_account_do_not_rewrite_historical_entries(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")
        code, payload, _ = self.run_cli(
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
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0)
        entry_id = payload["entry"]["id"]

        code, payload, _ = self.run_cli("delete-category", "--name", "daily")
        self.assertEqual(code, 0)
        self.assertEqual(payload["active_category_names"], [])

        code, payload, _ = self.run_cli("delete-account", "--name", "\u652f\u4ed8\u5b9d")
        self.assertEqual(code, 0)
        self.assertEqual(payload["active_account_labels"], [])

        code, payload, _ = self.run_cli("list-transactions", "--date", "2026-03-15")
        self.assertEqual(code, 0)
        self.assertEqual(payload["entries"][0]["id"], entry_id)
        self.assertEqual(payload["entries"][0]["category"], "daily")
        self.assertEqual(payload["entries"][0]["account"], ACCOUNT_ALIPAY_CNY)

    def test_delete_entry_and_delete_latest_entry_update_counts(self) -> None:
        self.seed_cny_entries()

        code, payload, _ = self.run_cli("delete-entry", "--id", "1")
        self.assertEqual(code, 0)
        self.assertEqual(payload["deleted_entry"]["description"], "tea")
        self.assertEqual(payload["entry_count"], 3)

        code, payload, _ = self.run_cli("delete-latest-entry")
        self.assertEqual(code, 0)
        self.assertEqual(payload["deleted_entry"]["description"], "breakfast")
        self.assertEqual(payload["entry_count"], 2)

    def test_empty_periods_and_latest_failures_are_stable(self) -> None:
        code, payload, _ = self.run_cli("month-report", "--month", "2026-03")
        self.assertEqual(code, 0)
        self.assertEqual(payload["expense_total"], "0.00")
        self.assertEqual(payload["income_total"], "0.00")
        self.assertEqual(payload["entry_count"], 0)

        code, payload, _ = self.run_cli("latest-entry")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "No entries available.")

        code, payload, _ = self.run_cli("delete-latest-entry")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "No entries available to delete.")

    def test_repeat_deletions_fail_cleanly(self) -> None:
        self.run_cli("set-categories", "--replace", "daily")
        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--amount",
            "20",
            "--category",
            "daily",
            "--account",
            "\u652f\u4ed8\u5b9d",
            "--description",
            "coffee",
            "--frequency",
            "monthly",
            "--next-date",
            "2026-04-01",
            "--strict-category",
            "--strict-account",
        )
        self.assertEqual(code, 0, payload)
        recurring_id = payload["recurring_transaction"]["id"]

        code, payload, _ = self.run_cli("delete-recurring", "--id", str(recurring_id))
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli("delete-recurring", "--id", str(recurring_id))
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Recurring transaction is already inactive.")

        code, payload, _ = self.run_cli("list-recurring", "--all")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["recurring_transactions"]), 1)
        self.assertFalse(payload["recurring_transactions"][0]["is_active"])

        code, payload, _ = self.run_cli("delete-account", "--name", "\u652f\u4ed8\u5b9d")
        self.assertEqual(code, 0, payload)

        code, payload, _ = self.run_cli("delete-account", "--name", "\u652f\u4ed8\u5b9d")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account is already inactive.")

    def test_validation_failures_return_json_errors(self) -> None:
        code, payload, _ = self.run_cli("list-transactions", "--week", "2026-W99")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Invalid week. Expected YYYY-Www.")

        code, payload, _ = self.run_cli("year-report", "--year", "0")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Invalid year. Expected YYYY.")

        code, payload, _ = self.run_cli(
            "add-recurring",
            "--amount",
            "10",
            "--description",
            "bad_interval",
            "--frequency",
            "monthly",
            "--interval",
            "0",
            "--next-date",
            "2026-04-01",
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Interval must be greater than zero.")

        code, payload, _ = self.run_cli("set-accounts", "Wise")
        self.assertEqual(code, 1)
        self.assertEqual(
            payload["error"],
            "Account currency is required. Use a wallet name with a currency, for example 支付宝:CNY or 银行卡:USD.",
        )

        code, payload, _ = self.run_cli("update-account", "--name", "\u94f6\u884c\u5361", "--new-name", "PrimaryCard")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Account is ambiguous. Specify the currency, for example 银行卡:USD.")

        self.run_cli("set-accounts", "--replace", "\u652f\u4ed8\u5b9d")
        code, payload, _ = self.run_cli("record", "--amount", "10", "--account", "\u652f\u4ed8\u5b9d", "--currency", "USD", "--description", "bad_currency", "--strict-account")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Currency does not match the selected account.")

        code, payload, _ = self.run_cli("recent-transactions", "--limit", "0")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error"], "Limit must be greater than zero.")


if __name__ == "__main__":
    unittest.main()
